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


async def test_crear_y_ver_detalle_sin_password(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _seed_user_company(session, "cc@f.co", "Firma CC")

    headers = await _login(api_client, "cc@f.co")
    resp = await api_client.post(
        "/companies",
        headers=headers,
        json={
            "name": "Nueva Empresa",
            "nit": "901111111",
            "odoo_url": "https://odoo.test",
            "odoo_username": "u",
            "odoo_password": "secret",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_odoo"] is True
    cid = body["id"]

    detail = (await api_client.get(f"/companies/{cid}", headers=headers)).json()
    assert detail["odoo_username"] == "u"
    assert detail["has_odoo_password"] is True
    # La contrasena NUNCA se devuelve, ni en el detalle.
    assert "odoo_password" not in detail
    assert "imap_password" not in detail


async def test_editar_empresa(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_user_company(session, "ce@f.co", "Firma CE")
        cid = str(company.id)

    headers = await _login(api_client, "ce@f.co")
    resp = await api_client.patch(
        f"/companies/{cid}", headers=headers, json={"name": "Renombrada", "active": False}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renombrada"
    assert resp.json()["active"] is False


async def test_nit_duplicado_da_409(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _seed_user_company(session, "cd@f.co", "Firma CD")

    headers = await _login(api_client, "cd@f.co")
    payload = {"name": "A", "nit": "902222222"}
    assert (await api_client.post("/companies", headers=headers, json=payload)).status_code == 201
    assert (await api_client.post("/companies", headers=headers, json=payload)).status_code == 409


async def test_no_edita_empresa_de_otro_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        company_a = _seed_user_company(session, "ia@f.co", "Firma IA")
        _seed_user_company(session, "ib@f.co", "Firma IB")
        cid_a = str(company_a.id)

    headers_b = await _login(api_client, "ib@f.co")
    assert (await api_client.get(f"/companies/{cid_a}", headers=headers_b)).status_code == 404
    patch = await api_client.patch(f"/companies/{cid_a}", headers=headers_b, json={"name": "x"})
    assert patch.status_code == 404
