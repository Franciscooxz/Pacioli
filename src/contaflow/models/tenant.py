"""tenant: la firma contable (nuestro cliente que paga)."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin


class Tenant(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tenant"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # NIT de la firma contable (opcional; algunas operan como persona natural).
    nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
