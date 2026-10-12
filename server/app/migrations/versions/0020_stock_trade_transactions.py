"""Stock purchases and sales linked to the transaction that paid for them

``stock_lots.transaction_id`` and ``stock_sale_orders.transaction_id``: the bank or brokerage
transaction a purchase or sale was classified from on the Transactions page. No foreign keys
(adding one would mean rebuilding these tables, which ``stock_sales`` points at); deleting the
transaction clears the link in services/ledger/transactions.py.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-09 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("stock_lots", "stock_sale_orders")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("transaction_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_transaction_id", table, ["transaction_id"], unique=True)


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_transaction_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("transaction_id")
