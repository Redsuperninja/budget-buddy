"""Automatic transfer matching: remember transfers you unlinked

``transactions.auto_transfer_off`` is set on both sides when you undo a transfer link, so
automatic matching never links them again. A plain added column (no table rebuild).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-09 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("auto_transfer_off", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("transactions", "auto_transfer_off")
