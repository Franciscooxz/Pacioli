"""CRUD de reglas de clasificacion, con aislamiento multi-tenant."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contaflow.api.deps import get_current_user
from contaflow.db import get_async_session
from contaflow.models.company import Company
from contaflow.models.rule import ClassificationRule
from contaflow.models.user import User
from contaflow.schemas.rule import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"])


async def _get_owned_company(
    session: AsyncSession, tenant_id: uuid.UUID, company_id: uuid.UUID
) -> Company:
    company = await session.get(Company, company_id)
    if company is None or company.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada")
    return company


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ClassificationRule:
    await _get_owned_company(session, current_user.tenant_id, body.company_id)
    rule = ClassificationRule(
        tenant_id=current_user.tenant_id,
        company_id=body.company_id,
        account_code=body.account_code,
        issuer_nit=body.issuer_nit,
        match_pattern=body.match_pattern,
        cost_center=body.cost_center,
        priority=body.priority,
        confidence=body.confidence,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.get("", response_model=list[RuleOut])
async def list_rules(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    company_id: uuid.UUID | None = Query(default=None),
) -> list[ClassificationRule]:
    query = select(ClassificationRule).where(ClassificationRule.tenant_id == current_user.tenant_id)
    if company_id is not None:
        query = query.where(ClassificationRule.company_id == company_id)
    result = await session.scalars(query.order_by(ClassificationRule.priority.desc()))
    return list(result)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ClassificationRule:
    rule = await session.get(ClassificationRule, rule_id)
    if rule is None or rule.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regla no encontrada")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await session.commit()
    await session.refresh(rule)
    return rule
