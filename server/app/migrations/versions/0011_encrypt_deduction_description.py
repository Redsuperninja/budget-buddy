"""Encrypt deduction descriptions

A deduction's description is free text that can hold health details ("Dentist", "Chemo"), so it is
encrypted like the notes fields (ADR-0003). Existing text is encrypted in place, and the
downgrade decrypts it again. As in 0003, the declared SQL type stays as it is: SQLite keeps the
ciphertext bytes in the VARCHAR column, and rebuilding the table isn't needed.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-07 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.crypto.errors import EncryptionError
from app.crypto.fields import get_field_cipher

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEXT = "deductions.description"


def _rewrite(convert) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, description FROM deductions WHERE description IS NOT NULL")
    ).all()
    if not rows:
        return
    cipher = get_field_cipher(bind.dialect)
    if cipher is None:
        raise EncryptionError(
            "This update needs the encryption key, but the database was opened without it."
        )
    update = sa.text("UPDATE deductions SET description = :value WHERE id = :id")
    for row_id, value in rows:
        bind.execute(update, {"id": row_id, "value": convert(cipher, value)})


def _encrypt(cipher, value) -> bytes:
    if isinstance(value, bytes):  # text that was saved as a BLOB
        value = value.decode("utf-8")
    return cipher.encrypt(value, CONTEXT)


def upgrade() -> None:
    _rewrite(_encrypt)


def downgrade() -> None:
    _rewrite(lambda cipher, value: cipher.decrypt(value, CONTEXT))
