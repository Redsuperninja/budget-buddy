"""Remember the filing status that narrows the yearly tax summary (roadmap 25j)

One row (id 1, made when first saved). ``filing_status`` is null until chosen ("Not set: show
all"). Not encrypted: it's one of four fixed words, and the tax summary works the same without it.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-20 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The filing statuses the tax-year data files had when this was written (app/tax_data).
STATUSES = ("single", "married_filing_jointly", "married_filing_separately", "head_of_household")


def upgrade() -> None:
    allowed = ", ".join(f"'{s}'" for s in STATUSES)
    op.create_table(
        "tax_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filing_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_tax_preferences_single_row")),
        sa.CheckConstraint(
            f"filing_status IN ({allowed})", name=op.f("ck_tax_preferences_known_filing_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_preferences")),
    )


def downgrade() -> None:
    op.drop_table("tax_preferences")
