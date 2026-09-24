"""Tests de integracion del posting a Odoo (Fase 3b), con un OdooClient falso."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import DocType, DocumentEventType, DocumentStatus, TaxCategory
from contaflow.models.posting import Posting
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant
from contaflow.odoo.posting import post_document

POSTING_CONFIG = {
    "payable_account_code": "220505",
    "iva_account_code": "240810",
    "retefuente_account_code": "236540",
    "reteica_account_code": "236805",
}
KNOWN_ACCOUNTS = {"511595": 1, "240810": 2, "236540": 3, "236805": 4, "220505": 5}

SALE_CONFIG = {
    "receivable_account_code": "130505",
    "iva_generado_account_code": "240805",
    "retefuente_favor_account_code": "135515",
    "reteica_favor_account_code": "135518",
}
# Cuentas que Odoo conoce para el lado venta (ingreso 413595 + las de SALE_CONFIG).
SALE_KNOWN_ACCOUNTS = {"413595": 20, "240805": 21, "135515": 22, "135518": 23, "130505": 24}


class FakeOdoo:
    def __init__(self, accounts: dict[str, int], existing_ref: str | None = None) -> None:
        self.accounts = accounts
        self.existing_ref = existing_ref
        self.moves: dict[int, dict[str, Any]] = {}
        self.posted: list[int] = []
        self._next = 100

    def find_move_by_ref(self, ref: str) -> int | None:
        return 999 if ref == self.existing_ref else None

    def find_account_id(self, code: str) -> int | None:
        return self.accounts.get(code)

    def find_partner_id(self, nit: str) -> int | None:
        return 7

    def create_partner(self, name: str, nit: str) -> int:
        return 7

    def find_purchase_journal_id(self) -> int | None:
        return 11

    def find_sale_journal_id(self) -> int | None:
        return 12

    def create_move(self, move: dict[str, Any]) -> int:
        move_id = self._next
        self._next += 1
        self.moves[move_id] = move
        return move_id

    def post_move(self, move_id: int) -> None:
        self.posted.append(move_id)


def _seed_classified(session: Session, config: dict[str, Any] | None = POSTING_CONFIG) -> uuid.UUID:
    tenant = Tenant(name="Firma Post")
    session.add(tenant)
    session.flush()
    company = Company(
        tenant_id=tenant.id,
        name="Empresa",
        nit=f"900{uuid.uuid4().hex[:9]}",
        posting_config=config,
    )
    session.add(company)
    session.flush()
    doc = SourceDocument(
        tenant_id=tenant.id,
        company_id=company.id,
        status=DocumentStatus.CLASSIFIED,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        cufe=f"CUFE-{uuid.uuid4().hex}",
        doc_type=DocType.FACTURA_COMPRA,
        issuer_nit="900555111",
        issuer_name="Proveedor SAS",
        subtotal=Decimal("1000000.00"),
        total_tax=Decimal("190000.00"),
        total_withholding=Decimal("34660.00"),
        total=Decimal("1190000.00"),
        proposed_account_code="511595",
    )
    session.add(doc)
    session.flush()
    session.add(
        DocumentTax(
            tenant_id=tenant.id,
            document_id=doc.id,
            category=TaxCategory.IVA,
            is_withholding=False,
            tax_name="IVA",
            percent=Decimal("19.00"),
            taxable_amount=Decimal("1000000.00"),
            tax_amount=Decimal("190000.00"),
        )
    )
    session.add(
        DocumentTax(
            tenant_id=tenant.id,
            document_id=doc.id,
            category=TaxCategory.RETEFUENTE,
            is_withholding=True,
            tax_name="Retefuente",
            percent=Decimal("2.50"),
            taxable_amount=Decimal("1000000.00"),
            tax_amount=Decimal("25000.00"),
        )
    )
    session.add(
        DocumentTax(
            tenant_id=tenant.id,
            document_id=doc.id,
            category=TaxCategory.RETEICA,
            is_withholding=True,
            tax_name="ReteICA",
            percent=Decimal("0.966"),
            taxable_amount=Decimal("1000000.00"),
            tax_amount=Decimal("9660.00"),
        )
    )
    session.commit()
    return doc.id


def test_post_ok(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_classified(session)
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTED
        assert len(odoo.posted) == 1  # se contabilizo (action_post)

        posting = session.scalar(select(Posting).where(Posting.document_id == doc_id))
        assert posting is not None
        assert posting.odoo_move_id in odoo.moves

        events = set(
            session.scalars(
                select(DocumentEvent.event_type).where(DocumentEvent.document_id == doc_id)
            )
        )
        assert DocumentEventType.POSTED in events


def test_idempotente_si_ya_existe_en_odoo(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_classified(session)
        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        odoo = FakeOdoo(KNOWN_ACCOUNTS, existing_ref=doc.cufe)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTED
        assert odoo.moves == {}  # NO creo un asiento nuevo
        posting = session.scalar(select(Posting).where(Posting.document_id == doc_id))
        assert posting is not None
        assert posting.odoo_move_id == 999


def test_cuenta_faltante_marca_posting_failed(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_classified(session)
        # Odoo no conoce la cuenta base 511595.
        accounts = {k: v for k, v in KNOWN_ACCOUNTS.items() if k != "511595"}
        odoo = FakeOdoo(accounts)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTING_FAILED
        assert odoo.posted == []


def test_config_incompleta_marca_posting_failed(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_classified(session, config={"iva_account_code": "240810"})  # sin payable
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTING_FAILED


def test_post_moneda_extranjera_convierte_con_trm_del_xml(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        # Compra en USD con TRM ya guardada (venida del XML).
        doc_id = _seed_doc(
            session,
            doc_type=DocType.FACTURA_COMPRA,
            config=POSTING_CONFIG,
            company_nit="800111222",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="511595",
            currency="USD",
            trm=Decimal("4000.000000"),
        )
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTED

        move = next(iter(odoo.moves.values()))
        # Base gravable (511595 -> 1) convertida a COP: 1.000.000 USD * 4.000.
        base = _line_by_account(move, 1)
        assert base["debit"] == 4000000000.00
        _assert_move_balanced(move)


def test_post_moneda_extranjera_sin_trm_falla(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(
            session,
            doc_type=DocType.FACTURA_COMPRA,
            config=POSTING_CONFIG,
            company_nit="800111222",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="511595",
            currency="USD",
            trm=None,
        )
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        # Sin TRM en el XML ni proveedor -> no se puede convertir.
        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTING_FAILED


def test_post_moneda_extranjera_usa_proveedor_de_trm(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(
            session,
            doc_type=DocType.FACTURA_COMPRA,
            config=POSTING_CONFIG,
            company_nit="800111222",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="511595",
            currency="USD",
            trm=None,
        )
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id, trm_provider=FakeTrm(Decimal("3900")))
        assert status is DocumentStatus.POSTED

        move = next(iter(odoo.moves.values()))
        base = _line_by_account(move, 1)
        assert base["debit"] == 3900000000.00
        _assert_move_balanced(move)


# --- Fase B: ventas y notas ---


def _add_taxes(session: Session, tenant_id: uuid.UUID, doc_id: uuid.UUID) -> None:
    """Agrega IVA + Retefuente + ReteICA de una base de 1.000.000 (retencion total 34.660)."""
    filas = [
        (TaxCategory.IVA, False, "IVA", "19.00", "190000.00"),
        (TaxCategory.RETEFUENTE, True, "Retefuente", "2.50", "25000.00"),
        (TaxCategory.RETEICA, True, "ReteICA", "0.966", "9660.00"),
    ]
    for category, withholding, name, percent, amount in filas:
        session.add(
            DocumentTax(
                tenant_id=tenant_id,
                document_id=doc_id,
                category=category,
                is_withholding=withholding,
                tax_name=name,
                percent=Decimal(percent),
                taxable_amount=Decimal("1000000.00"),
                tax_amount=Decimal(amount),
            )
        )


def _seed_doc(
    session: Session,
    *,
    doc_type: DocType,
    config: dict[str, Any],
    company_nit: str,
    issuer_nit: str,
    receiver_nit: str,
    proposed: str,
    currency: str = "COP",
    trm: Decimal | None = None,
) -> uuid.UUID:
    tenant = Tenant(name="Firma Post")
    session.add(tenant)
    session.flush()
    company = Company(tenant_id=tenant.id, name="Empresa", nit=company_nit, posting_config=config)
    session.add(company)
    session.flush()
    doc = SourceDocument(
        tenant_id=tenant.id,
        company_id=company.id,
        status=DocumentStatus.CLASSIFIED,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        cufe=f"CUFE-{uuid.uuid4().hex}",
        doc_type=doc_type,
        issuer_nit=issuer_nit,
        issuer_name="Contraparte SAS",
        receiver_nit=receiver_nit,
        currency=currency,
        trm=trm,
        subtotal=Decimal("1000000.00"),
        total_tax=Decimal("190000.00"),
        total_withholding=Decimal("34660.00"),
        total=Decimal("1155340.00"),
        proposed_account_code=proposed,
    )
    session.add(doc)
    session.flush()
    _add_taxes(session, tenant.id, doc.id)
    session.commit()
    return doc.id


class FakeTrm:
    """Proveedor de TRM inyectable para tests."""

    def __init__(self, rate: Decimal | None) -> None:
        self.rate = rate

    def rate_for(self, currency: str, on_date: object) -> Decimal | None:
        return self.rate


def _line_by_account(move: dict[str, Any], account_id: int) -> dict[str, Any]:
    for _cmd, _zero, vals in move["line_ids"]:
        if vals["account_id"] == account_id:
            return vals  # type: ignore[no-any-return]
    raise AssertionError(f"no hay linea con account_id={account_id}")


def _assert_move_balanced(move: dict[str, Any]) -> None:
    debit = sum(vals["debit"] for _cmd, _zero, vals in move["line_ids"])
    credit = sum(vals["credit"] for _cmd, _zero, vals in move["line_ids"])
    assert round(debit, 2) == round(credit, 2)


def test_post_venta_ok(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(
            session,
            doc_type=DocType.FACTURA_VENTA,
            config=SALE_CONFIG,
            company_nit="900555111",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="413595",
        )
        odoo = FakeOdoo(SALE_KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTED
        assert len(odoo.posted) == 1

        move = next(iter(odoo.moves.values()))
        assert move["journal_id"] == 12  # diario de ventas
        # CxC (130505 -> 24) es debito y vale el total: 1.000.000 + 190.000 - 34.660.
        cxc = _line_by_account(move, 24)
        assert cxc["debit"] == 1155340.00
        assert cxc["credit"] == 0.0
        # IVA generado (240805 -> 21) es credito.
        iva = _line_by_account(move, 21)
        assert iva["credit"] == 190000.00
        assert iva["debit"] == 0.0
        _assert_move_balanced(move)


def test_post_nota_credito_compra_invierte(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        # La empresa es el receptor (adquiriente) -> nota del lado compra.
        doc_id = _seed_doc(
            session,
            doc_type=DocType.NOTA_CREDITO,
            config=POSTING_CONFIG,
            company_nit="800111222",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="511595",
        )
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTED

        move = next(iter(odoo.moves.values()))
        assert move["journal_id"] == 11  # lado compra
        # En una compra normal CxP (220505 -> 5) es credito; la nota credito lo invierte.
        cxp = _line_by_account(move, 5)
        assert cxp["debit"] > 0
        assert cxp["credit"] == 0.0
        _assert_move_balanced(move)


def test_nota_perspectiva_indeterminada_falla(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        # El NIT de la empresa no coincide con emisor ni receptor: no se sabe el lado.
        doc_id = _seed_doc(
            session,
            doc_type=DocType.NOTA_DEBITO,
            config=POSTING_CONFIG,
            company_nit="700000000",
            issuer_nit="900555111",
            receiver_nit="800111222",
            proposed="511595",
        )
        odoo = FakeOdoo(KNOWN_ACCOUNTS)

        status = post_document(session, odoo, doc_id)
        assert status is DocumentStatus.POSTING_FAILED
