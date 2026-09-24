"""Tests de observabilidad: formateador JSON, request_id y endpoints de infra."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from contaflow.api.deps import check_minio, check_postgres, check_redis
from contaflow.api.main import app
from contaflow.core.logging import JsonFormatter, request_id_ctx


def test_json_formatter_campos_basicos() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "contaflow.test", logging.INFO, __file__, 10, "hola %s", ("mundo",), None
    )
    data = json.loads(formatter.format(record))
    assert data["level"] == "INFO"
    assert data["logger"] == "contaflow.test"
    assert data["msg"] == "hola mundo"
    assert "ts" in data


def test_json_formatter_incluye_request_id() -> None:
    formatter = JsonFormatter()
    token = request_id_ctx.set("abc123")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "m", None, None)
        data = json.loads(formatter.format(record))
    finally:
        request_id_ctx.reset(token)
    assert data["request_id"] == "abc123"


def test_respuesta_incluye_request_id() -> None:
    app.dependency_overrides[check_postgres] = lambda: True
    app.dependency_overrides[check_redis] = lambda: True
    app.dependency_overrides[check_minio] = lambda: True
    try:
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID")
    finally:
        app.dependency_overrides.clear()


def test_respeta_request_id_entrante() -> None:
    app.dependency_overrides[check_postgres] = lambda: True
    app.dependency_overrides[check_redis] = lambda: True
    app.dependency_overrides[check_minio] = lambda: True
    try:
        with TestClient(app) as client:
            resp = client.get("/health", headers={"X-Request-ID": "mi-id-fijo"})
        assert resp.headers.get("X-Request-ID") == "mi-id-fijo"
    finally:
        app.dependency_overrides.clear()


def test_metrics_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "# " in resp.text  # formato de exposicion Prometheus
