"""Tests de la API de auth y del aislamiento multi-tenant (Fase 0.1).

Usan el cliente async (api_client) contra la base efimera. El sembrado se hace con la
sesion sincrona (pg_engine); la API lee via su sesion async apuntada a la misma base.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.company import Company
from contaflow.models.enums import DocumentStatus, UserRole
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant
from contaflow.models.user import User


def _seed_user(session: Session, email: str, password: str, firma: str) -> User:
    tenant = Tenant(name=firma)
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    return user


def _seed_doc(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    company = Company(tenant_id=tenant_id, name="Empresa", nit=f"900{uuid.uuid4().hex[:9]}")
    session.add(company)
    session.flush()
    doc = SourceDocument(
        tenant_id=tenant_id,
        company_id=company.id,
        status=DocumentStatus.RECEIVED,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
    )
    session.add(doc)
    session.commit()
    return doc.id


async def test_login_y_me(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "ana@firma.co", "secreto-123", "Firma Ana")

    resp = await api_client.post(
        "/auth/login", json={"email": "ana@firma.co", "password": "secreto-123"}
    )
    assert resp.status_code == 200
    tokens = resp.json()

    me = await api_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "ana@firma.co"


async def test_login_password_incorrecta(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "beto@firma.co", "secreto-123", "Firma Beto")

    resp = await api_client.post(
        "/auth/login", json={"email": "beto@firma.co", "password": "incorrecta"}
    )
    assert resp.status_code == 401


async def test_me_sin_token_es_401(api_client: httpx.AsyncClient) -> None:
    resp = await api_client.get("/auth/me")
    assert resp.status_code == 401


async def test_refresh_emite_access_valido(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _seed_user(session, "cami@firma.co", "secreto-123", "Firma Cami")

    login = (
        await api_client.post(
            "/auth/login", json={"email": "cami@firma.co", "password": "secreto-123"}
        )
    ).json()
    refreshed = await api_client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]

    me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


async def test_documents_aislamiento_multi_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        user_a = _seed_user(session, "a@firma.co", "secreto-123", "Firma A")
        user_b = _seed_user(session, "b@firma.co", "secreto-123", "Firma B")
        doc_a = _seed_doc(session, user_a.tenant_id)
        _seed_doc(session, user_b.tenant_id)  # documento de la otra firma

    login_a = (
        await api_client.post(
            "/auth/login", json={"email": "a@firma.co", "password": "secreto-123"}
        )
    ).json()
    resp = await api_client.get(
        "/documents", headers={"Authorization": f"Bearer {login_a['access_token']}"}
    )
    assert resp.status_code == 200
    docs = resp.json()

    # El usuario de la Firma A solo ve su documento, nunca el de la Firma B.
    assert len(docs) == 1
    assert docs[0]["id"] == str(doc_a)
