"""signature_valid en source_document

Revision ID: d4e2a1c9f6b8
Revises: c7b1e8f4a3d9
Create Date: 2026-09-26 10:00:00.000000

Nota (Fase D2): guarda el resultado de la validacion de firma (verify_xades).
None = no verificada / sin firma; False = presente pero invalida; True = integra.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e2a1c9f6b8"
down_revision: str | None = "c7b1e8f4a3d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_document", sa.Column("signature_valid", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_document", "signature_valid")
