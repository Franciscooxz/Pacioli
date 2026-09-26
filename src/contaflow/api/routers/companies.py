"""CRUD de empresas cliente de la firma. Multi-tenant; nunca expone credenciales."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.db import get_async_session
from contaflow.models.company import Company
from contaflow.models.user import User
from contaflow.schemas.company import (
    CompanyCreate,
    CompanyDetailOut,
    CompanyOut,
    CompanyUpdate,
)

router = APIRouter(prefix="/companies", tags=["companies"])

_DUP_NIT = "Ya existe una empresa con ese NIT en la firma"


def _to_out(c: Company) -> CompanyOut:
    return CompanyOut(
        id=c.id,
        name=c.name,
        nit=c.nit,
        active=c.active,
        has_odoo=bool(c.odoo_url and c.odoo_username),
        has_imap=bool(c.imap_host and c.imap_username),
    )


async def _owned(session: AsyncSession, user: User, company_id: uuid.UUID) -> Company:
    company = await session.get(Company, company_id)
    if company is None or company.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada")
    return company


@router.get("", response_model=list[CompanyOut])
async def list_companies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[CompanyOut]:
    result = await session.scalars(
        select(Company).where(Company.tenant_id == current_user.tenant_id).order_by(Company.name)
    )
    return [_to_out(c) for c in result]


@router.get("/{company_id}", response_model=CompanyDetailOut)
async def get_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CompanyDetailOut:
    c = await _owned(session, current_user, company_id)
    return CompanyDetailOut(
        id=c.id,
        name=c.name,
        nit=c.nit,
        active=c.active,
        odoo_url=c.odoo_url,
        odoo_db=c.odoo_db,
        odoo_username=c.odoo_username,
        imap_host=c.imap_host,
        imap_port=c.imap_port,
        imap_username=c.imap_username,
        posting_config=c.posting_config,
        has_odoo_password=bool(c.odoo_password),
        has_imap_password=bool(c.imap_password),
    )


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    body: CompanyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CompanyOut:
    company = Company(tenant_id=current_user.tenant_id, **body.model_dump())
    session.add(company)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUP_NIT) from exc
    await session.refresh(company)
    return _to_out(company)


@router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> CompanyOut:
    company = await _owned(session, current_user, company_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUP_NIT) from exc
    await session.refresh(company)
    return _to_out(company)
