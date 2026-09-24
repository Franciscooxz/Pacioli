"""classification_rule: reglas deterministas de clasificacion contable.

El motor de reglas resuelve el 70-80% de los documentos antes de recurrir a ML/LLM.
Una regla dice: para esta empresa y este emisor (o patron), usa esta cuenta del PUC.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin


class ClassificationRule(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "classification_rule"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_classification_rule_confidence_rango",
        ),
        # Consulta tipica: reglas de una empresa, filtradas por emisor, por prioridad.
        Index(
            "ix_classification_rule_company_issuer_priority",
            "company_id",
            "issuer_nit",
            "priority",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # La regla puede matchear por NIT del emisor y/o por un patron de texto.
    issuer_nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_pattern: Mapped[str | None] = mapped_column(String(500), nullable=True)

    account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # confidence 0..1; NUMERIC (no float) para que el valor sea exacto y comparable.
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
