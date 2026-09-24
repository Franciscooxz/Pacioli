"""Clasificacion asistida por LLM para el residuo ambiguo (Fase 5).

Solo se invoca sobre documentos que el motor de reglas mando a PENDING_REVIEW (sin
regla o baja confianza). El LLM SUGIERE una cuenta; el documento sigue en
PENDING_REVIEW para que un humano confirme (control humano sobre lo ambiguo).

Privacidad (CLAUDE.md 4.5): al LLM se le envia el nombre del emisor, el tipo de
documento, las descripciones de las lineas y los montos, mas las cuentas candidatas.
NO se envia el NIT (puede ser de una persona natural) ni el XML crudo.

La interfaz AccountSuggester permite probar la logica con un doble, sin llamar al API.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.core.exceptions import IngestionError
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.enums import ActorType, DocumentEventType, DocumentStatus
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SuggestionContext:
    issuer_name: str | None
    doc_type: str | None
    total: Decimal | None
    line_descriptions: list[str] = field(default_factory=list)
    candidate_accounts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Suggestion:
    account_code: str | None
    confidence: Decimal
    rationale: str


@runtime_checkable
class AccountSuggester(Protocol):
    def suggest(self, context: SuggestionContext) -> Suggestion: ...


_SYSTEM = (
    "Eres un asistente contable colombiano. Dado un documento electronico, elige la "
    "cuenta del PUC mas adecuada. Prefiere una de las cuentas candidatas si aplica; si "
    "ninguna aplica, propon el codigo PUC (hoja) mas razonable. Responde UNICAMENTE con "
    'JSON: {"account_code": "<codigo>", "confidence": <0..1>, "rationale": "<breve>"}.'
)


def _build_prompt(ctx: SuggestionContext) -> str:
    lines = "\n".join(f"- {d}" for d in ctx.line_descriptions) or "(sin descripciones)"
    candidates = ", ".join(ctx.candidate_accounts) or "(sin candidatas)"
    total = f"{ctx.total}" if ctx.total is not None else "(desconocido)"
    return (
        f"Emisor: {ctx.issuer_name or '(desconocido)'}\n"
        f"Tipo de documento: {ctx.doc_type or '(desconocido)'}\n"
        f"Total: {total}\n"
        f"Lineas:\n{lines}\n"
        f"Cuentas candidatas: {candidates}\n"
    )


def _parse_suggestion(text: str) -> Suggestion:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return Suggestion(None, Decimal("0"), "respuesta sin JSON")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return Suggestion(None, Decimal("0"), "JSON no parseable")
    code = data.get("account_code")
    account_code = str(code) if code else None
    try:
        raw = Decimal(str(data.get("confidence", 0)))
    except (InvalidOperation, TypeError):
        raw = Decimal("0")
    confidence = min(Decimal("1"), max(Decimal("0"), raw))
    rationale = str(data.get("rationale", ""))[:500]
    return Suggestion(account_code, confidence, rationale)


class ClaudeAccountSuggester:
    """Implementacion real sobre el SDK de Anthropic (Claude)."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def suggest(self, context: SuggestionContext) -> Suggestion:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(context)}],
        )
        text = "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return _parse_suggestion(text)


def suggest_for_document(
    session: Session, suggester: AccountSuggester, document_id: uuid.UUID
) -> DocumentStatus:
    """Pide una sugerencia al LLM y la adjunta al documento (sigue en PENDING_REVIEW)."""
    doc = session.get(SourceDocument, document_id)
    if doc is None:
        raise IngestionError(f"source_document inexistente: {document_id}")
    if doc.status is not DocumentStatus.PENDING_REVIEW:
        return doc.status  # solo el residuo ambiguo

    company = session.get(Company, doc.company_id)
    if company is None:
        raise IngestionError(f"company inexistente para el documento {document_id}")

    descriptions = [
        d
        for d in session.scalars(
            select(DocumentLine.description).where(DocumentLine.document_id == doc.id)
        )
        if d
    ]
    candidates = sorted(
        set(
            session.scalars(
                select(ClassificationRule.account_code).where(
                    ClassificationRule.company_id == doc.company_id,
                    ClassificationRule.active.is_(True),
                )
            )
        )
    )

    ctx = SuggestionContext(
        issuer_name=doc.issuer_name,
        doc_type=doc.doc_type.value if doc.doc_type else None,
        total=doc.total,
        line_descriptions=descriptions,
        candidate_accounts=candidates,
    )
    suggestion = suggester.suggest(ctx)

    if suggestion.account_code:
        doc.proposed_account_code = suggestion.account_code
        doc.classification_confidence = suggestion.confidence
        doc.classification_rule_id = None  # origen LLM, no una regla
        payload: dict[str, object] = {
            "source": "llm",
            "account_code": suggestion.account_code,
            "confidence": str(suggestion.confidence),
            "rationale": suggestion.rationale,
        }
    else:
        payload = {"source": "llm", "result": "sin_sugerencia", "rationale": suggestion.rationale}

    session.add(
        DocumentEvent(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            event_type=DocumentEventType.SENT_TO_REVIEW,
            actor_type=ActorType.SYSTEM,
            payload=payload,
        )
    )
    session.commit()
    logger.info("documento %s: sugerencia LLM %s", doc.id, suggestion.account_code)
    return doc.status
