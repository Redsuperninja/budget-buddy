"""Donations from transactions: link a gift to the bank or card payment it came from

Adds ``donations.transaction_id``. One payment can back only one gift (unique index). Deleting the
transaction keeps the gift and clears the link (``ON DELETE SET NULL``), since the gift still
happened.

As in 0005, the table is rebuilt (batch mode) so SQLite keeps the named foreign key with its
``ON DELETE`` rule. No other table points at ``donations``, so dropping the old copy is safe. The
encrypted ``notes`` bytes are copied as they are.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-08 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("donations", recreate="always") as batch:
        batch.add_column(sa.Column("transaction_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_donations_transaction_id_transactions",
            "transactions",
            ["transaction_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_donations_transaction_id", ["transaction_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("donations", recreate="always") as batch:
        batch.drop_index("ix_donations_transaction_id")
        batch.drop_constraint("fk_donations_transaction_id_transactions", "foreignkey")
        batch.drop_column("transaction_id")
