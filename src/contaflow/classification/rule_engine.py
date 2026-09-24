"""Motor de reglas deterministas de clasificacion contable.

Toma un documento PARSED y propone una cuenta del PUC segun las reglas de la empresa.
Resuelve el grueso de los documentos; lo que no alcanza el umbral de confianza va a
revision humana (PENDING_REVIEW) con la propuesta adjunta para acelerar al contador.

Una regla matchea si cumple TODOS sus criterios definidos (AND): issuer_nit exacto y/o
match_pattern (regex, case-insensitive) contra el nombre del emisor y las descripciones
de las lineas. Gana la de mayor priority; desempata la mayor confidence.
"""

from __future__ import annotations

import logging
import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.config import get_settings
from contaflow.core.exceptions import IngestionError
from contaflow.models.company import Company
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.enums import ActorType, DocumentEventType, DocumentStatus
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument

logger = logging.getLogger(__name__)


def _rule_matches(rule: ClassificationRule, issuer_nit: str | None, haystack: str) -> bool:
    if rule.issuer_nit and rule.issuer_nit != issuer_nit:
        return False
    if rule.match_pattern:
        try:
            if re.search(rule.match_pattern, haystack, re.IGNORECASE) is None:
                return False
        except re.error:
            logger.warning("regla %s con patron invalido, se ignora", rule.id)
            return False
    return True


def select_rule(
    rules: list[ClassificationRule], issuer_nit: str | None, haystack: str
) -> ClassificationRule | None:
    """Elige la mejor regla: mayor priority, luego mayor confidence."""
    matching = [r for r in rules if _rule_matches(r, issuer_nit, haystack)]
    if not matching:
        return None
    matching.sort(key=lambda r: (r.priority, r.confidence), reverse=True)
    return matching[0]


def _event(
    company: Company,
    document_id: uuid.UUID,
    event_type: DocumentEventType,
    payload: dict[str, object],
) -> DocumentEvent:
    return DocumentEvent(
        tenant_id=company.tenant_id,
        document_id=document_id,
        event_type=event_type,
        actor_type=ActorType.RULE_ENGINE,
        payload=payload,
    )


def classify_document(
    session: Session, document_id: uuid.UUID, threshold: Decimal | None = None
) -> DocumentStatus:
    """Clasifica un documento PARSED. Idempotente (si no esta PARSED, no hace nada)."""
    if threshold is None:
        threshold = get_settings().classification_confidence_threshold

    doc = session.get(SourceDocument, document_id)
    if doc is None:
        raise IngestionError(f"source_document inexistente: {document_id}")
    if doc.status is not DocumentStatus.PARSED:
        return doc.status

    company = session.get(Company, doc.company_id)
    if company is None:
        raise IngestionError(f"company inexistente para el documento {document_id}")

    descriptions = session.scalars(
        select(DocumentLine.description).where(DocumentLine.document_id == doc.id)
    )
    parts = [doc.issuer_name or ""]
    parts.extend(d for d in descriptions if d)
    haystack = " ".join(parts)

    rules = list(
        session.scalars(
            select(ClassificationRule).where(
                ClassificationRule.company_id == doc.company_id,
                ClassificationRule.active.is_(True),
            )
        )
    )
    rule = select_rule(rules, doc.issuer_nit, haystack)

    if rule is None:
        doc.status = DocumentStatus.PENDING_REVIEW
        session.add(
            _event(company, doc.id, DocumentEventType.SENT_TO_REVIEW, {"reason": "sin_regla"})
        )
        session.commit()
        logger.info("documento %s -> PENDING_REVIEW (sin regla)", doc.id)
        return doc.status

    # Guardamos la propuesta aunque no alcance el umbral (le sirve al revisor).
    doc.proposed_account_code = rule.account_code
    doc.proposed_cost_center = rule.cost_center
    doc.classification_confidence = rule.confidence
    doc.classification_rule_id = rule.id

    if rule.confidence >= threshold:
        doc.status = DocumentStatus.CLASSIFIED
        session.add(
            _event(
                company,
                doc.id,
                DocumentEventType.CLASSIFIED,
                {"account_code": rule.account_code, "confidence": str(rule.confidence)},
            )
        )
        session.commit()
        logger.info("documento %s -> CLASSIFIED (%s)", doc.id, rule.account_code)
        return doc.status

    doc.status = DocumentStatus.PENDING_REVIEW
    session.add(
        _event(
            company,
            doc.id,
            DocumentEventType.SENT_TO_REVIEW,
            {
                "reason": "confianza_baja",
                "account_code": rule.account_code,
                "confidence": str(rule.confidence),
            },
        )
    )
    session.commit()
    logger.info("documento %s -> PENDING_REVIEW (confianza baja)", doc.id)
    return doc.status
