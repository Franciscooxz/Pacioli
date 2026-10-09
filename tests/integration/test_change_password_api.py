"""Tests del cambio de contrasena del usuario autenticado."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from draxia.core.auth import hash_password
from draxia.models.enums import UserRole
from draxia.models.tenant import Tenant
from draxia.models.user import User

PASSWORD = "secreto-123"
NEW = "nueva-clave-456"


def _seed_user(session: Session, email: str) -> None:
    tenant = Tenant(name=f"Firma {uuid.uuid4().hex[:6]}")
    session.add(tenant)
    session.flush()
    session.add(
        User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(PASSWORD),
            role=UserRole.MEMBER,
        )
    )
    session.commit()


async def _login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_cambiar_contrasena_ok(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "cp@f.co")

    token = (await _login(api_client, "cp@f.co", PASSWORD)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await api_client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": NEW},
    )
    assert resp.status_code == 204

    # La nueva sirve; la vieja ya no.
    assert (await _login(api_client, "cp@f.co", NEW)).status_code == 200
    assert (await _login(api_client, "cp@f.co", PASSWORD)).status_code == 401


async def test_cambiar_contrasena_actual_incorrecta(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "cp2@f.co")

    token = (await _login(api_client, "cp2@f.co", PASSWORD)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await api_client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "equivocada", "new_password": NEW},
    )
    assert resp.status_code == 400
    # La contrasena no cambio.
    assert (await _login(api_client, "cp2@f.co", PASSWORD)).status_code == 200


async def test_cambiar_contrasena_muy_corta(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "cp3@f.co")

    token = (await _login(api_client, "cp3@f.co", PASSWORD)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await api_client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "corta"},
    )
    assert resp.status_code == 422


async def test_cambiar_contrasena_sin_sesion(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    resp = await api_client.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW},
    )
    assert resp.status_code == 401
