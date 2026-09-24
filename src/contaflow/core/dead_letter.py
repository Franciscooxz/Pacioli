"""Cola de fallidos (dead-letter): registrar fallos terminales del pipeline.

Un fallo terminal es el que ya no se reintenta. En vez de perderse en los logs, queda
una fila en `ingestion_failure` con el contexto para inspeccionarlo y reprocesarlo.

Esta capa es logica de dominio pura (recibe una Session): la usan tanto el pipeline de
ingesta (fallo de correo) como la task base de Celery (fallo de tarea).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from contaflow.models.enums import FailureStage
from contaflow.models.ingestion_failure import IngestionFailure
from contaflow.models.source_document import SourceDocument

logger = logging.getLogger(__name__)


def resolve_document_context(
    session: Session, document_id: uuid.UUID
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Devuelve (tenant_id, company_id) de un documento, o (None, None) si no existe."""
    row = session.execute(
        select(SourceDocument.tenant_id, SourceDocument.company_id).where(
            SourceDocument.id == document_id
        )
    ).first()
    if row is None:
        return None, None
    return row[0], row[1]


def record_failure(
    session: Session,
    *,
    stage: FailureStage,
    reason: str,
    tenant_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    task_name: str | None = None,
    source_ref: str | None = None,
    raw_uri: str | None = None,
    payload: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Inserta una fila en la cola de fallidos y la confirma. Devuelve su id."""
    failure = IngestionFailure(
        tenant_id=tenant_id,
        company_id=company_id,
        document_id=document_id,
        stage=stage,
        reason=reason[:500],
        task_name=task_name,
        source_ref=source_ref,
        raw_uri=raw_uri,
        payload=payload,
    )
    session.add(failure)
    session.commit()
    logger.info("dead-letter: fallo %s registrado (stage=%s)", failure.id, stage.value)
    return failure.id
