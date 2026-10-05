"""Paycheck details: health insurance, Roth, and the linked deposit (roadmap #7)

Adds two deduction columns and ``deposit_transaction_id``, the bank deposit a paycheck explains.
One deposit can back only one paycheck (unique index).

SQLite can't add a named foreign key with ``ON DELETE SET NULL`` that it can read back, so the
``paychecks`` table is rebuilt (batch mode). That's safe here, unlike the tables in migration
0003: no other table points at ``paychecks``, so dropping the old copy can't fire any
``ON DELETE`` rule elsewhere. Every row, link, and CHECK rule is copied over (see the tests).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-02 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_AMOUNT_COLUMNS = ("health_insurance_cents", "roth_retirement_cents")


def upgrade() -> None:
    with op.batch_alter_table("paychecks", recreate="always") as batch:
        for column in NEW_AMOUNT_COLUMNS:
            batch.add_column(sa.Column(column, sa.Integer(), server_default="0", nullable=False))
            batch.create_check_constraint(f"{column}_not_negative", f"{column} >= 0")
        batch.add_column(sa.Column("deposit_transaction_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_paychecks_deposit_transaction_id_transactions",
            "transactions",
            ["deposit_transaction_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_paychecks_deposit_transaction_id", ["deposit_transaction_id"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("paychecks", recreate="always") as batch:
        batch.drop_index("ix_paychecks_deposit_transaction_id")
        batch.drop_constraint("fk_paychecks_deposit_transaction_id_transactions", "foreignkey")
        batch.drop_column("deposit_transaction_id")
        for column in NEW_AMOUNT_COLUMNS:
            batch.drop_constraint(op.f(f"ck_paychecks_{column}_not_negative"), "check")
            batch.drop_column(column)
