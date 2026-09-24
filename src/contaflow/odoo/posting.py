"""Contabilizacion de documentos en Odoo (asiento balanceado por montos).

Decision aprobada: armamos las lineas debito/credito con los montos ya parseados
(sin usar el motor de impuestos de Odoo). Todos los documentos se registran como asiento
tipo `entry`; lo que cambia es el diario, el sentido de las lineas y la contraparte.

Compra (FACTURA_COMPRA, DOCUMENTO_SOPORTE):
  Debito  base            -> cuenta propuesta (gasto/activo)
  Debito  IVA descontable -> cuenta IVA
  Credito retenciones     -> Retefuente/ReteIVA/ReteICA por pagar
  Credito CxP proveedor   -> base + IVA - retenciones

Venta (FACTURA_VENTA) -> espejo de la compra:
  Debito  CxC cliente        -> base + IVA - retenciones que nos practican
  Debito  retenciones a favor -> anticipos (activo)
  Credito ingreso           -> cuenta propuesta
  Credito IVA generado      -> por pagar

Notas: la perspectiva (compra/venta) de una nota se decide por NIT (misma logica que la
factura). NOTA_CREDITO invierte el asiento de su lado; NOTA_DEBITO va en el mismo sentido
que la factura de su lado. El asiento siempre queda balanceado (debitos == creditos).

Idempotencia: no se crea un asiento si ya existe uno en Odoo con ref = CUFE, o si ya
tenemos un posting para el documento. Contra Odoo, siempre via su API (nunca SQL).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.core.currency import COP, TrmProvider
from contaflow.core.exceptions import OdooConnectionError, PostingError
from contaflow.core.money import to_money
from contaflow.core.nit import same_nit
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import (
    ActorType,
    DocType,
    DocumentEventType,
    DocumentStatus,
    TaxCategory,
)
from contaflow.models.posting import Posting
from contaflow.models.source_document import SourceDocument
from contaflow.odoo.client import OdooClient

logger = logging.getLogger(__name__)

_PURCHASE_TYPES = {DocType.FACTURA_COMPRA, DocType.DOCUMENTO_SOPORTE}


class PostingSide(StrEnum):
    """Lado contable de un documento. No se persiste: se calcula al contabilizar."""

    PURCHASE = "PURCHASE"
    SALE = "SALE"


@dataclass(frozen=True)
class PostingAccounts:
    # Lado compra.
    payable: str | None = None
    iva: str | None = None
    retefuente: str | None = None
    reteiva: str | None = None
    reteica: str | None = None
    # Lado venta.
    receivable: str | None = None
    iva_generado: str | None = None
    retefuente_favor: str | None = None
    reteiva_favor: str | None = None
    reteica_favor: str | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> PostingAccounts:
        # No se exige ninguna cuenta aqui: cada armador valida las que necesita, para que
        # una config solo-compras o solo-ventas sea valida.
        cfg = config or {}
        return cls(
            payable=cfg.get("payable_account_code"),
            iva=cfg.get("iva_account_code"),
            retefuente=cfg.get("retefuente_account_code"),
            reteiva=cfg.get("reteiva_account_code"),
            reteica=cfg.get("reteica_account_code"),
            receivable=cfg.get("receivable_account_code"),
            iva_generado=cfg.get("iva_generado_account_code"),
            retefuente_favor=cfg.get("retefuente_favor_account_code"),
            reteiva_favor=cfg.get("reteiva_favor_account_code"),
            reteica_favor=cfg.get("reteica_favor_account_code"),
        )

    def withholding_account(self, category: TaxCategory) -> str | None:
        """Cuenta de la retencion POR PAGAR (compra: se la retenemos al proveedor)."""
        return {
            TaxCategory.RETEFUENTE: self.retefuente,
            TaxCategory.RETEIVA: self.reteiva,
            TaxCategory.RETEICA: self.reteica,
        }.get(category)

    def withholding_favor_account(self, category: TaxCategory) -> str | None:
        """Cuenta de la retencion A FAVOR (venta: nos la practica el cliente, es activo)."""
        return {
            TaxCategory.RETEFUENTE: self.retefuente_favor,
            TaxCategory.RETEIVA: self.reteiva_favor,
            TaxCategory.RETEICA: self.reteica_favor,
        }.get(category)


@dataclass(frozen=True)
class MoveLine:
    account_code: str
    name: str
    debit: Decimal
    credit: Decimal


def build_move_lines(
    subtotal: Decimal,
    base_account_code: str,
    taxes: Iterable[DocumentTax],
    accounts: PostingAccounts,
    rate: Decimal = Decimal("1"),
) -> list[MoveLine]:
    """Arma las lineas del asiento de una compra. `rate` es la TRM (1 si ya es COP)."""
    lines: list[MoveLine] = [
        MoveLine(base_account_code, "Base gravable", to_money(subtotal * rate), Decimal("0"))
    ]
    for tax in taxes:
        amount = to_money(tax.tax_amount * rate)
        if tax.is_withholding:
            code = accounts.withholding_account(tax.category)
            if not code:
                raise PostingError(f"Sin cuenta configurada para {tax.category.value}")
            lines.append(MoveLine(code, tax.tax_name, Decimal("0"), amount))
        else:
            if not accounts.iva:
                raise PostingError("Sin cuenta IVA configurada (iva_account_code)")
            lines.append(MoveLine(accounts.iva, tax.tax_name, amount, Decimal("0")))

    if not accounts.payable:
        raise PostingError("Sin cuenta CxP configurada (payable_account_code)")
    total_debit = sum((line.debit for line in lines), Decimal("0"))
    total_credit = sum((line.credit for line in lines), Decimal("0"))
    payable_amount = total_debit - total_credit
    lines.append(MoveLine(accounts.payable, "Cuentas por pagar", Decimal("0"), payable_amount))

    _assert_balanced(lines)
    return lines


def build_sale_move_lines(
    subtotal: Decimal,
    revenue_account_code: str,
    taxes: Iterable[DocumentTax],
    accounts: PostingAccounts,
    rate: Decimal = Decimal("1"),
) -> list[MoveLine]:
    """Arma las lineas del asiento de una venta (espejo de la compra). `rate` es la TRM."""
    if not accounts.receivable:
        raise PostingError("Sin cuenta CxC configurada (receivable_account_code)")
    lines: list[MoveLine] = []
    for tax in taxes:
        amount = to_money(tax.tax_amount * rate)
        if tax.is_withholding:
            # Retencion que nos practica el cliente: anticipo (activo) -> debito.
            code = accounts.withholding_favor_account(tax.category)
            if not code:
                raise PostingError(f"Sin cuenta a favor configurada para {tax.category.value}")
            lines.append(MoveLine(code, tax.tax_name, amount, Decimal("0")))
        else:
            # IVA generado: por pagar -> credito.
            if not accounts.iva_generado:
                raise PostingError(
                    "Sin cuenta IVA generado configurada (iva_generado_account_code)"
                )
            lines.append(MoveLine(accounts.iva_generado, tax.tax_name, Decimal("0"), amount))

    lines.append(MoveLine(revenue_account_code, "Ingreso", Decimal("0"), to_money(subtotal * rate)))

    total_debit = sum((line.debit for line in lines), Decimal("0"))
    total_credit = sum((line.credit for line in lines), Decimal("0"))
    receivable_amount = total_credit - total_debit
    lines.append(
        MoveLine(accounts.receivable, "Cuentas por cobrar", receivable_amount, Decimal("0"))
    )

    _assert_balanced(lines)
    return lines


def reverse_lines(lines: list[MoveLine]) -> list[MoveLine]:
    """Invierte debito<->credito de cada linea (una nota credito reversa su asiento)."""
    return [MoveLine(line.account_code, line.name, line.credit, line.debit) for line in lines]


def _assert_balanced(lines: list[MoveLine]) -> None:
    debit = sum((line.debit for line in lines), Decimal("0"))
    credit = sum((line.credit for line in lines), Decimal("0"))
    if debit != credit:
        raise PostingError(f"Asiento descuadrado: debitos {debit} != creditos {credit}")


def posting_side(
    doc_type: DocType | None,
    company_nit: str,
    issuer_nit: str | None,
    receiver_nit: str | None,
) -> PostingSide:
    """Decide si un documento es compra o venta desde la perspectiva de la empresa."""
    if doc_type in _PURCHASE_TYPES:
        return PostingSide.PURCHASE
    if doc_type is DocType.FACTURA_VENTA:
        return PostingSide.SALE
    if doc_type in (DocType.NOTA_CREDITO, DocType.NOTA_DEBITO):
        if same_nit(receiver_nit, company_nit):
            return PostingSide.PURCHASE
        if same_nit(issuer_nit, company_nit):
            return PostingSide.SALE
        raise PostingError("No se pudo determinar el lado de la nota: NITs no coinciden")
    raise PostingError(f"Tipo no soportado para posting: {doc_type}")


def _resolve_trm(doc: SourceDocument, provider: TrmProvider | None) -> Decimal:
    """TRM a aplicar: 1 si es COP, la del XML si viene, o la del proveedor. Falla si falta."""
    if doc.currency == COP:
        return Decimal("1")
    if doc.trm is not None:
        return doc.trm
    if provider is not None:
        rate = provider.rate_for(doc.currency, doc.issue_date)
        if rate is not None:
            return rate
    raise PostingError(f"Documento en {doc.currency} sin TRM (ni en el XML ni en el proveedor)")


def _to_odoo_amount(value: Decimal) -> float:
    # Unico punto donde el dinero pasa a float: la API XML-RPC de Odoo no acepta Decimal.
    return float(to_money(value))


def _event(
    doc: SourceDocument, event_type: DocumentEventType, payload: dict[str, object]
) -> DocumentEvent:
    return DocumentEvent(
        tenant_id=doc.tenant_id,
        document_id=doc.id,
        event_type=event_type,
        actor_type=ActorType.SYSTEM,
        payload=payload,
    )


def _record_posting(session: Session, doc: SourceDocument, odoo_move_id: int) -> None:
    session.add(
        Posting(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            odoo_move_id=odoo_move_id,
            posted_at=datetime.now(UTC),
        )
    )
    doc.status = DocumentStatus.POSTED
    session.add(_event(doc, DocumentEventType.POSTED, {"odoo_move_id": odoo_move_id}))


def post_document(
    session: Session,
    client: OdooClient,
    document_id: uuid.UUID,
    trm_provider: TrmProvider | None = None,
) -> DocumentStatus:
    """Contabiliza un documento CLASSIFIED en Odoo. Idempotente.

    Si el documento esta en moneda extranjera, convierte los montos a COP con la TRM del
    XML o, en su defecto, la del `trm_provider`.
    """
    doc = session.get(SourceDocument, document_id)
    if doc is None:
        raise PostingError(f"source_document inexistente: {document_id}")
    if doc.status is DocumentStatus.POSTED:
        return doc.status
    if doc.status is not DocumentStatus.CLASSIFIED:
        return doc.status  # solo se contabiliza lo clasificado/aprobado

    # Idempotencia local: ya hay un posting para este documento.
    if session.scalar(select(Posting.id).where(Posting.document_id == doc.id)) is not None:
        doc.status = DocumentStatus.POSTED
        session.commit()
        return doc.status

    try:
        subtotal = doc.subtotal
        proposed = doc.proposed_account_code
        if not proposed or subtotal is None:
            raise PostingError("Documento sin cuenta propuesta o sin subtotal")
        cufe = doc.cufe
        issuer_nit = doc.issuer_nit
        if not cufe or not issuer_nit:
            raise PostingError("Documento sin CUFE o NIT de emisor")

        company = session.get(Company, doc.company_id)
        if company is None:
            raise PostingError("company inexistente")
        accounts = PostingAccounts.from_config(company.posting_config)

        side = posting_side(doc.doc_type, company.nit, issuer_nit, doc.receiver_nit)

        # Idempotencia contra Odoo: ¿ya existe un asiento con este CUFE?
        existing = client.find_move_by_ref(cufe)
        if existing is not None:
            _record_posting(session, doc, existing)
            session.commit()
            logger.info("documento %s ya estaba en Odoo (move %s)", doc.id, existing)
            return doc.status

        taxes = list(session.scalars(select(DocumentTax).where(DocumentTax.document_id == doc.id)))

        # Moneda extranjera -> COP con la TRM (1 si ya es COP).
        rate = _resolve_trm(doc, trm_provider)

        if side is PostingSide.PURCHASE:
            lines = build_move_lines(subtotal, proposed, taxes, accounts, rate)
            journal_id = client.find_purchase_journal_id()
            if journal_id is None:
                raise PostingError("Odoo no tiene un diario de compras")
            # La contraparte de una compra es el emisor (proveedor).
            partner_nit = issuer_nit
            partner_name = doc.issuer_name or issuer_nit
        else:
            lines = build_sale_move_lines(subtotal, proposed, taxes, accounts, rate)
            journal_id = client.find_sale_journal_id()
            if journal_id is None:
                raise PostingError("Odoo no tiene un diario de ventas")
            # La contraparte de una venta es el receptor (cliente).
            if not doc.receiver_nit:
                raise PostingError("Documento de venta sin NIT del cliente (receiver_nit)")
            partner_nit = doc.receiver_nit
            partner_name = doc.receiver_nit

        # Una nota credito reversa el asiento de su lado; la nota debito va igual que la
        # factura de su lado (no se invierte).
        if doc.doc_type is DocType.NOTA_CREDITO:
            lines = reverse_lines(lines)

        partner_id = client.find_partner_id(partner_nit) or client.create_partner(
            partner_name, partner_nit
        )

        line_ids: list[Any] = []
        for line in lines:
            account_id = client.find_account_id(line.account_code)
            if account_id is None:
                raise PostingError(f"La cuenta {line.account_code} no existe en Odoo")
            line_ids.append(
                (
                    0,
                    0,
                    {
                        "account_id": account_id,
                        "partner_id": partner_id,
                        "name": line.name,
                        "debit": _to_odoo_amount(line.debit),
                        "credit": _to_odoo_amount(line.credit),
                    },
                )
            )

        move = {
            "move_type": "entry",
            "ref": cufe,
            "date": doc.issue_date.isoformat() if doc.issue_date else None,
            "journal_id": journal_id,
            "line_ids": line_ids,
        }
        move_id = client.create_move(move)
        client.post_move(move_id)

        _record_posting(session, doc, move_id)
        session.commit()
        logger.info("documento %s -> POSTED (odoo move %s)", doc.id, move_id)
        return doc.status

    except PostingError as exc:
        session.rollback()
        doc = session.get(SourceDocument, document_id)
        if doc is not None:
            doc.status = DocumentStatus.POSTING_FAILED
            session.add(_event(doc, DocumentEventType.POSTING_FAILED, {"error": str(exc)[:200]}))
            session.commit()
        logger.info("documento %s -> POSTING_FAILED (%s)", document_id, exc)
        return DocumentStatus.POSTING_FAILED
    except OdooConnectionError:
        # Transitorio: no marcamos fallo, dejamos que la tarea reintente.
        session.rollback()
        raise
