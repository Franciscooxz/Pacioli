"""Schemas de entrada/salida para las reglas de clasificacion."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Confidence = Annotated[Decimal, Field(ge=0, le=1, max_digits=5, decimal_places=4)]


class RuleCreate(BaseModel):
    company_id: uuid.UUID
    account_code: str
    issuer_nit: str | None = None
    match_pattern: str | None = None
    cost_center: str | None = None
    priority: int = 100
    confidence: Confidence = Decimal("0.90")


class RuleUpdate(BaseModel):
    account_code: str | None = None
    issuer_nit: str | None = None
    match_pattern: str | None = None
    cost_center: str | None = None
    priority: int | None = None
    confidence: Confidence | None = None
    active: bool | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    account_code: str
    issuer_nit: str | None
    match_pattern: str | None
    cost_center: str | None
    priority: int
    confidence: Decimal
    active: bool
