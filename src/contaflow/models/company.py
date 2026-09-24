"""company: cada empresa cliente de la firma contable.

Guarda las credenciales de Odoo e IMAP cifradas en reposo (EncryptedStr -> BYTEA).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.core.security import EncryptedStr
from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin


class Company(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "company"
    __table_args__ = (
        # El NIT de la empresa es unico dentro de cada firma, no globalmente.
        UniqueConstraint("tenant_id", "nit", name="uq_company_tenant_nit"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    nit: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Credenciales de Odoo (cifradas) ---
    odoo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    odoo_db: Mapped[str | None] = mapped_column(String(200), nullable=True)
    odoo_username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    odoo_password: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)

    # --- Buzon IMAP de ingesta (credenciales cifradas) ---
    imap_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imap_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imap_password: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)

    # Cuentas del PUC para armar los asientos (payable, iva, retefuente, reteiva,
    # reteica, journal_code). Se lee al contabilizar en Odoo.
    posting_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
