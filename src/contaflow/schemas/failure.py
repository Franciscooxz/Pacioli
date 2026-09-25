"""Schema de salida para la cola de fallidos (dead-letter)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from contaflow.models.enums import FailureStage


class IngestionFailureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage: FailureStage
    company_id: uuid.UUID | None
    document_id: uuid.UUID | None
    task_name: str | None
    source_ref: str | None
    reason: str
    raw_uri: str | None
    resolved_at: datetime | None
    created_at: datetime
