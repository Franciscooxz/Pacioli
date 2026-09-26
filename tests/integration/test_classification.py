"""Tests de integracion del motor de reglas (Fase 2), con Postgres efimera."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.classification.rule_engine import classify_document
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.enums import DocumentEventType, DocumentStatus
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant


def _seed_company(session: Session) -> Company:
    tenant = Tenant(name="Firma Clasif")
    session.add(tenant)
    session.flush()
    company = Company(tenant_id=tenant.id, name="Empresa", nit=f"900{uuid.uuid4().hex[:9]}")
    session.add(company)
    session.flush()
    return company


def _seed_parsed_doc(
    session: Session,
    company: Company,
    issuer_nit: str = "900123456",
    issuer_name: str = "Proveedor SAS",
    descriptions: list[str] | None = None,
) -> uuid.UUID:
    doc = SourceDocument(
        tenant_id=company.tenant_id,
        company_id=company.id,
        status=DocumentStatus.PARSED,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        issuer_nit=issuer_nit,
        issuer_name=issuer_name,
    )
    session.add(doc)
    session.flush()
    for i, desc in enumerate(descriptions or [], start=1):
        session.add(
            DocumentLine(
                tenant_id=company.tenant_id,
                document_id=doc.id,
                line_id=str(i),
                description=desc,
                quantity=Decimal("1"),
                unit_price=Decimal("100.00"),
                line_total=Decimal("100.00"),
            )
        )
    session.commit()
    return doc.id


def _add_rule(session: Session, company: Company, **kwargs: object) -> ClassificationRule:
    kwargs.setdefault("account_code", "613505")
    kwargs.setdefault("priority", 100)
    kwargs.setdefault("confidence", Decimal("0.95"))
    rule = ClassificationRule(tenant_id=company.tenant_id, company_id=company.id, **kwargs)
    session.add(rule)
    session.commit()
    return rule


def test_clasifica_por_nit(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        rule = _add_rule(session, company, issuer_nit="900123456", account_code="613505")
        doc_id = _seed_parsed_doc(session, company, issuer_nit="900123456")

        status = classify_document(session, doc_id, threshold=Decimal("0.80"))
        assert status is DocumentStatus.CLASSIFIED

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code == "613505"
        assert doc.classification_rule_id == rule.id

        events = set(
            session.scalars(
                select(DocumentEvent.event_type).where(DocumentEvent.document_id == doc_id)
            )
        )
        assert DocumentEventType.CLASSIFIED in events


def test_confianza_baja_va_a_revision_con_propuesta(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        _add_rule(
            session,
            company,
            issuer_nit="900123456",
            account_code="613505",
            confidence=Decimal("0.50"),
        )
        doc_id = _seed_parsed_doc(session, company, issuer_nit="900123456")

        status = classify_document(session, doc_id, threshold=Decimal("0.80"))
        assert status is DocumentStatus.PENDING_REVIEW

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code == "613505"  # la propuesta se guarda igual


def test_sin_regla_va_a_revision(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        doc_id = _seed_parsed_doc(session, company)

        status = classify_document(session, doc_id, threshold=Decimal("0.80"))
        assert status is DocumentStatus.PENDING_REVIEW

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code is None


def test_firma_invalida_va_a_revision(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        # Regla que normalmente clasificaria con alta confianza...
        _add_rule(
            session,
            company,
            issuer_nit="900123456",
            account_code="613505",
            confidence=Decimal("0.99"),
        )
        doc_id = _seed_parsed_doc(session, company, issuer_nit="900123456")
        # ...pero la firma es invalida: debe forzar revision humana.
        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        doc.signature_valid = False
        session.commit()

        status = classify_document(session, doc_id, threshold=Decimal("0.80"))
        assert status is DocumentStatus.PENDING_REVIEW

        events = set(
            session.scalars(
                select(DocumentEvent.event_type).where(DocumentEvent.document_id == doc_id)
            )
        )
        assert DocumentEventType.SENT_TO_REVIEW in events
        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code is None  # no se auto-propone con firma invalida


def test_clasifica_por_patron_y_prioridad(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        company = _seed_company(session)
        # Regla catch-all de baja prioridad y una especifica por patron de mayor prioridad.
        _add_rule(session, company, account_code="519999", priority=1)
        _add_rule(session, company, match_pattern="arrend", account_code="511595", priority=90)
        doc_id = _seed_parsed_doc(session, company, descriptions=["Arrendamiento oficina enero"])

        status = classify_document(session, doc_id, threshold=Decimal("0.80"))
        assert status is DocumentStatus.CLASSIFIED

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code == "511595"  # gana la de mayor prioridad
