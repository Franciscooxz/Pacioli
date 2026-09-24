"""Inicializacion de Sentry (opt-in) y del logging, compartida por API y worker.

Sentry solo se activa si hay SENTRY_DSN; sin el, todo es no-op. Nunca enviamos PII
(send_default_pii=False) para respetar la regla de no filtrar NITs ni datos de nomina.
"""

from __future__ import annotations

from contaflow.config import get_settings
from contaflow.core.logging import configure_logging


def setup_observability() -> None:
    """Configura logging y, si hay DSN, inicializa Sentry. Llamar al arrancar."""
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    if not settings.sentry_dsn:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,  # no enviar datos personales
        traces_sample_rate=0.0,
    )
