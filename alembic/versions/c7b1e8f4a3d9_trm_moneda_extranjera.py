"""trm para moneda extranjera

Revision ID: c7b1e8f4a3d9
Revises: f3a9c1d20b47
Create Date: 2026-09-19 11:00:00.000000

Nota (Fase C): agrega source_document.trm (NUMERIC(19,6)). Los montos se guardan en la
moneda original del documento; la TRM permite convertir a COP al contabilizar en Odoo.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7b1e8f4a3d9"
down_revision: str | None = "f3a9c1d20b47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_document", sa.Column("trm", sa.Numeric(precision=19, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column("source_document", "trm")
