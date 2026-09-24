"""posting: enlace entre nuestro documento y el account.move creado en Odoo.

Un asiento contabilizado jamas se edita ni se borra; una correccion es un asiento
reverso (otro posting) referenciado por reversed_by. Aqui solo guardamos el puente,
nunca replicamos la contabilidad de Odoo.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import TimestampMixin, UUIDPkMixin


class Posting(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "posting"
    __table_args__ = (
        # Un mismo account.move de Odoo no debe enlazarse dos veces.
        UniqueConstraint("odoo_move_id", name="uq_posting_odoo_move_id"),
        Index("ix_posting_document_id", "document_id"),
    )

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

    # id del account.move en Odoo (entero de su ORM).
    odoo_move_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Si este posting fue reversado, apunta al posting del asiento reverso.
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posting.id", ondelete="RESTRICT"),
        nullable=True,
    )
