"""Retirement account types: Roth IRA, traditional IRA, 401(k), Roth 401(k), 403(b) or other

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-09 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("retirement_type", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "retirement_type")
