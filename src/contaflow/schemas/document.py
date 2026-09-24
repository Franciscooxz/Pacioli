"""Schemas de salida para documentos."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from contaflow.models.enums import DocType, DocumentStatus, TaxCategory


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: DocumentStatus
    doc_type: DocType | None
    cufe: str | None
    document_number: str | None
    issuer_nit: str | None
    issuer_name: str | None
    total: Decimal | None
    issue_date: date | None
    received_at: datetime
    proposed_account_code: str | None
    classification_confidence: Decimal | None


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_id: str
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class TaxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: TaxCategory
    is_withholding: bool
    tax_name: str
    percent: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    municipality: str | None


class DocumentDetailOut(DocumentOut):
    receiver_nit: str | None
    currency: str
    subtotal: Decimal | None
    total_tax: Decimal | None
    total_withholding: Decimal | None
    proposed_cost_center: str | None
    lines: list[LineOut] = []
    taxes: list[TaxOut] = []


class ApproveRequest(BaseModel):
    account_code: str
    cost_center: str | None = None
    # Si es True, crea una regla para este emisor (aprendizaje).
    create_rule: bool = False


class RejectRequest(BaseModel):
    reason: str | None = None
