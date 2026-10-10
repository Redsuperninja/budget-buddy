"""Import history: each imported file, and what it added, so an import can be undone

``imports`` lists the files (names encrypted, like other personal text). ``transactions``,
``stock_lots``, ``stock_sale_orders`` and ``positions`` get ``import_id`` (no foreign keys, so no
table rebuilds; undoing an import deletes its rows by this id).

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-09 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("transactions", "stock_lots", "stock_sale_orders", "positions")


def upgrade() -> None:
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.LargeBinary(), nullable=False),  # encrypted (ADR-0003)
        sa.Column("rows_added", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_imports_account_id_accounts",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_imports"),
    )
    for table in TABLES:
        op.add_column(table, sa.Column("import_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_import_id", table, ["import_id"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_import_id", table_name=table)
        op.drop_column(table, "import_id")  # SQLite drops a plain column in place
    op.drop_table("imports")
