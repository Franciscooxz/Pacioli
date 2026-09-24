"""Task base de Celery que envia los fallos terminales a la cola de fallidos.

Celery llama a `on_failure` una sola vez, cuando la tarea falla de verdad: tras agotar
los reintentos de `autoretry_for`, o ante una excepcion que no se reintenta. Los
reintentos intermedios pasan por `on_retry`, no por aqui. Asi cada fila de
`ingestion_failure` es un fallo terminal, no ruido de reintentos.

Los fallos de datos que el pipeline ya maneja (XML corrupto -> PARSE_FAILED) no lanzan
excepcion, asi que no llegan aqui: son resultados esperados, no fallos.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from celery import Task

from contaflow.core.dead_letter import record_failure, resolve_document_context
from contaflow.db import SyncSessionLocal
from contaflow.models.company import Company
from contaflow.models.enums import FailureStage

logger = logging.getLogger(__name__)

# Etapa que representa cada tarea. INGEST recibe un company_id como primer argumento;
# el resto recibe un document_id (de ahi se resuelve la empresa y el tenant).
_STAGE_BY_TASK: dict[str, FailureStage] = {
    "contaflow.workers.tasks.ingest_company": FailureStage.INGEST,
    "contaflow.workers.tasks.parse_document": FailureStage.PARSE,
    "contaflow.workers.tasks.classify_document": FailureStage.CLASSIFY,
    "contaflow.workers.tasks.llm_suggest": FailureStage.LLM_SUGGEST,
    "contaflow.workers.tasks.post_document": FailureStage.POST,
}


class DeadLetterTask(Task):  # type: ignore[misc]  # celery.Task no esta tipado
    """Base para las tareas de ingesta: registra el fallo terminal antes de rendirse."""

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        stage = _STAGE_BY_TASK.get(self.name or "")
        if stage is None:
            return
        arg0 = str(args[0]) if args else None
        try:
            with SyncSessionLocal() as session:
                tenant_id: uuid.UUID | None = None
                company_id: uuid.UUID | None = None
                document_id: uuid.UUID | None = None
                if stage is FailureStage.INGEST and arg0:
                    company_id = uuid.UUID(arg0)
                    company = session.get(Company, company_id)
                    tenant_id = company.tenant_id if company is not None else None
                elif arg0:
                    document_id = uuid.UUID(arg0)
                    tenant_id, company_id = resolve_document_context(session, document_id)
                record_failure(
                    session,
                    stage=stage,
                    reason=f"{type(exc).__name__}: {exc}",
                    tenant_id=tenant_id,
                    company_id=company_id,
                    document_id=document_id,
                    task_name=self.name,
                    source_ref=task_id,
                    payload={"args": [str(a) for a in args]},
                )
        except Exception:  # noqa: BLE001 - el dead-letter jamas debe tapar el fallo real
            logger.exception("dead-letter: no se pudo registrar el fallo de %s", self.name)
