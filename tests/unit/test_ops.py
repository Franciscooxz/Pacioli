"""Tests de operacion (Fase 0.3): rotacion de clave Fernet y proteccion de /metrics."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from contaflow.api.routers.metrics import _token_ok
from contaflow.config import get_settings
from contaflow.core import security


def test_token_metrics_compara_de_forma_segura() -> None:
    assert _token_ok("abc", "abc") is True
    assert _token_ok("abc", "xyz") is False


def test_rotacion_fernet_descifra_con_clave_vieja(monkeypatch: pytest.MonkeyPatch) -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", new_key)
    monkeypatch.setenv("FERNET_KEYS_SECONDARY", old_key)
    get_settings.cache_clear()
    security._fernet.cache_clear()
    try:
        # Un dato cifrado con la clave VIEJA sigue descifrandose tras rotar.
        token_old = Fernet(old_key.encode()).encrypt(b"secreto-odoo")
        assert security.decrypt(token_old) == "secreto-odoo"

        # Lo nuevo se cifra con la clave PRIMARIA (nueva).
        token_new = security.encrypt("secreto-odoo")
        assert Fernet(new_key.encode()).decrypt(token_new) == b"secreto-odoo"
    finally:
        get_settings.cache_clear()
        security._fernet.cache_clear()
