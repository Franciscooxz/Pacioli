"""Schemas de reportes contables (agregados sobre source_document)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class MonthBucket(BaseModel):
    month: str  # 'YYYY-MM'
    count: int
    total: Decimal


class ReportSummary(BaseModel):
    count: int
    subtotal: Decimal
    total_tax: Decimal
    total_withholding: Decimal
    total: Decimal
    by_status: dict[str, int]
    by_month: list[MonthBucket]
