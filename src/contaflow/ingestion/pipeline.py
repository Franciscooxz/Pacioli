"""Pipeline de ingesta (logica de dominio, sin Celery/IMAP/MinIO reales).

Se separa de las tareas Celery para poder probarla inyectando dobles de Mailbox y
RawStorage. Las tareas (workers/tasks.py) son envoltorios delgados sobre estas
funciones.

Idempotencia:
- pre-parseo: (company_id, raw_sha256) UNIQUE evita ingestar el mismo XML dos veces.
- final: cufe UNIQUE evita dos documentos parseados con el mismo CUFE.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contaflow.core.dead_letter import record_failure
from contaflow.core.exceptions import IngestionError, UblParseError
from contaflow.core.nit import same_nit
from contaflow.ingestion.imap_reader import Mailbox, extract_xml_attachments
from contaflow.ingestion.signature import verify_xades
from contaflow.ingestion.storage import RawStorage
from contaflow.ingestion.ubl_parser import parse_ubl
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import (
    ActorType,
    DocType,
    DocumentEventType,
    DocumentStatus,
    FailureStage,
)
from contaflow.models.source_document import SourceDocument
from contaflow.schemas.ubl import ParsedDocument

logger = logging.getLogger(__name__)


def _resolve_doc_type(parsed: ParsedDocument, company_nit: str) -> tuple[DocType, str | None]:
    """Decide compra/venta segun quien es la empresa frente al documento.

    Solo reinterpreta las facturas (el parser las devuelve como FACTURA_VENTA por ser la
    naturaleza del <Invoice>). Las notas/documento soporte se dejan como vienen.
    """
    if parsed.doc_type is not DocType.FACTURA_VENTA:
        return parsed.doc_type, None
    if same_nit(parsed.receiver_nit, company_nit):
        return DocType.FACTURA_COMPRA, None
    if same_nit(parsed.issuer_nit, company_nit):
        return DocType.FACTURA_VENTA, None
    return DocType.FACTURA_VENTA, "perspectiva_indeterminada: el NIT de la empresa no coincide"


def _event(
    company: Company,
    document_id: uuid.UUID,
    event_type: DocumentEventType,
    payload: dict[str, object] | None = None,
) -> DocumentEvent:
    return DocumentEvent(
        tenant_id=company.tenant_id,
        document_id=document_id,
        event_type=event_type,
        actor_type=ActorType.SYSTEM,
        payload=payload,
    )


def ingest_attachment(
    session: Session,
    storage: RawStorage,
    company: Company,
    filename: str,
    xml_bytes: bytes,
    source_ref: str | None = None,
) -> uuid.UUID | None:
    """Guarda el crudo y crea el source_document en RECEIVED. None si ya existia."""
    sha = hashlib.sha256(xml_bytes).hexdigest()

    already = session.scalar(
        select(SourceDocument.id).where(
            SourceDocument.company_id == company.id,
            SourceDocument.raw_sha256 == sha,
        )
    )
    if already is not None:
        logger.info("adjunto ya ingestado (company=%s sha=%s), se omite", company.id, sha[:12])
        return None

    # El crudo se guarda SIEMPRE antes de parsear (evidencia DIAN).
    uri = storage.put_raw(str(company.id), sha, filename, xml_bytes)

    doc = SourceDocument(
        tenant_id=company.tenant_id,
        company_id=company.id,
        status=DocumentStatus.RECEIVED,
        raw_xml_uri=uri,
        raw_sha256=sha,
        source_ref=source_ref,
    )
    session.add(doc)
    try:
        session.flush()
    except IntegrityError:
        # Carrera: otro worker inserto el mismo (company, sha) primero.
        session.rollback()
        logger.info("adjunto ingestado en paralelo (company=%s), se omite", company.id)
        return None

    session.add(_event(company, doc.id, DocumentEventType.RECEIVED, {"sha256": sha}))
    session.commit()
    return doc.id


def process_mailbox(
    session: Session,
    storage: RawStorage,
    mailbox: Mailbox,
    company: Company,
    enqueue_parse: Callable[[uuid.UUID], None],
) -> list[uuid.UUID]:
    """Recorre los correos no leidos de una empresa e ingesta sus adjuntos XML."""
    created: list[uuid.UUID] = []
    for uid in mailbox.search_unseen():
        raw_email = mailbox.fetch(uid)
        try:
            attachments = extract_xml_attachments(raw_email)
        except IngestionError as exc:
            # Correo roto o malicioso (p. ej. zip bomb): no reprocesar en bucle, pero
            # guardar el crudo y dejar constancia en la cola de fallidos (dead-letter)
            # para poder inspeccionarlo despues, en vez de perderlo en los logs.
            logger.warning("correo uid=%s descartado en extraccion: %s", uid, type(exc).__name__)
            raw_uri: str | None = None
            try:
                sha = hashlib.sha256(raw_email).hexdigest()
                raw_uri = storage.put_raw(str(company.id), sha, f"correo-{uid}.eml", raw_email)
            except Exception:  # noqa: BLE001 - guardar el crudo es best-effort
                logger.warning("no se pudo guardar el crudo del correo uid=%s", uid)
            record_failure(
                session,
                stage=FailureStage.MAIL_EXTRACTION,
                reason=f"{type(exc).__name__}: {exc}",
                tenant_id=company.tenant_id,
                company_id=company.id,
                source_ref=uid,
                raw_uri=raw_uri,
            )
            mailbox.mark_seen(uid)
            continue

        ids_email: list[uuid.UUID] = []
        for filename, xml_bytes in attachments:
            doc_id = ingest_attachment(session, storage, company, filename, xml_bytes, uid)
            if doc_id is not None:
                ids_email.append(doc_id)

        # Marcar leido SOLO despues de persistir los adjuntos del correo.
        mailbox.mark_seen(uid)
        for doc_id in ids_email:
            enqueue_parse(doc_id)
        created.extend(ids_email)
    return created


def parse_source_document(
    session: Session, storage: RawStorage, document_id: uuid.UUID
) -> DocumentStatus:
    """Parsea un source_document en RECEIVED y actualiza su estado. Idempotente."""
    doc = session.get(SourceDocument, document_id)
    if doc is None:
        raise IngestionError(f"source_document inexistente: {document_id}")

    company = session.get(Company, doc.company_id)
    if company is None:
        raise IngestionError(f"company inexistente para el documento {document_id}")

    if doc.status is not DocumentStatus.RECEIVED:
        return doc.status  # ya procesado; no repetir

    raw = storage.get_raw(doc.raw_xml_uri)

    try:
        parsed = parse_ubl(raw)
    except UblParseError as exc:
        doc.status = DocumentStatus.PARSE_FAILED
        session.add(
            _event(
                company,
                doc.id,
                DocumentEventType.PARSE_FAILED,
                {"error_type": type(exc).__name__, "message": str(exc)[:200]},
            )
        )
        session.commit()
        logger.info("documento %s -> PARSE_FAILED (%s)", doc.id, type(exc).__name__)
        return doc.status

    # Conflicto de CUFE: la misma factura ya entro por otra via -> duplicado.
    conflict = session.scalar(
        select(SourceDocument.id).where(
            SourceDocument.cufe == parsed.cufe,
            SourceDocument.id != doc.id,
        )
    )
    if conflict is not None:
        doc.status = DocumentStatus.REJECTED
        session.add(
            _event(company, doc.id, DocumentEventType.REJECTED, {"reason": "cufe_duplicado"})
        )
        session.commit()
        logger.info("documento %s -> REJECTED (cufe duplicado)", doc.id)
        return doc.status

    doc_type, perspective_warning = _resolve_doc_type(parsed, company.nit)
    doc.cufe = parsed.cufe
    doc.doc_type = doc_type
    doc.document_number = parsed.document_number
    doc.issuer_nit = parsed.issuer_nit
    doc.issuer_name = parsed.issuer_name
    doc.receiver_nit = parsed.receiver_nit
    doc.issue_date = parsed.issue_date
    doc.currency = parsed.currency
    doc.trm = parsed.exchange_rate
    doc.subtotal = parsed.subtotal
    doc.total_tax = parsed.total_tax
    doc.total_withholding = parsed.total_withholding
    doc.total = parsed.total
    doc.status = DocumentStatus.PARSED

    # Persistir el detalle (lineas e impuestos/retenciones).
    for line in parsed.lines:
        session.add(
            DocumentLine(
                tenant_id=company.tenant_id,
                document_id=doc.id,
                line_id=line.line_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            )
        )
    for tax in parsed.taxes:
        session.add(
            DocumentTax(
                tenant_id=company.tenant_id,
                document_id=doc.id,
                category=tax.category,
                is_withholding=tax.is_withholding,
                tax_name=tax.tax_name,
                percent=tax.percent,
                taxable_amount=tax.taxable_amount,
                tax_amount=tax.tax_amount,
                municipality=tax.municipality,
            )
        )

    # Validacion de firma (integridad). present=False -> None (sin firma / no verificada).
    sig = verify_xades(raw)
    doc.signature_valid = sig.valid if sig.present else None

    warnings = list(parsed.warnings)
    if perspective_warning:
        warnings.append(perspective_warning)
    if sig.present and not sig.valid:
        detail = sig.errors[0] if sig.errors else "verificacion fallida"
        warnings.append(f"Firma digital invalida: {detail}")
    session.add(
        _event(
            company,
            doc.id,
            DocumentEventType.PARSED,
            {
                "warnings": warnings,
                "doc_type": doc_type.value,
                "total": str(parsed.total),
                "signature": {"present": sig.present, "valid": sig.valid, "signer": sig.signer},
            },
        )
    )
    try:
        session.commit()
    except IntegrityError:
        # Carrera con otro documento del mismo CUFE.
        session.rollback()
        doc = session.get(SourceDocument, document_id)
        if doc is not None:
            doc.status = DocumentStatus.REJECTED
            session.add(
                _event(company, doc.id, DocumentEventType.REJECTED, {"reason": "cufe_duplicado"})
            )
            session.commit()
            return doc.status
        return DocumentStatus.REJECTED

    logger.info("documento %s -> PARSED", doc.id)
    return doc.status
