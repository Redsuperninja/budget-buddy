"""Seed default budget categories

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A frozen copy of the categories table, so this migration keeps working if the model changes.
categories = sa.table(
    "categories",
    sa.column("name", sa.String),
    sa.column("group", sa.String),
    sa.column("budget_cents", sa.Integer),
)

DEFAULT_CATEGORIES = {
    "needs": [
        "Rent/Mortgage",
        "Utilities",
        "Groceries",
        "Transportation",
        "Insurance",
        "Healthcare",
    ],
    "wants": ["Dining Out", "Entertainment", "Shopping", "Subscriptions", "Travel"],
    "savings": ["Emergency Fund", "Retirement", "Investments"],
    "income": ["Paycheck", "Interest", "Other Income"],
}


def upgrade() -> None:
    op.bulk_insert(
        categories,
        [
            {"name": name, "group": group, "budget_cents": 0}
            for group, names in DEFAULT_CATEGORIES.items()
            for name in names
        ],
    )


def downgrade() -> None:
    names = [name for group_names in DEFAULT_CATEGORIES.values() for name in group_names]
    op.execute(categories.delete().where(categories.c.name.in_(names)))
