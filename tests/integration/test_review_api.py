"""Tests de la API de reglas y revision humana (Fase 3a), con aislamiento multi-tenant."""

from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.core.auth import hash_password
from contaflow.models.company import Company
from contaflow.models.document_line import DocumentLine
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import DocType, DocumentStatus, TaxCategory, UserRole
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant
from contaflow.models.user import User

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


def _seed_pending_doc(session: Session, company: Company) -> uuid.UUID:
    doc = SourceDocument(
        tenant_id=company.tenant_id,
        company_id=company.id,
        status=DocumentStatus.PENDING_REVIEW,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        issuer_nit="900123456",
        issuer_name="Proveedor SAS",
        doc_type=DocType.FACTURA_COMPRA,
        total=Decimal("119000.00"),
    )
    session.add(doc)
    session.flush()
    session.add(
        DocumentLine(
            tenant_id=company.tenant_id,
            document_id=doc.id,
            line_id="1",
            description="Servicio",
            quantity=Decimal("1"),
            unit_price=Decimal("100000.00"),
            line_total=Decimal("100000.00"),
        )
    )
    session.add(
        DocumentTax(
            tenant_id=company.tenant_id,
            document_id=doc.id,
            category=TaxCategory.IVA,
            is_withholding=False,
            tax_name="IVA",
            percent=Decimal("19.00"),
            taxable_amount=Decimal("100000.00"),
            tax_amount=Decimal("19000.00"),
        )
    )
    session.commit()
    return doc.id


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_crear_y_listar_reglas(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "a@f.co", "Firma A")
        company_id = company.id

    headers = await _login(api_client, "a@f.co")
    created = await api_client.post(
        "/rules",
        headers=headers,
        json={"company_id": str(company_id), "issuer_nit": "900123456", "account_code": "613505"},
    )
    assert created.status_code == 201

    listed = await api_client.get("/rules", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["account_code"] == "613505"


async def test_reglas_aisladas_por_tenant(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "a2@f.co", "Firma A2")
        _seed_user_company(session, "b2@f.co", "Firma B2")
        session.add(
            ClassificationRule(
                tenant_id=company_a.tenant_id,
                company_id=company_a.id,
                account_code="613505",
                confidence=Decimal("0.9"),
                priority=100,
            )
        )
        session.commit()

    headers_b = await _login(api_client, "b2@f.co")
    listed = await api_client.get("/rules", headers=headers_b)
    assert listed.status_code == 200
    assert listed.json() == []  # B no ve las reglas de A


async def test_aprobar_documento_crea_regla(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "c@f.co", "Firma C")
        doc_id = _seed_pending_doc(session, company)

    headers = await _login(api_client, "c@f.co")
    resp = await api_client.post(
        f"/documents/{doc_id}/approve",
        headers=headers,
        json={"account_code": "511595", "create_rule": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLASSIFIED"

    detail = await api_client.get(f"/documents/{doc_id}", headers=headers)
    assert detail.json()["proposed_account_code"] == "511595"
    assert len(detail.json()["taxes"]) == 1

    rules = await api_client.get("/rules", headers=headers)
    assert len(rules.json()) == 1  # la aprobacion creo la regla


async def test_rechazar_documento(api_client: httpx.AsyncClient, pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        _, company = _seed_user_company(session, "d@f.co", "Firma D")
        doc_id = _seed_pending_doc(session, company)

    headers = await _login(api_client, "d@f.co")
    resp = await api_client.post(
        f"/documents/{doc_id}/reject", headers=headers, json={"reason": "no corresponde"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


async def test_no_puede_tocar_documento_de_otro_tenant(
    api_client: httpx.AsyncClient, pg_engine: Engine
) -> None:
    with Session(pg_engine) as session:
        _, company_a = _seed_user_company(session, "a3@f.co", "Firma A3")
        _seed_user_company(session, "b3@f.co", "Firma B3")
        doc_a = _seed_pending_doc(session, company_a)

    headers_b = await _login(api_client, "b3@f.co")
    assert (await api_client.get(f"/documents/{doc_a}", headers=headers_b)).status_code == 404
    approve = await api_client.post(
        f"/documents/{doc_a}/approve", headers=headers_b, json={"account_code": "1"}
    )
    assert approve.status_code == 404
