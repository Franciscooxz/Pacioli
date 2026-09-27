"""posting.is_reversal

Revision ID: e5f3b2a7c1d0
Revises: d4e2a1c9f6b8
Create Date: 2026-09-27 10:00:00.000000

Nota: marca los asientos de reverso para distinguirlos de los originales (permite
re-contabilizar un documento reversado sin chocar con la idempotencia).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f3b2a7c1d0"
down_revision: str | None = "d4e2a1c9f6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "posting",
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("posting", "is_reversal")
