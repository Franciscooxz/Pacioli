"""Test del endpoint /health.

Sobreescribimos las sondas de conectividad para no depender de infra real: el
objetivo aqui es validar el contrato del endpoint (codigo y cuerpo), no la
disponibilidad de los servicios (eso se verifica con `docker compose up`).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from contaflow.api.deps import check_minio, check_postgres, check_redis
from contaflow.api.main import app


def test_health_ok_cuando_todo_arriba() -> None:
    app.dependency_overrides[check_postgres] = lambda: True
    app.dependency_overrides[check_redis] = lambda: True
    app.dependency_overrides[check_minio] = lambda: True
    try:
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["services"] == {
            "postgres": "up",
            "redis": "up",
            "minio": "up",
        }
    finally:
        app.dependency_overrides.clear()


def test_health_degradado_cuando_un_servicio_cae() -> None:
    app.dependency_overrides[check_postgres] = lambda: True
    app.dependency_overrides[check_redis] = lambda: False
    app.dependency_overrides[check_minio] = lambda: True
    try:
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["services"]["redis"] == "down"
    finally:
        app.dependency_overrides.clear()
