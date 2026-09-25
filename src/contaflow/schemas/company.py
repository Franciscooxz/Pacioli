"""Schema de salida para empresas cliente. NUNCA expone credenciales (Odoo/IMAP)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    nit: str
    active: bool
    # Flags de configuracion, sin revelar las credenciales cifradas.
    has_odoo: bool
    has_imap: bool
