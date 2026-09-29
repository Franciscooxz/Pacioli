"""Schemas de empresas cliente.

Las credenciales (Odoo/IMAP) se ACEPTAN al crear/editar pero NUNCA se devuelven: el
modelo las cifra en reposo (EncryptedStr) y las salidas solo exponen flags de presencia.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class CompanyOut(BaseModel):
    """Salida de listado: datos basicos + flags de configuracion."""

    id: uuid.UUID
    name: str
    nit: str
    active: bool
    has_odoo: bool
    has_imap: bool


class CompanyDetailOut(BaseModel):
    """Detalle para editar. Incluye urls/usuarios (no secretos) pero NUNCA las contrasenas."""

    id: uuid.UUID
    name: str
    nit: str
    active: bool
    odoo_url: str | None
    odoo_db: str | None
    odoo_username: str | None
    imap_host: str | None
    imap_port: int | None
    imap_username: str | None
    posting_config: dict[str, Any] | None
    has_odoo_password: bool
    has_imap_password: bool


class CompanyCreate(BaseModel):
    name: str
    nit: str
    active: bool = True
    odoo_url: str | None = None
    odoo_db: str | None = None
    odoo_username: str | None = None
    odoo_password: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_password: str | None = None
    posting_config: dict[str, Any] | None = None


class CompanyUpdate(BaseModel):
    # Todos opcionales: se aplica solo lo enviado (exclude_unset). Una contrasena en blanco
    # no debe enviarse desde el cliente (se deja como esta).
    name: str | None = None
    nit: str | None = None
    active: bool | None = None
    odoo_url: str | None = None
    odoo_db: str | None = None
    odoo_username: str | None = None
    odoo_password: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_password: str | None = None
    posting_config: dict[str, Any] | None = None
