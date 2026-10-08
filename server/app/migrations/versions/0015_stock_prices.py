"""Stock prices you type in, to show what your holdings are worth

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-08 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_prices",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_cents >= 0", name="ck_stock_prices_price_not_negative"),
        sa.PrimaryKeyConstraint("symbol", name="pk_stock_prices"),
    )


def downgrade() -> None:
    op.drop_table("stock_prices")
