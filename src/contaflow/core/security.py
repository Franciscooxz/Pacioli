"""Cifrado simetrico de secretos en reposo (credenciales de Odoo e IMAP).

Usamos Fernet (AES-128 en modo CBC + HMAC) de la libreria cryptography. La clave
vive en Settings.fernet_key y NUNCA en el repo. Guardamos solo el ciphertext en la
base: si alguien accede al dump de Postgres, no obtiene las contrasenas.

EncryptedStr es un TypeDecorator: el modelo declara una columna str normal y el
cifrado/descifrado ocurre de forma transparente al escribir/leer. Asi es imposible
que quede texto plano por olvido.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import LargeBinary
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from contaflow.config import get_settings


@lru_cache
def _fernet() -> MultiFernet:
    """MultiFernet para permitir rotacion de clave.

    La primera clave (FERNET_KEY) cifra; las secundarias (FERNET_KEYS_SECONDARY, viejas)
    solo se usan para descifrar. Rotacion: mueve la actual a secundarias, pon una nueva
    en FERNET_KEY, y re-cifra en background; cuando ya no queden datos con la vieja,
    quitala de las secundarias.
    """
    settings = get_settings()
    keys = [Fernet(settings.fernet_key.encode("utf-8"))]
    if settings.fernet_keys_secondary:
        keys.extend(
            Fernet(k.strip().encode("utf-8"))
            for k in settings.fernet_keys_secondary.split(",")
            if k.strip()
        )
    return MultiFernet(keys)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(token).decode("utf-8")


class EncryptedStr(TypeDecorator[str]):
    """Columna de texto cifrada en reposo. Se almacena como BYTEA."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return decrypt(bytes(value))
