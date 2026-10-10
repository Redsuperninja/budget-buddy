"""Donations added automatically for a payment to a charity you gave to before

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-09 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("donations") as batch:
        batch.add_column(sa.Column("auto_added", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("donations") as batch:
        batch.drop_column("auto_added")
