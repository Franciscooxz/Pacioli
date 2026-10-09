"""Tests del endpoint de subida manual de facturas (/documents/upload).

El request solo valida y encola (regla 4.6), asi que se monkeypatchea la tarea Celery
para capturar lo encolado sin necesitar Redis/MinIO. Incluye aislamiento multi-tenant.
"""

from __future__ import annotations

import base64
import uuid

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from draxia.core.auth import hash_password
from draxia.models.company import Company
from draxia.models.enums import UserRole
from draxia.models.tenant import Tenant
from draxia.models.user import User

PASSWORD = "secreto-123"
XML = b"<Invoice><cbc:ID>FE-1</cbc:ID></Invoice>"


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


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_subir_factura_encola(
    api_client: httpx.AsyncClient, pg_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "up@f.co", "Firma UP")
        company_id = str(company.id)

    captured: dict[str, tuple[str, str, str]] = {}
    monkeypatch.setattr(
        "draxia.workers.tasks.ingest_upload.delay",
        lambda *args: captured.__setitem__("args", args),
    )

    headers = await _login(api_client, "up@f.co")
    resp = await api_client.post(
        "/documents/upload",
        headers=headers,
        data={"company_id": company_id},
        files={"file": ("factura.xml", XML, "application/xml")},
    )

    assert resp.status_code == 202
    assert resp.json() == {"status": "queued", "company_id": company_id}
    cid, filename, xml_b64 = captured["args"]
    assert cid == company_id
    assert filename == "factura.xml"
    assert base64.b64decode(xml_b64) == XML


async def test_subir_a_empresa_de_otro_tenant_404(
    api_client: httpx.AsyncClient, pg_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "ta@f.co", "Firma TA")
        _seed_user_company(session, "tb@f.co", "Firma TB")
        company_a_id = str(company_a.id)

    called = {"n": 0}
    monkeypatch.setattr(
        "draxia.workers.tasks.ingest_upload.delay",
        lambda *args: called.__setitem__("n", called["n"] + 1),
    )

    headers_b = await _login(api_client, "tb@f.co")
    resp = await api_client.post(
        "/documents/upload",
        headers=headers_b,
        data={"company_id": company_a_id},
        files={"file": ("factura.xml", XML, "application/xml")},
    )
    assert resp.status_code == 404
    assert called["n"] == 0  # no se encola nada


async def test_subir_archivo_no_xml_400(
    api_client: httpx.AsyncClient, pg_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "nx@f.co", "Firma NX")
        company_id = str(company.id)

    monkeypatch.setattr("draxia.workers.tasks.ingest_upload.delay", lambda *args: None)

    headers = await _login(api_client, "nx@f.co")
    resp = await api_client.post(
        "/documents/upload",
        headers=headers,
        data={"company_id": company_id},
        files={"file": ("factura.txt", b"esto no es xml", "text/plain")},
    )
    assert resp.status_code == 400


async def test_subir_archivo_vacio_400(
    api_client: httpx.AsyncClient, pg_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "ev@f.co", "Firma EV")
        company_id = str(company.id)

    monkeypatch.setattr("draxia.workers.tasks.ingest_upload.delay", lambda *args: None)

    headers = await _login(api_client, "ev@f.co")
    resp = await api_client.post(
        "/documents/upload",
        headers=headers,
        data={"company_id": company_id},
        files={"file": ("vacio.xml", b"", "application/xml")},
    )
    assert resp.status_code == 400
