"""Remember first-start setup progress on the Home Base (roadmap 25e, ADR-0015)

One row (id 1, made when first saved): when setup was finished, when the recovery phrase was
marked as written down, and when the Home Base last wrote a backup file. Dates only.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-20 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "setup_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("phrase_saved_at", sa.DateTime(), nullable=True),
        sa.Column("last_backup_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_setup_progress_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_setup_progress")),
    )


def downgrade() -> None:
    op.drop_table("setup_progress")
