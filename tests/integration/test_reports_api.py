"""Tests del endpoint /reports: resumen agregado, export CSV y aislamiento multi-tenant."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.company import Company
from contaflow.models.enums import DocType, DocumentStatus, UserRole
from contaflow.models.source_document import SourceDocument
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


def _seed_doc(
    session: Session,
    company: Company,
    *,
    issue_date: date,
    subtotal: str,
    total_tax: str,
    total_withholding: str,
    total: str,
) -> None:
    session.add(
        SourceDocument(
            tenant_id=company.tenant_id,
            company_id=company.id,
            status=DocumentStatus.POSTED,
            raw_xml_uri="mem://x",
            raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
            doc_type=DocType.FACTURA_COMPRA,
            issuer_nit="900123456",
            issuer_name="Proveedor SAS",
            issue_date=issue_date,
            subtotal=Decimal(subtotal),
            total_tax=Decimal(total_tax),
            total_withholding=Decimal(total_withholding),
            total=Decimal(total),
        )
    )
    session.commit()


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_summary_agrega(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_user_company(session, "r1@f.co", "Firma R1")
        _seed_doc(
            session, company, issue_date=date(2026, 1, 10),
            subtotal="1000.00", total_tax="190.00", total_withholding="25.00", total="1165.00",
        )
        _seed_doc(
            session, company, issue_date=date(2026, 2, 5),
            subtotal="2000.00", total_tax="380.00", total_withholding="50.00", total="2330.00",
        )

    headers = await _login(api_client, "r1@f.co")
    s = (await api_client.get("/reports/summary", headers=headers)).json()
    assert s["count"] == 2
    assert Decimal(s["subtotal"]) == Decimal("3000.00")
    assert Decimal(s["total"]) == Decimal("3495.00")
    assert s["by_status"]["POSTED"] == 2
    assert {b["month"] for b in s["by_month"]} == {"2026-01", "2026-02"}


async def test_export_csv(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_user_company(session, "r2@f.co", "Firma R2")
        _seed_doc(
            session, company, issue_date=date(2026, 3, 1),
            subtotal="500.00", total_tax="95.00", total_withholding="0.00", total="595.00",
        )

    headers = await _login(api_client, "r2@f.co")
    resp = await api_client.get("/reports/export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "emisor" in resp.text
    assert "Proveedor SAS" in resp.text


async def test_summary_aislado_por_tenant(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company_a = _seed_user_company(session, "ra@f.co", "Firma RA")
        _seed_user_company(session, "rb@f.co", "Firma RB")
        _seed_doc(
            session, company_a, issue_date=date(2026, 1, 1),
            subtotal="100.00", total_tax="19.00", total_withholding="0.00", total="119.00",
        )

    headers_b = await _login(api_client, "rb@f.co")
    s = (await api_client.get("/reports/summary", headers=headers_b)).json()
    assert s["count"] == 0
    assert Decimal(s["total"]) == Decimal("0")
