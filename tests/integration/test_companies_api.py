"""Tests del endpoint /companies: solo lectura, sin credenciales, multi-tenant."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.company import Company
from contaflow.models.enums import UserRole
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


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_listar_companies_sin_credenciales(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        company = _seed_user_company(session, "co1@f.co", "Firma CO1")
        nit = company.nit

    headers = await _login(api_client, "co1@f.co")
    resp = await api_client.get("/companies", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["nit"] == nit
    assert set(item) >= {"id", "name", "nit", "active", "has_odoo", "has_imap"}
    # Nunca se exponen las credenciales cifradas.
    assert "odoo_password" not in item
    assert "imap_password" not in item


async def test_companies_aisladas_por_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _seed_user_company(session, "coa@f.co", "Firma COA")
        _seed_user_company(session, "cob@f.co", "Firma COB")

    headers_b = await _login(api_client, "cob@f.co")
    data = (await api_client.get("/companies", headers=headers_b)).json()
    assert len(data) == 1  # cada firma ve solo su empresa
