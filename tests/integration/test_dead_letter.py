"""Tests de la cola de fallidos (dead-letter, Fase A).

Cubren los dos niveles de fallo terminal:
- correo que no se puede abrir (zip bomb) -> process_mailbox lo manda a la cola,
  guarda el crudo y lo marca leido para no reprocesarlo en bucle.
- registro por documento -> record_failure deja la fila con el contexto resuelto.

Usan una PostgreSQL efimera (fixture pg_engine) y dobles en memoria de Mailbox/Storage.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.dead_letter import record_failure, resolve_document_context
from contaflow.ingestion.imap_reader import MAX_ZIP_ENTRIES
from contaflow.ingestion.pipeline import process_mailbox
from contaflow.models.company import Company
from contaflow.models.enums import DocumentStatus, FailureStage
from contaflow.models.ingestion_failure import IngestionFailure
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant


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


def _seed_company(session: Session) -> Company:
    tenant = Tenant(name="Firma DeadLetter")
    session.add(tenant)
    session.flush()
    company = Company(
        tenant_id=tenant.id,
        name="Empresa DeadLetter",
        nit=f"900{uuid.uuid4().hex[:9]}",
    )
    session.add(company)
    session.flush()
    return company


def _zip_bomb_email() -> bytes:
    """Correo con un ZIP de demasiadas entradas: extract_xml_attachments lo rechaza."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for i in range(MAX_ZIP_ENTRIES + 1):
            archive.writestr(f"f{i}.xml", b"<x/>")
    msg = EmailMessage()
    msg["From"] = "proveedor@ejemplo.co"
    msg["To"] = "empresa@ejemplo.co"
    msg["Subject"] = "Factura"
    msg.set_content("Adjunta")
    msg.add_attachment(
        buf.getvalue(), maintype="application", subtype="zip", filename="facturas.zip"
    )
    return msg.as_bytes()


def test_correo_roto_va_a_dead_letter(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        storage = FakeStorage()
        mailbox = FakeMailbox([("301", _zip_bomb_email())])

        created = process_mailbox(session, storage, mailbox, company, lambda _id: None)

        assert created == []  # ningun documento creado
        assert mailbox.seen == ["301"]  # marcado leido: no se reprocesa en bucle

        failures = list(
            session.scalars(
                select(IngestionFailure).where(IngestionFailure.company_id == company.id)
            )
        )
        assert len(failures) == 1
        failure = failures[0]
        assert failure.stage is FailureStage.MAIL_EXTRACTION
        assert failure.source_ref == "301"
        assert failure.tenant_id == company.tenant_id
        assert failure.resolved_at is None
        assert "ZipBomb" in failure.reason
        # El crudo del correo quedo guardado para inspeccion.
        assert failure.raw_uri is not None
        assert storage.get_raw(failure.raw_uri)


def test_record_failure_por_documento(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        doc = SourceDocument(
            tenant_id=company.tenant_id,
            company_id=company.id,
            status=DocumentStatus.RECEIVED,
            raw_xml_uri="s3://bucket/key",
            raw_sha256="abc123",
        )
        session.add(doc)
        session.commit()

        # El contexto (tenant, company) se resuelve a partir del documento.
        tenant_id, company_id = resolve_document_context(session, doc.id)
        assert tenant_id == company.tenant_id
        assert company_id == company.id

        failure_id = record_failure(
            session,
            stage=FailureStage.PARSE,
            reason="OSError: infra caida",
            tenant_id=tenant_id,
            company_id=company_id,
            document_id=doc.id,
            task_name="contaflow.workers.tasks.parse_document",
            source_ref="task-123",
        )

        failure = session.get(IngestionFailure, failure_id)
        assert failure is not None
        assert failure.document_id == doc.id
        assert failure.company_id == company.id
        assert failure.stage is FailureStage.PARSE
        assert failure.resolved_at is None


def test_resolve_document_context_inexistente(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tenant_id, company_id = resolve_document_context(session, uuid.uuid4())
        assert tenant_id is None
        assert company_id is None
