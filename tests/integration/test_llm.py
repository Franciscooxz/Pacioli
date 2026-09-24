"""Tests de integracion de la sugerencia LLM (Fase 5), con un AccountSuggester falso."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from contaflow.classification.llm_classifier import (
    Suggestion,
    SuggestionContext,
    suggest_for_document,
)
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.enums import DocType, DocumentStatus
from contaflow.models.source_document import SourceDocument
from contaflow.models.tenant import Tenant


class FakeSuggester:
    def __init__(self, suggestion: Suggestion) -> None:
        self._suggestion = suggestion
        self.calls = 0
        self.last_ctx: SuggestionContext | None = None

    def suggest(self, context: SuggestionContext) -> Suggestion:
        self.calls += 1
        self.last_ctx = context
        return self._suggestion


def _seed_doc(session: Session, status: DocumentStatus) -> uuid.UUID:
    tenant = Tenant(name="Firma LLM")
    session.add(tenant)
    session.flush()
    company = Company(tenant_id=tenant.id, name="Empresa", nit=f"900{uuid.uuid4().hex[:9]}")
    session.add(company)
    session.flush()
    doc = SourceDocument(
        tenant_id=tenant.id,
        company_id=company.id,
        status=status,
        raw_xml_uri="mem://x",
        raw_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        issuer_name="Nube Digital SAS",
        doc_type=DocType.FACTURA_COMPRA,
        total=Decimal("149940.00"),
    )
    session.add(doc)
    session.flush()
    session.add(
        DocumentLine(
            tenant_id=tenant.id,
            document_id=doc.id,
            line_id="1",
            description="Suscripcion software mensual",
            quantity=Decimal("1"),
            unit_price=Decimal("126000.00"),
            line_total=Decimal("126000.00"),
        )
    )
    session.commit()
    return doc.id


def test_llm_sugiere_y_queda_en_revision(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(session, DocumentStatus.PENDING_REVIEW)
        fake = FakeSuggester(Suggestion("519530", Decimal("0.72"), "gasto de software"))

        status = suggest_for_document(session, fake, doc_id)

        assert status is DocumentStatus.PENDING_REVIEW  # sigue en revision humana
        assert fake.calls == 1
        assert fake.last_ctx is not None
        assert "Suscripcion software mensual" in fake.last_ctx.line_descriptions

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code == "519530"
        assert doc.classification_confidence == Decimal("0.72")

        events = session.scalars(
            select(DocumentEvent.payload).where(DocumentEvent.document_id == doc_id)
        ).all()
        assert any(p and p.get("source") == "llm" for p in events)


def test_llm_sin_sugerencia_no_cambia_cuenta(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(session, DocumentStatus.PENDING_REVIEW)
        fake = FakeSuggester(Suggestion(None, Decimal("0"), "no se pudo determinar"))

        suggest_for_document(session, fake, doc_id)

        doc = session.get(SourceDocument, doc_id)
        assert doc is not None
        assert doc.proposed_account_code is None


def test_llm_no_actua_si_no_esta_en_revision(pg_engine: Engine) -> None:
    with Session(pg_engine) as session:
        doc_id = _seed_doc(session, DocumentStatus.CLASSIFIED)
        fake = FakeSuggester(Suggestion("1", Decimal("1"), "x"))

        status = suggest_for_document(session, fake, doc_id)

        assert status is DocumentStatus.CLASSIFIED
        assert fake.calls == 0  # no se llama al LLM fuera del residuo
