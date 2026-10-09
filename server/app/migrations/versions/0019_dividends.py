"""Dividends found in your transactions, with their deposit sweeps

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-08 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dividends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("sweep_transaction_id", sa.Integer(), nullable=True),
        sa.Column("payer", sa.String(length=100), nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_dividends_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sweep_transaction_id"],
            ["transactions.id"],
            name="fk_dividends_sweep_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dividends"),
        sa.UniqueConstraint("transaction_id", name="uq_dividends_transaction_id"),
        sa.UniqueConstraint("sweep_transaction_id", name="uq_dividends_sweep_transaction_id"),
    )


def downgrade() -> None:
    op.drop_table("dividends")
