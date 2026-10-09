"""Live stock prices from Finnhub (ADR-0010)

``price_feed`` holds whether it's on and the Finnhub key (encrypted, like other secret columns).
``stock_prices`` gets where each price came from (``you`` or ``feed``) and when it was fetched.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-09 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_feed",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("api_key", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_price_feed"),
    )
    op.add_column(
        "stock_prices", sa.Column("source", sa.String(8), server_default="you", nullable=False)
    )
    op.add_column("stock_prices", sa.Column("fetched_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("stock_prices", "fetched_at")
    op.drop_column("stock_prices", "source")
    op.drop_table("price_feed")
