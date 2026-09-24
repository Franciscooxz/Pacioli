"""Tests de integracion del modelo de datos (Entrega 2).

Verifican garantias que viven en la base, no en la app:
- CUFE unico a nivel de base (idempotencia).
- document_event es append-only (trigger rechaza UPDATE y DELETE).
- los Decimal sobreviven el round-trip sin perder precision.
- las credenciales se guardan cifradas (nunca texto plano) y se descifran al leer.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from contaflow.models import (
    Company,
    DocumentEvent,
    SourceDocument,
    Tenant,
)
from contaflow.models.enums import ActorType, DocType, DocumentEventType, DocumentStatus


def _seed_tenant_company(session: Session) -> tuple[Tenant, Company]:
    """Crea un tenant y una company nuevos (nit unico) para aislar cada test."""
    tenant = Tenant(name="Firma Contable de Prueba")
    session.add(tenant)
    session.flush()
    company = Company(
        tenant_id=tenant.id,
        name="Empresa Cliente",
        nit=f"900{uuid.uuid4().hex[:9]}",
    )
    session.add(company)
    session.flush()
    return tenant, company


def _new_document(tenant: Tenant, company: Company, cufe: str, total: str) -> SourceDocument:
    return SourceDocument(
        tenant_id=tenant.id,
        company_id=company.id,
        cufe=cufe,
        doc_type=DocType.FACTURA_COMPRA,
        document_number="FE-001",
        issuer_nit="800197268",
        issue_date=date(2026, 1, 15),
        total=Decimal(total),
        raw_xml_uri="minio://contaflow-raw/x.xml",
        raw_sha256=(uuid.uuid4().hex + uuid.uuid4().hex),  # 64 chars, unico por doc
        status=DocumentStatus.RECEIVED,
    )


def test_cufe_duplicado_falla(pg_engine: Engine) -> None:
    cufe = f"CUFE-{uuid.uuid4().hex}"
    with Session(pg_engine) as session:
        tenant, company = _seed_tenant_company(session)
        session.add(_new_document(tenant, company, cufe, "100.00"))
        session.commit()

        session.add(_new_document(tenant, company, cufe, "200.00"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_document_event_no_permite_update(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tenant, company = _seed_tenant_company(session)
        doc = _new_document(tenant, company, f"CUFE-{uuid.uuid4().hex}", "100.00")
        session.add(doc)
        session.flush()
        event = DocumentEvent(
            tenant_id=tenant.id,
            document_id=doc.id,
            event_type=DocumentEventType.RECEIVED,
            actor_type=ActorType.SYSTEM,
        )
        session.add(event)
        session.commit()
        event_id = event.id

    with Session(pg_engine) as session, pytest.raises(DBAPIError):
        session.execute(
            update(DocumentEvent).where(DocumentEvent.id == event_id).values(actor_id="alguien")
        )
        session.commit()


def test_document_event_no_permite_delete(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tenant, company = _seed_tenant_company(session)
        doc = _new_document(tenant, company, f"CUFE-{uuid.uuid4().hex}", "100.00")
        session.add(doc)
        session.flush()
        event = DocumentEvent(
            tenant_id=tenant.id,
            document_id=doc.id,
            event_type=DocumentEventType.RECEIVED,
            actor_type=ActorType.SYSTEM,
        )
        session.add(event)
        session.commit()
        event_id = event.id

    with Session(pg_engine) as session, pytest.raises(DBAPIError):
        session.execute(delete(DocumentEvent).where(DocumentEvent.id == event_id))
        session.commit()


def test_decimal_round_trip_sin_perder_precision(pg_engine: Engine) -> None:
    # 18 digitos enteros no caben en NUMERIC(19,2); usamos 16 enteros + 2 decimales.
    total = Decimal("1234567890123456.78")
    doc_id: uuid.UUID
    with Session(pg_engine) as session:
        tenant, company = _seed_tenant_company(session)
        doc = _new_document(tenant, company, f"CUFE-{uuid.uuid4().hex}", str(total))
        session.add(doc)
        session.commit()
        doc_id = doc.id

    with Session(pg_engine) as session:
        reloaded = session.get(SourceDocument, doc_id)
        assert reloaded is not None
        assert isinstance(reloaded.total, Decimal)
        assert reloaded.total == total


def test_total_negativo_rechazado(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tenant, company = _seed_tenant_company(session)
        session.add(_new_document(tenant, company, f"CUFE-{uuid.uuid4().hex}", "-1.00"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_credenciales_se_guardan_cifradas(pg_engine: Engine) -> None:
    secreto = "sup3r-s3creto-odoo"
    company_id: uuid.UUID
    with Session(pg_engine) as session:
        tenant = Tenant(name="Firma con creds")
        session.add(tenant)
        session.flush()
        company = Company(
            tenant_id=tenant.id,
            name="Empresa con Odoo",
            nit=f"901{uuid.uuid4().hex[:9]}",
            odoo_password=secreto,
        )
        session.add(company)
        session.commit()
        company_id = company.id

    # A nivel de base, la columna es bytes y NO contiene el texto plano.
    with Session(pg_engine) as session:
        raw = session.execute(
            text("SELECT odoo_password FROM company WHERE id = :id"),
            {"id": company_id},
        ).scalar_one()
        assert raw is not None
        assert secreto.encode("utf-8") not in bytes(raw)

    # Al leer via ORM se descifra de forma transparente.
    with Session(pg_engine) as session:
        reloaded = session.get(Company, company_id)
        assert reloaded is not None
        assert reloaded.odoo_password == secreto
