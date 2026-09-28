"""reglas: tasas de retencion del comprador

Revision ID: f6a4d8c2b3e1
Revises: e5f3b2a7c1d0
Create Date: 2026-09-28 10:00:00.000000

Nota (retenciones del comprador): tasas por regla (%) para calcular retefuente/reteICA/
reteIVA en compras que no traen retencion en el XML. NULL = no aplica.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a4d8c2b3e1"
down_revision: str | None = "e5f3b2a7c1d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "classification_rule",
        sa.Column("retefuente_rate", sa.Numeric(precision=6, scale=3), nullable=True),
    )
    op.add_column(
        "classification_rule",
        sa.Column("reteica_rate", sa.Numeric(precision=6, scale=3), nullable=True),
    )
    op.add_column(
        "classification_rule",
        sa.Column("reteiva_rate", sa.Numeric(precision=6, scale=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("classification_rule", "reteiva_rate")
    op.drop_column("classification_rule", "reteica_rate")
    op.drop_column("classification_rule", "retefuente_rate")
