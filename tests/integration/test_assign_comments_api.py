"""Tests de asignacion de revisor y comentarios, con aislamiento multi-tenant."""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from draxia.core.auth import hash_password
from draxia.models.company import Company
from draxia.models.enums import DocType, DocumentStatus, UserRole
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


def _add_user(session: Session, tenant_id: uuid.UUID, email: str, active: bool = True) -> User:
    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=hash_password(PASSWORD),
        role=UserRole.MEMBER,
        active=active,
    )
    session.add(user)
    session.commit()
    return user


def _seed_doc(session: Session, company: Company) -> uuid.UUID:
    doc = SourceDocument(
        tenant_id=company.tenant_id,
        company_id=company.id,
        status=DocumentStatus.PENDING_REVIEW,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        issuer_nit="900123456",
        doc_type=DocType.FACTURA_COMPRA,
        total=Decimal("119000.00"),
    )
    session.add(doc)
    session.commit()
    return doc.id


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_asignar_y_desasignar(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        admin, company = _seed_user_company(session, "as@f.co", "Firma AS")
        revisor = _add_user(session, company.tenant_id, "revisor@f.co")
        doc_id = _seed_doc(session, company)
        revisor_id = str(revisor.id)

    headers = await _login(api_client, "as@f.co")
    resp = await api_client.post(
        f"/documents/{doc_id}/assign", headers=headers, json={"user_id": revisor_id}
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_user_id"] == revisor_id

    detail = await api_client.get(f"/documents/{doc_id}", headers=headers)
    assert detail.json()["assigned_user_id"] == revisor_id

    # Desasignar con null.
    resp = await api_client.post(
        f"/documents/{doc_id}/assign", headers=headers, json={"user_id": None}
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_user_id"] is None


async def test_asignar_usuario_de_otro_tenant_404(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "oa@f.co", "Firma OA")
        user_b, _ = _seed_user_company(session, "ob@f.co", "Firma OB")
        doc_id = _seed_doc(session, company_a)
        user_b_id = str(user_b.id)

    headers = await _login(api_client, "oa@f.co")
    resp = await api_client.post(
        f"/documents/{doc_id}/assign", headers=headers, json={"user_id": user_b_id}
    )
    assert resp.status_code == 404


async def test_comentarios(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "cm@f.co", "Firma CM")
        doc_id = _seed_doc(session, company)

    headers = await _login(api_client, "cm@f.co")
    created = await api_client.post(
        f"/documents/{doc_id}/comments", headers=headers, json={"body": "Falta el centro de costo"}
    )
    assert created.status_code == 201
    assert created.json()["author_email"] == "cm@f.co"

    listed = await api_client.get(f"/documents/{doc_id}/comments", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["body"] == "Falta el centro de costo"


async def test_comentario_vacio_422(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "cv@f.co", "Firma CV")
        doc_id = _seed_doc(session, company)

    headers = await _login(api_client, "cv@f.co")
    resp = await api_client.post(
        f"/documents/{doc_id}/comments", headers=headers, json={"body": ""}
    )
    assert resp.status_code == 422


async def test_assignable_solo_activos_del_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        admin, company = _seed_user_company(session, "al@f.co", "Firma AL")
        _add_user(session, company.tenant_id, "activo@f.co", active=True)
        _add_user(session, company.tenant_id, "inactivo@f.co", active=False)
        # Usuario de otro tenant: no debe aparecer.
        _seed_user_company(session, "otro@f.co", "Firma OTRA")

    headers = await _login(api_client, "al@f.co")
    resp = await api_client.get("/users/assignable", headers=headers)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "al@f.co" in emails
    assert "activo@f.co" in emails
    assert "inactivo@f.co" not in emails  # inactivo excluido
    assert "otro@f.co" not in emails  # otro tenant excluido


async def test_comentar_documento_de_otro_tenant_404(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "x1@f.co", "Firma X1")
        _seed_user_company(session, "x2@f.co", "Firma X2")
        doc_a = _seed_doc(session, company_a)

    headers_b = await _login(api_client, "x2@f.co")
    resp = await api_client.post(
        f"/documents/{doc_a}/comments", headers=headers_b, json={"body": "hola"}
    )
    assert resp.status_code == 404
