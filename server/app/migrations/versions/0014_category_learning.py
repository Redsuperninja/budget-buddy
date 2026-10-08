"""Auto-sort learning: how each category was set, and learned rules

``transactions.category_source`` ("rule" or "you") and ``transactions.sorted_by_rule_id`` say how
a category was set, so auto-sorted transactions can be listed and hand-picked ones learned from.
``category_rules.learned`` marks rules Budget Buddy made from repeated picks.

Plain added columns, no table rebuild: ``transactions`` is pointed at by other tables, so
``sorted_by_rule_id`` has no foreign key (deleting a rule clears it in code). Existing rows get
NULL: their history isn't known.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-08 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("category_source", sa.String(length=8), nullable=True))
    op.add_column("transactions", sa.Column("sorted_by_rule_id", sa.Integer(), nullable=True))
    op.create_index("ix_transactions_sorted_by_rule_id", "transactions", ["sorted_by_rule_id"])
    op.add_column(
        "category_rules",
        sa.Column("learned", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("category_rules", "learned")
    op.drop_index("ix_transactions_sorted_by_rule_id", table_name="transactions")
    op.drop_column("transactions", "sorted_by_rule_id")
    op.drop_column("transactions", "category_source")
