"""Automatic transfer matching: remember transfers you unlinked

``transactions.auto_transfer_off`` is set on both sides when you undo a transfer link, so
automatic matching never links them again. ``pre_transfer_*`` keep the category from before a link,
put back on undo. Plain added columns (no table rebuild, so no foreign keys).

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
    op.add_column("transactions", sa.Column("pre_transfer_category_id", sa.Integer()))
    op.add_column("transactions", sa.Column("pre_transfer_category_source", sa.String(8)))
    op.add_column("transactions", sa.Column("pre_transfer_rule_id", sa.Integer()))


def downgrade() -> None:
    for column in (
        "pre_transfer_rule_id",
        "pre_transfer_category_source",
        "pre_transfer_category_id",
        "auto_transfer_off",
    ):
        op.drop_column("transactions", column)
