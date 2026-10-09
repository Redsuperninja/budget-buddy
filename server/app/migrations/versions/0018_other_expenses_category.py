"""Add an "Other Expenses" category

A catch-all for spending that fits no other category, next to the starter "Other Income". It's in
the wants group with no budget. Skipped if you already have a category with that name (names are
unique, ignoring upper and lower case here too).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-08 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "Other Expenses"


def upgrade() -> None:
    # One statement (no reading first), so it also works in offline SQL mode.
    op.execute(
        sa.text(
            'INSERT INTO categories (name, "group", budget_cents) '
            "SELECT :name, 'wants', 0 "
            "WHERE NOT EXISTS (SELECT 1 FROM categories WHERE lower(name) = lower(:name))"
        ).bindparams(name=NAME)
    )


def downgrade() -> None:
    # Only when it still looks like the one added here and nothing uses it, so a category you
    # made yourself (or have since used) is never deleted.
    op.execute(
        sa.text(
            "DELETE FROM categories WHERE name = :name AND \"group\" = 'wants' "
            "AND budget_cents = 0 AND budget_percent_bp IS NULL "
            "AND id NOT IN (SELECT category_id FROM transactions WHERE category_id IS NOT NULL) "
            "AND id NOT IN (SELECT category_id FROM category_rules)"
        ).bindparams(name=NAME)
    )
