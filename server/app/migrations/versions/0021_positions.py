"""Positions from a broker's file: what each account held on a day (a snapshot)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-09 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("shares_micro", sa.Integer(), nullable=False),
        sa.Column("cost_basis_cents", sa.Integer(), nullable=True),
        sa.Column("value_cents", sa.Integer(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("shares_micro > 0", name="ck_positions_shares_positive"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_positions_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_positions"),
        sa.UniqueConstraint("account_id", "symbol", name="uq_positions_account_id_symbol"),
    )


def downgrade() -> None:
    op.drop_table("positions")
