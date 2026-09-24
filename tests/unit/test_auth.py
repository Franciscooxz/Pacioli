"""Tests de las utilidades de auth (hashing y tokens JWT), sin base de datos."""

from __future__ import annotations

import uuid

import pytest

from contaflow.core.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_y_verify_password() -> None:
    h = hash_password("secreto-123")
    assert h != "secreto-123"  # nunca texto plano
    assert verify_password(h, "secreto-123") is True
    assert verify_password(h, "otra-cosa") is False


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id, tenant_id, "ADMIN")
    payload = decode_token(token, "access")
    assert payload["sub"] == str(user_id)
    assert payload["tid"] == str(tenant_id)
    assert payload["role"] == "ADMIN"


def test_refresh_token_no_sirve_como_access() -> None:
    token = create_refresh_token(uuid.uuid4())
    with pytest.raises(TokenError):
        decode_token(token, "access")


def test_token_basura_lanza_error() -> None:
    with pytest.raises(TokenError):
        decode_token("no-es-un-token", "access")
