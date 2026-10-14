"""One deposit sweep can pay for several dividends or trades

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-10 12:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("dividends", "bank_trades")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"uq_{table}_sweep_transaction_id", type_="unique")
            batch.create_index(f"ix_{table}_sweep_transaction_id", ["sweep_transaction_id"])


def downgrade() -> None:
    # A sweep shared by several rows can't be unique again: keep it on the first one only.
    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET sweep_transaction_id = NULL "
            "WHERE sweep_transaction_id IS NOT NULL AND id NOT IN ("
            f"SELECT MIN(id) FROM {table} WHERE sweep_transaction_id IS NOT NULL "
            "GROUP BY sweep_transaction_id)"
        )
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_sweep_transaction_id")
            batch.create_unique_constraint(
                f"uq_{table}_sweep_transaction_id", ["sweep_transaction_id"]
            )
