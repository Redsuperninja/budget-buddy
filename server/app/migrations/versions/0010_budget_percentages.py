"""Percentage budgets

A category's budget can be a share of monthly income (``budget_percent_bp``, basis points), and
a one-row ``budget_plan`` table holds the planned monthly income those shares are taken from.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch:
        batch.add_column(sa.Column("budget_percent_bp", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_categories_budget_percent_range",
            "budget_percent_bp IS NULL OR budget_percent_bp BETWEEN 1 AND 10000",
        )
    op.create_table(
        "budget_plan",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_income_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_budget_plan"),
    )


def downgrade() -> None:
    op.drop_table("budget_plan")
    with op.batch_alter_table("categories") as batch:
        batch.drop_constraint("ck_categories_budget_percent_range", type_="check")
        batch.drop_column("budget_percent_bp")
