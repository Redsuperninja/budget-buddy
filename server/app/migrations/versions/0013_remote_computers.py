"""Other computers on the home network (ADR-0009)

A table of computers allowed to use the dashboard over the home network. Only a hash of each
computer's cookie token is stored; removing a computer clears it.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-08 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remote_computers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("joined_from", sa.String(length=45), nullable=False),
        sa.Column("paired_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_remote_computers"),
        sa.UniqueConstraint("token_hash", name="uq_remote_computers_token_hash"),
    )


def downgrade() -> None:
    op.drop_table("remote_computers")
