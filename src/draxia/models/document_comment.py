"""document_comment: notas de los revisores sobre un documento.

Es una tabla aparte de document_event (la bitacora de sistema append-only): los
comentarios son contenido humano y tienen su propia seccion en la UI. No se editan ni
se borran desde la app, por eso no lleva updated_at. Si el autor se borra, el comentario
se conserva con author_id en NULL (evidencia de la revision).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from draxia.db import Base
from draxia.models.base import UUIDPkMixin


class DocumentComment(UUIDPkMixin, Base):
    __tablename__ = "document_comment"
    __table_args__ = (
        Index("ix_document_comment_document_created", "document_id", "created_at"),
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
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
