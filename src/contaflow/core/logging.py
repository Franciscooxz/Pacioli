"""Logging estructurado en JSON con un id de correlacion por request.

Un log por linea en JSON facilita buscar y agregar en produccion. El request_id se
propaga por un ContextVar, de modo que todas las lineas de una misma peticion comparten
el mismo id sin tener que pasarlo a mano.

Recordatorio de privacidad (CLAUDE.md 4.5): nunca loguear XML completos, NITs de
personas naturales ni datos de nomina. El formateador no filtra por si solo; la
responsabilidad es de quien llama a logging.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Atributos internos de LogRecord que no queremos duplicar como "extra".
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una linea JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = request_id_ctx.get()
        if request_id is not None:
            data["request_id"] = request_id
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        # Cualquier campo pasado via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                data[key] = value
        return json.dumps(data, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """Configura el logger raiz. Idempotente (reemplaza los handlers)."""
    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
