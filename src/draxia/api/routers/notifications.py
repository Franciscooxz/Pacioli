"""Resumen de notificaciones in-app: contadores de lo que requiere atencion.

Son contadores derivados en vivo (no una tabla de notificaciones): documentos por
revisar, asignados al usuario actual y fallos de ingesta sin resolver. Multi-tenant,
con filtro opcional por empresa activa.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from draxia.api.deps import get_current_user
from draxia.db import get_async_session
from draxia.models.enums import DocumentStatus
from draxia.models.ingestion_failure import IngestionFailure
from draxia.models.source_document import SourceDocument
from draxia.models.user import User
from draxia.schemas.notification import NotificationSummary

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Estados que aun requieren una accion humana.
_REVIEWABLE = (DocumentStatus.PENDING_REVIEW, DocumentStatus.CLASSIFIED)


@router.get("/summary", response_model=NotificationSummary)
async def notification_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    company_id: uuid.UUID | None = Query(default=None),
) -> NotificationSummary:
    pending_q = (
        select(func.count())
        .select_from(SourceDocument)
        .where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.status == DocumentStatus.PENDING_REVIEW,
        )
    )
    mine_q = (
        select(func.count())
        .select_from(SourceDocument)
        .where(
            SourceDocument.tenant_id == current_user.tenant_id,
            SourceDocument.assigned_user_id == current_user.id,
            SourceDocument.status.in_(_REVIEWABLE),
        )
    )
    failures_q = (
        select(func.count())
        .select_from(IngestionFailure)
        .where(
            IngestionFailure.tenant_id == current_user.tenant_id,
            IngestionFailure.resolved_at.is_(None),
        )
    )
    if company_id is not None:
        pending_q = pending_q.where(SourceDocument.company_id == company_id)
        mine_q = mine_q.where(SourceDocument.company_id == company_id)
        failures_q = failures_q.where(IngestionFailure.company_id == company_id)

    return NotificationSummary(
        pending_review=await session.scalar(pending_q) or 0,
        assigned_to_me=await session.scalar(mine_q) or 0,
        failures=await session.scalar(failures_q) or 0,
    )
