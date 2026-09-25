"""Endpoints de documentos: listado, detalle y revision humana.

Aislamiento multi-tenant estricto: toda consulta filtra por el tenant del usuario.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.db import get_async_session
from contaflow.models.document_event import DocumentEvent
from contaflow.models.document_line import DocumentLine
from contaflow.models.document_tax import DocumentTax
from contaflow.models.enums import ActorType, DocumentEventType, DocumentStatus
from contaflow.models.rule import ClassificationRule
from contaflow.models.source_document import SourceDocument
from contaflow.models.user import User
from contaflow.schemas.document import (
    ApproveRequest,
    DocumentDetailOut,
    DocumentOut,
    LineOut,
    RejectRequest,
    TaxOut,
)

router = APIRouter(prefix="/documents", tags=["documents"])

# Estados sobre los que el humano puede actuar en revision.
_REVIEWABLE = {DocumentStatus.PENDING_REVIEW, DocumentStatus.CLASSIFIED}


async def _get_owned_document(
    session: AsyncSession, user: User, document_id: uuid.UUID
) -> SourceDocument:
    doc = await session.get(SourceDocument, document_id)
    if doc is None or doc.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    return doc


def _user_event(
    doc: SourceDocument, user: User, event_type: DocumentEventType, payload: dict[str, object]
) -> DocumentEvent:
    return DocumentEvent(
        tenant_id=doc.tenant_id,
        document_id=doc.id,
        event_type=event_type,
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        payload=payload,
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    company_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SourceDocument]:
    query = select(SourceDocument).where(SourceDocument.tenant_id == current_user.tenant_id)
    if status_filter is not None:
        query = query.where(SourceDocument.status == status_filter)
    if company_id is not None:
        query = query.where(SourceDocument.company_id == company_id)
    result = await session.scalars(
        query.order_by(SourceDocument.received_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentDetailOut:
    doc = await _get_owned_document(session, current_user, document_id)
    lines = await session.scalars(select(DocumentLine).where(DocumentLine.document_id == doc.id))
    taxes = await session.scalars(select(DocumentTax).where(DocumentTax.document_id == doc.id))
    detail = DocumentDetailOut.model_validate(doc)
    detail.lines = [LineOut.model_validate(line) for line in lines]
    detail.taxes = [TaxOut.model_validate(tax) for tax in taxes]
    return detail


@router.post("/{document_id}/approve", response_model=DocumentOut)
async def approve_document(
    document_id: uuid.UUID,
    body: ApproveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceDocument:
    doc = await _get_owned_document(session, current_user, document_id)
    if doc.status not in _REVIEWABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede aprobar un documento en estado {doc.status.value}",
        )
    doc.proposed_account_code = body.account_code
    doc.proposed_cost_center = body.cost_center
    doc.classification_confidence = Decimal("1.0")  # confirmado por humano
    doc.classification_rule_id = None
    doc.status = DocumentStatus.CLASSIFIED
    session.add(
        _user_event(
            doc,
            current_user,
            DocumentEventType.CLASSIFIED,
            {"account_code": body.account_code, "source": "human"},
        )
    )
    if body.create_rule and doc.issuer_nit:
        session.add(
            ClassificationRule(
                tenant_id=doc.tenant_id,
                company_id=doc.company_id,
                issuer_nit=doc.issuer_nit,
                account_code=body.account_code,
                cost_center=body.cost_center,
                priority=100,
                confidence=Decimal("1.0"),
            )
        )
    await session.commit()
    await session.refresh(doc)
    return doc


@router.post("/{document_id}/reject", response_model=DocumentOut)
async def reject_document(
    document_id: uuid.UUID,
    body: RejectRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SourceDocument:
    doc = await _get_owned_document(session, current_user, document_id)
    if doc.status not in _REVIEWABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede rechazar un documento en estado {doc.status.value}",
        )
    doc.status = DocumentStatus.REJECTED
    session.add(_user_event(doc, current_user, DocumentEventType.REJECTED, {"reason": body.reason}))
    await session.commit()
    await session.refresh(doc)
    return doc


@router.post("/{document_id}/post", status_code=status.HTTP_202_ACCEPTED)
async def post_document_endpoint(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Encola la contabilizacion en Odoo (el trabajo pesado corre en Celery)."""
    doc = await _get_owned_document(session, current_user, document_id)
    if doc.status is not DocumentStatus.CLASSIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solo se contabiliza un documento CLASSIFIED (esta en {doc.status.value})",
        )
    # Import local para no acoplar la carga del router con Celery.
    from contaflow.workers.tasks import post_document_task

    post_document_task.delay(str(document_id))
    return {"status": "queued", "document_id": str(document_id)}
