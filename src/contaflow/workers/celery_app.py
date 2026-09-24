"""Instancia de Celery. Redis es a la vez broker y backend de resultados.

Toda ingesta, parseo y llamada a Odoo corre aqui (regla de asincronia del
CLAUDE.md): el endpoint HTTP encola y devuelve 202, nunca hace el trabajo pesado.
"""

from __future__ import annotations

from celery import Celery

from contaflow.config import get_settings
from contaflow.core.observability import setup_observability

setup_observability()

_settings = get_settings()

celery_app = Celery(
    "contaflow",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["contaflow.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    task_acks_late=True,  # no perder tareas si el worker muere
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # justo para tareas largas de ingesta
    # No dejar que Celery reemplace nuestro logging JSON (setup_observability).
    worker_hijack_root_logger=False,
    beat_schedule={
        # Recorre los buzones de las empresas activas cada 5 minutos.
        "poll-mailboxes": {
            "task": "contaflow.workers.tasks.poll_mailboxes",
            "schedule": 300.0,
        },
    },
)
