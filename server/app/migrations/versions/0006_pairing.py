"""Phone pairing (roadmap #14, sync contract v1)

Devices get a platform, app version, revoke time, and an encrypted sync key. New tables hold the
short-lived pairing sessions (QR codes) and the nonces seen in them.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-05 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("platform", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("app_version", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("revoked_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("sync_key", sa.LargeBinary(), nullable=True))

    op.create_table(
        "pairing_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("pair_pub", sa.String(length=43), nullable=False),
        sa.Column("pair_sk", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("exp", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.Integer(), nullable=True),
        sa.Column("wrong_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pairing_sessions"),
    )
    op.create_table(
        "pairing_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["pairing_sessions.id"],
            name="fk_pairing_nonces_session_id_pairing_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pairing_nonces"),
        sa.UniqueConstraint("session_id", "nonce", name="uq_pairing_nonces_session_id"),
    )


def downgrade() -> None:
    op.drop_table("pairing_nonces")
    op.drop_table("pairing_sessions")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("sync_key")
        batch.drop_column("revoked_at")
        batch.drop_column("app_version")
        batch.drop_column("platform")
