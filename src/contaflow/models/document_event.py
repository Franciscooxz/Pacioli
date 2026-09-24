"""document_event: bitacora append-only del ciclo de vida de cada documento.

Nunca se hace UPDATE ni DELETE sobre esta tabla: es la evidencia de trazabilidad. Un
trigger de PostgreSQL (agregado en la migracion) rechaza ambas operaciones a nivel de
base, no solo en la app. Por eso NO usa TimestampMixin (no hay updated_at).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from contaflow.db import Base
from contaflow.models.base import UUIDPkMixin
from contaflow.models.enums import ActorType, DocumentEventType


class DocumentEvent(UUIDPkMixin, Base):
    __tablename__ = "document_event"
    __table_args__ = (
        # Para reconstruir la linea de tiempo de un documento en orden.
        Index("ix_document_event_document_created", "document_id", "created_at"),
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

    event_type: Mapped[DocumentEventType] = mapped_column(
        PGEnum(
            DocumentEventType,
            name="document_event_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    actor_type: Mapped[ActorType] = mapped_column(
        PGEnum(ActorType, name="actor_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Identificador del usuario cuando actor_type == USER (aun sin tabla de usuarios).
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
