"""Tests de integracion del pipeline de ingesta (Entrega 4).

Usan una PostgreSQL efimera (fixture pg_engine) y dobles en memoria de Mailbox y
RawStorage. Verifican: creacion en RECEIVED + parseo a PARSED, idempotencia total,
fallo de parseo -> PARSE_FAILED, y CUFE duplicado -> REJECTED.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.ingestion.pipeline import (
    ingest_attachment,
    parse_source_document,
    process_mailbox,
)
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import DocType, DocumentEventType, DocumentStatus
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant

FIXTURES = Path(__file__).parent.parent / "fixtures" / "xml"


class FakeStorage:
    """RawStorage en memoria."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_raw(self, company_id: str, sha256: str, filename: str, data: bytes) -> str:
        uri = f"mem://{company_id}/{sha256}/{filename}"
        self.objects[uri] = data
        return uri

    def get_raw(self, uri: str) -> bytes:
        return self.objects[uri]


class FakeMailbox:
    """Mailbox en memoria. Cada correo es (uid, bytes RFC822)."""

    def __init__(self, emails: list[tuple[str, bytes]]) -> None:
        self._emails = dict(emails)
        self._unseen = [uid for uid, _ in emails]
        self.seen: list[str] = []

    def search_unseen(self) -> list[str]:
        return list(self._unseen)

    def fetch(self, uid: str) -> bytes:
        return self._emails[uid]

    def mark_seen(self, uid: str) -> None:
        if uid in self._unseen:
            self._unseen.remove(uid)
        self.seen.append(uid)

    def close(self) -> None:
        pass


def _email_with_xml(xml_bytes: bytes, filename: str = "factura.xml") -> bytes:
    msg = EmailMessage()
    msg["From"] = "proveedor@ejemplo.co"
    msg["To"] = "empresa@ejemplo.co"
    msg["Subject"] = "Factura"
    msg.set_content("Adjunta")
    msg.add_attachment(xml_bytes, maintype="application", subtype="xml", filename=filename)
    return msg.as_bytes()


def _seed_company(session: Session) -> Company:
    tenant = Tenant(name="Firma Ingesta")
    session.add(tenant)
    session.flush()
    company = Company(
        tenant_id=tenant.id,
        name="Empresa Ingesta",
        nit=f"900{uuid.uuid4().hex[:9]}",
    )
    session.add(company)
    session.flush()
    return company


def _seed_company_nit(session: Session, nit: str) -> Company:
    tenant = Tenant(name=f"Firma {nit}")
    session.add(tenant)
    session.flush()
    company = Company(tenant_id=tenant.id, name="Empresa", nit=nit)
    session.add(company)
    session.flush()
    return company


def _count_docs(session: Session, company: Company) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(SourceDocument)
            .where(SourceDocument.company_id == company.id)
        )
        or 0
    )


def test_flujo_completo_received_y_parsed(pg_engine: Engine) -> None:
    xml = (FIXTURES / "factura_simple.xml").read_bytes()
    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()
        mailbox = FakeMailbox([("101", _email_with_xml(xml))])
        enqueued: list[uuid.UUID] = []

        created = process_mailbox(session, storage, mailbox, company, enqueued.append)

        assert len(created) == 1
        assert enqueued == created
        assert mailbox.seen == ["101"]  # marcado leido tras persistir

        doc = session.get(SourceDocument, created[0])
        assert doc is not None
        assert doc.status is DocumentStatus.RECEIVED
        assert doc.cufe is None  # aun no parseado
        assert doc.raw_sha256

        status = parse_source_document(session, storage, created[0])
        assert status is DocumentStatus.PARSED

        session.refresh(doc)
        assert doc.status is DocumentStatus.PARSED
        assert doc.cufe is not None
        assert doc.total is not None

        event_types = set(
            session.scalars(
                select(DocumentEvent.event_type).where(DocumentEvent.document_id == doc.id)
            )
        )
        assert DocumentEventType.RECEIVED in event_types
        assert DocumentEventType.PARSED in event_types


def test_idempotencia_mismo_xml_no_duplica(pg_engine: Engine) -> None:
    xml = (FIXTURES / "factura_simple.xml").read_bytes()
    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()

        first = ingest_attachment(session, storage, company, "factura.xml", xml)
        second = ingest_attachment(session, storage, company, "factura.xml", xml)

        assert first is not None
        assert second is None  # dedupe por (company, sha)
        assert _count_docs(session, company) == 1


def test_procesar_buzon_dos_veces_no_duplica(pg_engine: Engine) -> None:
    xml = (FIXTURES / "factura_simple.xml").read_bytes()
    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()

        # Mismo correo "no leido" en dos corridas (simula reejecucion de la tarea).
        mailbox1 = FakeMailbox([("201", _email_with_xml(xml))])
        mailbox2 = FakeMailbox([("201", _email_with_xml(xml))])

        created1 = process_mailbox(session, storage, mailbox1, company, lambda _id: None)
        created2 = process_mailbox(session, storage, mailbox2, company, lambda _id: None)

        assert len(created1) == 1
        assert created2 == []  # el sha ya existe
        assert _count_docs(session, company) == 1


def test_xml_corrupto_marca_parse_failed(pg_engine: Engine) -> None:
    xml = (FIXTURES / "corrupto.xml").read_bytes()
    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()

        doc_id = ingest_attachment(session, storage, company, "corrupto.xml", xml)
        assert doc_id is not None

        status = parse_source_document(session, storage, doc_id)
        assert status is DocumentStatus.PARSE_FAILED

        failed = session.scalars(
            select(DocumentEvent.event_type).where(DocumentEvent.document_id == doc_id)
        )
        assert DocumentEventType.PARSE_FAILED in set(failed)


def test_cufe_duplicado_marca_rejected(pg_engine: Engine) -> None:
    original = (FIXTURES / "factura_simple.xml").read_bytes()
    # Variante con los mismos datos (mismo CUFE) pero distintos bytes (distinto sha).
    variante = original.replace(b"Servicio de consultoria", b"Servicio de consultoria (copia)")
    assert variante != original

    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()

        id_a = ingest_attachment(session, storage, company, "a.xml", original)
        id_b = ingest_attachment(session, storage, company, "b.xml", variante)
        assert id_a is not None
        assert id_b is not None
        assert id_a != id_b

        assert parse_source_document(session, storage, id_a) is DocumentStatus.PARSED
        assert parse_source_document(session, storage, id_b) is DocumentStatus.REJECTED


def test_perspectiva_compra_y_persistencia_detalle(pg_engine: Engine) -> None:
    xml = (FIXTURES / "factura_con_retenciones.xml").read_bytes()
    with Session(pg_engine) as session:
        # La empresa es el ADQUIRIENTE (receiver_nit del XML) -> es una compra.
        company = _seed_company_nit(session, "800987654")
        storage = FakeStorage()

        doc_id = ingest_attachment(session, storage, company, "f.xml", xml)
        assert doc_id is not None
        assert parse_source_document(session, storage, doc_id) is DocumentStatus.PARSED

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.doc_type is DocType.FACTURA_COMPRA
        assert doc.receiver_nit == "800987654"
        assert doc.total_tax == Decimal("190000.00")
        assert doc.total_withholding == Decimal("34660.00")

        n_tax = session.scalar(
            select(func.count()).select_from(DocumentTax).where(DocumentTax.document_id == doc_id)
        )
        n_line = session.scalar(
            select(func.count()).select_from(DocumentLine).where(DocumentLine.document_id == doc_id)
        )
        assert n_tax == 3  # IVA + Retefuente + ReteICA
        assert n_line == 1


def test_perspectiva_venta(pg_engine: Engine) -> None:
    xml = (FIXTURES / "factura_con_retenciones.xml").read_bytes()
    with Session(pg_engine) as session:
        # La empresa es el EMISOR (issuer_nit del XML) -> es una venta.
        company = _seed_company_nit(session, "900555111")
        storage = FakeStorage()

        doc_id = ingest_attachment(session, storage, company, "f.xml", xml)
        assert doc_id is not None
        assert parse_source_document(session, storage, doc_id) is DocumentStatus.PARSED

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.doc_type is DocType.FACTURA_VENTA
