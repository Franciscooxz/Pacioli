"""Tests del resumen de notificaciones in-app, con aislamiento multi-tenant."""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from draxia.core.auth import hash_password
from draxia.models.company import Company
from draxia.models.enums import DocType, DocumentStatus, FailureStage, UserRole
from draxia.models.ingestion_failure import IngestionFailure
from draxia.models.source_document import SourceDocument
from draxia.models.tenant import Tenant
from draxia.models.user import User

PASSWORD = "secreto-123"


def _seed_user_company(session: Session, email: str, firma: str) -> tuple[User, Company]:
    tenant = Tenant(name=firma)
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id, email=email, password_hash=hash_password(PASSWORD), role=UserRole.ADMIN
    )
    company = Company(tenant_id=tenant.id, name="Empresa", nit=f"900{uuid.uuid4().hex[:9]}")
    session.add_all([user, company])
    session.commit()
    return user, company


def _doc(
    session: Session,
    company: Company,
    status: DocumentStatus,
    assigned_user_id: uuid.UUID | None = None,
) -> None:
    session.add(
        SourceDocument(
            tenant_id=company.tenant_id,
            company_id=company.id,
            status=status,
            raw_xml_uri="mem://x",
            raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            doc_type=DocType.FACTURA_COMPRA,
            total=Decimal("1000.00"),
            assigned_user_id=assigned_user_id,
        )
    )


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_resumen_de_notificaciones(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        user, company = _seed_user_company(session, "nt@f.co", "Firma NT")
        # 2 por revisar; 1 de ellos asignado al usuario. 1 clasificado asignado (cuenta en "mios").
        _doc(session, company, DocumentStatus.PENDING_REVIEW)
        _doc(session, company, DocumentStatus.PENDING_REVIEW, assigned_user_id=user.id)
        _doc(session, company, DocumentStatus.CLASSIFIED, assigned_user_id=user.id)
        _doc(session, company, DocumentStatus.POSTED)  # no cuenta
        session.add(
            IngestionFailure(
                tenant_id=company.tenant_id,
                company_id=company.id,
                stage=FailureStage.PARSE,
                reason="xml roto",
            )
        )
        session.commit()

    headers = await _login(api_client, "nt@f.co")
    resp = await api_client.get("/notifications/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_review"] == 2
    assert data["assigned_to_me"] == 2  # uno PENDING_REVIEW + uno CLASSIFIED
    assert data["failures"] == 1


async def test_notificaciones_aisladas_por_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "na@f.co", "Firma NA")
        _doc(session, company_a, DocumentStatus.PENDING_REVIEW)
        # Tenant B sin nada.
        _seed_user_company(session, "nb@f.co", "Firma NB")
        session.commit()

    headers_b = await _login(api_client, "nb@f.co")
    resp = await api_client.get("/notifications/summary", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == {"pending_review": 0, "assigned_to_me": 0, "failures": 0}
