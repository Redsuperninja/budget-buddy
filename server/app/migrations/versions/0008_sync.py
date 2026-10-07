"""Encrypted sync (roadmap #15, sync contract v1)

Devices get a replay watermark, a new table remembers the request nonces each phone has used,
and receipts uploaded from a phone remember the phone's own ID (so a retry is never added twice)
its tax tag, and which phone sent it.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-07 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(
            sa.Column("nonce_watermark", sa.Integer(), server_default="0", nullable=False)
        )
    with op.batch_alter_table("receipts") as batch:
        batch.add_column(sa.Column("client_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("deduction_kind", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("device_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_receipts_device_id_devices", "devices", ["device_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_unique_constraint("uq_receipts_client_id", ["client_id"])
    op.create_table(
        "seen_nonces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=24), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            name="fk_seen_nonces_device_id_devices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_seen_nonces"),
        sa.UniqueConstraint("device_id", "nonce", name="uq_seen_nonces_device_id"),
    )
    op.create_index("ix_seen_nonces_ts", "seen_nonces", ["device_id", "ts"])


def downgrade() -> None:
    op.drop_index("ix_seen_nonces_ts", table_name="seen_nonces")
    op.drop_table("seen_nonces")
    with op.batch_alter_table("receipts") as batch:
        batch.drop_constraint("uq_receipts_client_id", type_="unique")
        batch.drop_constraint("fk_receipts_device_id_devices", type_="foreignkey")
        batch.drop_column("device_id")
        batch.drop_column("deduction_kind")
        batch.drop_column("client_id")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("nonce_watermark")
