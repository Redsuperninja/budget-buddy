"""Remember which deposit sweeps you linked by hand

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-14 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("dividends", "bank_trades")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column("sweep_by_hand", sa.Boolean(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("sweep_by_hand")
