"""Endpoints de documentos: listado, detalle y revision humana.

Aislamiento multi-tenant estricto: toda consulta filtra por el tenant del usuario.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from draxia.api.deps import get_current_user
from draxia.db import get_async_session
from draxia.models.document_event import DocumentEvent
from draxia.models.document_line import DocumentLine
from draxia.models.document_tax import DocumentTax
from draxia.models.enums import ActorType, DocumentEventType, DocumentStatus
from draxia.models.rule import ClassificationRule
from draxia.models.source_document import SourceDocument
from draxia.models.user import User
from draxia.schemas.document import (
    ApproveRequest,
    BulkRequest,
    BulkResult,
    DocumentDetailOut,
    DocumentOut,
    EventOut,
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


@router.post("/bulk/approve", response_model=BulkResult)
async def bulk_approve(
    body: BulkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BulkResult:
    """Aprueba en lote: usa la cuenta propuesta de cada documento. Omite los que no aplican."""
    docs = await session.scalars(
        select(SourceDocument).where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.id.in_(body.ids),
        )
    )
    processed = 0
    skipped = 0
    for doc in docs:
        if doc.status in _REVIEWABLE and doc.proposed_account_code:
            doc.classification_confidence = Decimal("1.0")
            doc.status = DocumentStatus.CLASSIFIED
            session.add(
                _user_event(
                    doc,
                    current_user,
                    DocumentEventType.CLASSIFIED,
                    {"account_code": doc.proposed_account_code, "source": "human_bulk"},
                )
            )
            processed += 1
        else:
            skipped += 1
    await session.commit()
    return BulkResult(processed=processed, skipped=skipped)


@router.post("/bulk/reject", response_model=BulkResult)
async def bulk_reject(
    body: BulkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> BulkResult:
    """Rechaza en lote los documentos que estan en revision/clasificados."""
    docs = await session.scalars(
        select(SourceDocument).where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.id.in_(body.ids),
        )
    )
    processed = 0
    skipped = 0
    for doc in docs:
        if doc.status in _REVIEWABLE:
            doc.status = DocumentStatus.REJECTED
            session.add(
                _user_event(
                    doc,
                    current_user,
                    DocumentEventType.REJECTED,
                    {"reason": body.reason, "source": "human_bulk"},
                )
            )
            processed += 1
        else:
            skipped += 1
    await session.commit()
    return BulkResult(processed=processed, skipped=skipped)


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


@router.get("/{document_id}/events", response_model=list[EventOut])
async def list_document_events(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[DocumentEvent]:
    doc = await _get_owned_document(session, current_user, document_id)
    events = await session.scalars(
        select(DocumentEvent)
        .where(DocumentEvent.document_id == doc.id)
        .order_by(DocumentEvent.created_at)
    )
    return list(events)


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
    from draxia.workers.tasks import post_document_task

    post_document_task.delay(str(document_id))
    return {"status": "queued", "document_id": str(document_id)}


@router.post("/{document_id}/reverse", status_code=status.HTTP_202_ACCEPTED)
async def reverse_document_endpoint(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Encola el reverso en Odoo (asiento inverso) de un documento POSTED."""
    doc = await _get_owned_document(session, current_user, document_id)
    if doc.status is not DocumentStatus.POSTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solo se reversa un documento POSTED (esta en {doc.status.value})",
        )
    from draxia.workers.tasks import reverse_document_task

    reverse_document_task.delay(str(document_id))
    return {"status": "queued", "document_id": str(document_id)}
