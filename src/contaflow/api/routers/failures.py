"""Cola de fallidos (dead-letter): listar y marcar como atendidos. Multi-tenant."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.db import get_async_session
from contaflow.models.ingestion_failure import IngestionFailure
from contaflow.models.user import User
from contaflow.schemas.failure import IngestionFailureOut

router = APIRouter(prefix="/failures", tags=["failures"])


@router.get("", response_model=list[IngestionFailureOut])
async def list_failures(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    resolved: bool | None = Query(default=None),
) -> list[IngestionFailure]:
    query = select(IngestionFailure).where(IngestionFailure.tenant_id == current_user.tenant_id)
    if resolved is True:
        query = query.where(IngestionFailure.resolved_at.is_not(None))
    elif resolved is False:
        query = query.where(IngestionFailure.resolved_at.is_(None))
    result = await session.scalars(query.order_by(IngestionFailure.created_at.desc()))
    return list(result)


@router.post("/{failure_id}/resolve", response_model=IngestionFailureOut)
async def resolve_failure(
    failure_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> IngestionFailure:
    failure = await session.get(IngestionFailure, failure_id)
    if failure is None or failure.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fallo no encontrado")
    failure.resolved_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(failure)
    return failure
