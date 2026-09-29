"""Test unitario del mapeo tarea -> etapa de la cola de fallidos (Fase A).

Guarda de regresion: si se agrega una tarea de ingesta con dead-letter, debe quedar
mapeada aqui, o su fallo terminal no se registraria con la etapa correcta.
"""

from __future__ import annotations

from draxia.models.enums import FailureStage
from draxia.workers.dead_letter import _STAGE_BY_TASK


def test_todas_las_tareas_de_ingesta_estan_mapeadas() -> None:
    esperadas = {
        "draxia.workers.tasks.ingest_company": FailureStage.INGEST,
        "draxia.workers.tasks.parse_document": FailureStage.PARSE,
        "draxia.workers.tasks.classify_document": FailureStage.CLASSIFY,
        "draxia.workers.tasks.llm_suggest": FailureStage.LLM_SUGGEST,
        "draxia.workers.tasks.post_document": FailureStage.POST,
        "draxia.workers.tasks.reverse_document": FailureStage.POST,
    }
    assert esperadas == _STAGE_BY_TASK
