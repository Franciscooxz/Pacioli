"""Listado de empresas cliente de la firma. Solo lectura, sin exponer credenciales."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.db import get_async_session
from contaflow.models.company import Company
from contaflow.models.user import User
from contaflow.schemas.company import CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
async def list_companies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[CompanyOut]:
    result = await session.scalars(
        select(Company).where(Company.tenant_id == current_user.tenant_id).order_by(Company.name)
    )
    return [
        CompanyOut(
            id=c.id,
            name=c.name,
            nit=c.nit,
            active=c.active,
            has_odoo=bool(c.odoo_url and c.odoo_username),
            has_imap=bool(c.imap_host and c.imap_username),
        )
        for c in result
    ]
