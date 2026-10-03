"""Bank CSV import (roadmap #6)

Adds ``transactions.import_fingerprint`` (so re-importing an overlapping statement skips rows
already imported) and the ``csv_import_mappings`` table (one saved column mapping per account).

Only ``ADD COLUMN``, ``CREATE TABLE`` and ``CREATE INDEX``: none of these makes SQLite rebuild the
``transactions`` table, which with foreign keys on could fire ``ON DELETE SET NULL`` and unlink
transfers and receipts (see 0003). The downgrade uses ``DROP COLUMN`` (SQLite 3.35+) for the
same reason, instead of Alembic's batch mode.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("import_fingerprint", sa.String(64), nullable=True))
    op.create_index(
        "ix_transactions_import_fingerprint", "transactions", ["import_fingerprint"], unique=True
    )
    op.create_table(
        "csv_import_mappings",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("mapping", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_csv_import_mappings_account_id_accounts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", name="pk_csv_import_mappings"),
    )


def downgrade() -> None:
    op.drop_table("csv_import_mappings")
    op.drop_index("ix_transactions_import_fingerprint", table_name="transactions")
    op.execute("ALTER TABLE transactions DROP COLUMN import_fingerprint")
