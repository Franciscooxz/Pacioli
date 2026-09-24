"""document_tax: un impuesto o retencion del documento.

Modela IVA (is_withholding=False) y retenciones (Retefuente/ReteIVA/ReteICA,
is_withholding=True). El municipio soporta el ICA, que varia por municipio.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import UUIDPkMixin
from contaflow.models.enums import TaxCategory


class DocumentTax(UUIDPkMixin, Base):
    __tablename__ = "document_tax"
    __table_args__ = (Index("ix_document_tax_document_id", "document_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_document.id", ondelete="RESTRICT"),
        nullable=False,
    )

    category: Mapped[TaxCategory] = mapped_column(
        PGEnum(TaxCategory, name="tax_category", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    is_withholding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tax_name: Mapped[str] = mapped_column(String(100), nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    # Municipio para ICA/ReteICA (varia por municipio). Nullable hasta poblarlo.
    municipality: Mapped[str | None] = mapped_column(String(100), nullable=True)
