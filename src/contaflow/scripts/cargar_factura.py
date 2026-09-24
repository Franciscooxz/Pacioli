"""Carga manual de una factura de prueba (sin IMAP).

Ejercita el pipeline real (MinIO + BD + parser) contra una empresa demo. Util para
ver el flujo de ingesta de punta a punta sin configurar un buzon de correo.

Uso (dentro del contenedor):
    python -m contaflow.scripts.cargar_factura tests/fixtures/xml/factura_simple.xml
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.db import SyncSessionLocal
from contaflow.ingestion.pipeline import ingest_attachment, parse_source_document
from contaflow.ingestion.storage import MinioStorage
from contaflow.models.company import Company
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant

DEMO_NIT = "900000000"


def _get_or_create_demo_company(session: Session) -> Company:
    company = session.scalar(select(Company).where(Company.nit == DEMO_NIT))
    if company is not None:
        return company
    tenant = session.scalar(select(Tenant).where(Tenant.name == "Firma Demo"))
    if tenant is None:
        tenant = Tenant(name="Firma Demo")
        session.add(tenant)
        session.flush()
    company = Company(tenant_id=tenant.id, name="Empresa Demo", nit=DEMO_NIT)
    session.add(company)
    session.commit()
    return company


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: python -m contaflow.scripts.cargar_factura <ruta_xml>")
        return 2

    path = Path(argv[1])
    xml = path.read_bytes()
    storage = MinioStorage()

    with SyncSessionLocal() as session:
        company = _get_or_create_demo_company(session)
        doc_id = ingest_attachment(session, storage, company, path.name, xml, source_ref="cli")
        if doc_id is None:
            sha = hashlib.sha256(xml).hexdigest()
            doc_id = session.scalar(
                select(SourceDocument.id).where(
                    SourceDocument.company_id == company.id,
                    SourceDocument.raw_sha256 == sha,
                )
            )
            print("Documento ya ingestado antes (idempotencia).")
        assert doc_id is not None

        status = parse_source_document(session, storage, doc_id)
        doc = session.get(SourceDocument, doc_id)
        assert doc is not None

        print(f"Documento {doc_id}")
        print(f"  estado : {status.value}")
        print(f"  cufe   : {doc.cufe}")
        print(f"  emisor : {doc.issuer_nit}")
        print(f"  total  : {doc.total}")
        if doc.doc_type is not None:
            print(f"  tipo   : {doc.doc_type.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
