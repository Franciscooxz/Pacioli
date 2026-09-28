"""Tests de gestion de usuarios y enforcement de roles (ADMIN vs MEMBER)."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.enums import UserRole
from contaflow.models.tenant import Tenant
from contaflow.models.user import User

PASSWORD = "secreto-123"


def _seed_user(session: Session, tenant_id: uuid.UUID, email: str, role: UserRole) -> uuid.UUID:
    user = User(
        tenant_id=tenant_id, email=email, password_hash=hash_password(PASSWORD), role=role
    )
    session.add(user)
    session.commit()
    return user.id


def _seed_tenant(session: Session, firma: str) -> uuid.UUID:
    tenant = Tenant(name=firma)
    session.add(tenant)
    session.commit()
    return tenant.id


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_admin_gestiona_usuarios(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tid = _seed_tenant(session, "Firma U")
        _seed_user(session, tid, "admin@u.co", UserRole.ADMIN)

    headers = await _login(api_client, "admin@u.co")
    assert len((await api_client.get("/users", headers=headers)).json()) == 1

    created = await api_client.post(
        "/users",
        headers=headers,
        json={"email": "m@u.co", "password": "password123", "role": "MEMBER"},
    )
    assert created.status_code == 201
    mid = created.json()["id"]
    assert len((await api_client.get("/users", headers=headers)).json()) == 2

    promoted = await api_client.patch(f"/users/{mid}", headers=headers, json={"role": "ADMIN"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "ADMIN"

    deactivated = await api_client.patch(f"/users/{mid}", headers=headers, json={"active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False


async def test_member_no_gestiona(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        tid = _seed_tenant(session, "Firma M")
        _seed_user(session, tid, "adminm@u.co", UserRole.ADMIN)
        _seed_user(session, tid, "member@u.co", UserRole.MEMBER)

    headers = await _login(api_client, "member@u.co")
    assert (await api_client.get("/users", headers=headers)).status_code == 403
    company = await api_client.post(
        "/companies", headers=headers, json={"name": "X", "nit": "900111222"}
    )
    assert company.status_code == 403


async def test_no_puede_modificarse_a_si_mismo(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        tid = _seed_tenant(session, "Firma S")
        admin_id = _seed_user(session, tid, "self@u.co", UserRole.ADMIN)

    headers = await _login(api_client, "self@u.co")
    resp = await api_client.patch(f"/users/{admin_id}", headers=headers, json={"role": "MEMBER"})
    assert resp.status_code == 409


async def test_usuarios_aislados_por_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        ta = _seed_tenant(session, "Firma UA")
        _seed_user(session, ta, "ua@u.co", UserRole.ADMIN)
        tb = _seed_tenant(session, "Firma UB")
        _seed_user(session, tb, "ub@u.co", UserRole.ADMIN)

    headers = await _login(api_client, "ub@u.co")
    data = (await api_client.get("/users", headers=headers)).json()
    assert len(data) == 1  # solo su propio usuario
    assert data[0]["email"] == "ub@u.co"
