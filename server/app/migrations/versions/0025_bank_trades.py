"""Stock trades seen in a bank file with their deposit sweeps, and the ticker for each company

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-09 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "bank_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("sweep_transaction_id", sa.Integer(), nullable=True),
        sa.Column("security", sa.String(length=100), nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name="fk_bank_trades_transaction_id_transactions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sweep_transaction_id"],
            ["transactions.id"],
            name="fk_bank_trades_sweep_transaction_id_transactions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bank_trades"),
        sa.UniqueConstraint("transaction_id", name="uq_bank_trades_transaction_id"),
        sa.UniqueConstraint("sweep_transaction_id", name="uq_bank_trades_sweep_transaction_id"),
    )
    op.create_table(
        "security_symbols",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_security_symbols"),
        sa.UniqueConstraint("security", name="uq_security_symbols_security"),
    )


def downgrade() -> None:
    op.drop_table("security_symbols")
    op.drop_table("bank_trades")
