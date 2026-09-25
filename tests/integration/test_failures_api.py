"""Tests del endpoint /failures (dead-letter): listar, filtrar, resolver, multi-tenant."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.company import Company
from contaflow.models.enums import FailureStage, UserRole
from contaflow.models.ingestion_failure import IngestionFailure
from contaflow.models.tenant import Tenant
from contaflow.models.user import User

PASSWORD = "secreto-123"


def _seed_user_company(session: Session, email: str, firma: str) -> Company:
    tenant = Tenant(name=firma)
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id, email=email, password_hash=hash_password(PASSWORD), role=UserRole.ADMIN
    )
    company = Company(tenant_id=tenant.id, name="Empresa", nit=f"900{uuid.uuid4().hex[:9]}")
    session.add_all([user, company])
    session.commit()
    return company


def _seed_failure(session: Session, tenant_id: uuid.UUID, company_id: uuid.UUID) -> uuid.UUID:
    failure = IngestionFailure(
        tenant_id=tenant_id,
        company_id=company_id,
        stage=FailureStage.PARSE,
        reason="OSError: infra caida",
    )
    session.add(failure)
    session.commit()
    return failure.id


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_listar_filtrar_y_resolver(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_user_company(session, "fa@f.co", "Firma FA")
        failure_id = _seed_failure(session, company.tenant_id, company.id)

    headers = await _login(api_client, "fa@f.co")

    data = (await api_client.get("/failures", headers=headers)).json()
    assert len(data) == 1
    assert data[0]["stage"] == "PARSE"
    assert data[0]["resolved_at"] is None

    pend = (await api_client.get("/failures?resolved=false", headers=headers)).json()
    assert len(pend) == 1

    resp = await api_client.post(f"/failures/{failure_id}/resolve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["resolved_at"] is not None

    pend2 = (await api_client.get("/failures?resolved=false", headers=headers)).json()
    assert pend2 == []


async def test_failures_aisladas_por_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        company_a = _seed_user_company(session, "fb@f.co", "Firma FB")
        _seed_user_company(session, "fc@f.co", "Firma FC")
        _seed_failure(session, company_a.tenant_id, company_a.id)

    headers_c = await _login(api_client, "fc@f.co")
    assert (await api_client.get("/failures", headers=headers_c)).json() == []
