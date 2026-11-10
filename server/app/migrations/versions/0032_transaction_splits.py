"""Transaction splits: one transaction in several categories (ADR-0017, roadmap 10f-1)

Adds ``transaction_splits``: the parts of a split transaction, each with a category, an amount in
cents and an optional note (encrypted, like ``transactions.notes``, so stored as bytes). A
transaction with no parts is unchanged. Deleting a transaction deletes its parts; a category a
part uses can't be deleted (the foreign key has no ``ondelete``, and the app checks first).

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-10 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("note", sa.LargeBinary(), nullable=True),  # encrypted (ADR-0003)
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transaction_splits_transaction_id_transactions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transaction_splits_category_id_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_splits")),
    )
    op.create_index(
        op.f("ix_transaction_splits_transaction_id"), "transaction_splits", ["transaction_id"]
    )
    op.create_index(
        op.f("ix_transaction_splits_category_id"), "transaction_splits", ["category_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_transaction_splits_category_id"), table_name="transaction_splits")
    op.drop_index(op.f("ix_transaction_splits_transaction_id"), table_name="transaction_splits")
    op.drop_table("transaction_splits")
