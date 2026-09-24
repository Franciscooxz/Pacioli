"""ingestion_failure: cola de fallidos (dead-letter) del pipeline de ingesta.

Registra los fallos TERMINALES —los que ya agotaron reintentos, o un correo que ni
siquiera pudo abrirse— con el contexto suficiente para inspeccionarlos y reprocesarlos a
mano. Redis (nuestro broker) no tiene dead-letter nativo; esta tabla lo suple.

No es append-only (a diferencia de document_event): `resolved_at` permite marcar un fallo
como atendido sin borrar la evidencia. Todos los FK son nullable porque un fallo muy
temprano (un correo que no se pudo abrir) puede no tener aun documento asociado.
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
from contaflow.models.enums import FailureStage


class IngestionFailure(UUIDPkMixin, Base):
    __tablename__ = "ingestion_failure"
    __table_args__ = (
        # Para listar los fallos recientes de una empresa.
        Index("ix_ingestion_failure_company_created", "company_id", "created_at"),
        Index("ix_ingestion_failure_stage", "stage"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=True,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_document.id", ondelete="RESTRICT"),
        nullable=True,
    )

    stage: Mapped[FailureStage] = mapped_column(
        PGEnum(FailureStage, name="failure_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    task_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # uid del correo (fallo de correo) o id de la tarea Celery (fallo de tarea).
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    # URI en MinIO del crudo (correo/adjunto) para inspeccion posterior.
    raw_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Se rellena cuando un humano ya atendio el fallo (no se borra la evidencia).
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
