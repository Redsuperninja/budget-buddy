"""Auto-categorization rules (roadmap #9)

A rule says "a transaction whose description contains this text goes in this category".

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-07 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_category_rules_category_id_categories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_category_rules"),
        sa.UniqueConstraint("pattern", name="uq_category_rules_pattern"),
    )
    op.create_index("ix_category_rules_category_id", "category_rules", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_category_rules_category_id", table_name="category_rules")
    op.drop_table("category_rules")
