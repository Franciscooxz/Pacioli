"""document_line: una linea del documento (producto/servicio facturado)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import UUIDPkMixin


class DocumentLine(UUIDPkMixin, Base):
    __tablename__ = "document_line"
    __table_args__ = (Index("ix_document_line_document_id", "document_id"),)

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

    line_id: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
