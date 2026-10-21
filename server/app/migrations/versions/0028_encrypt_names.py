"""Encrypt organization, employer, institution, and merchant names (issue #28, ADR-0003)

``donations.organization`` (can reveal religion or politics), ``paychecks.employer``,
``accounts.institution`` and ``receipts.merchant`` become AES-256-GCM ciphertext. Nothing filters,
sorts, groups, or compares on them in SQL, so they can be encrypted (``accounts.name`` can't: the
account lists are sorted by it in SQL). Existing text is encrypted in place, and the downgrade
decrypts it again. As in 0003, the declared SQL types stay as they are (SQLite keeps bytes in a
VARCHAR column as-is), so no table is rebuilt.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-20 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.crypto.errors import EncryptionError
from app.crypto.fields import FieldCipher, get_field_cipher

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENCRYPTED_COLUMNS: dict[str, str] = {
    "donations": "organization",
    "paychecks": "employer",
    "accounts": "institution",
    "receipts": "merchant",
}


def _rewrite(convert) -> None:
    bind = op.get_bind()
    data = {
        table: bind.execute(
            sa.text(f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL')
        ).all()
        for table, column in ENCRYPTED_COLUMNS.items()
    }
    if not any(data.values()):
        return
    cipher = get_field_cipher(bind.dialect)
    if cipher is None:
        raise EncryptionError(
            "This update needs the encryption key, but the database was opened without it."
        )
    for table, column in ENCRYPTED_COLUMNS.items():
        update = sa.text(f'UPDATE "{table}" SET "{column}" = :value WHERE id = :id')
        for row_id, value in data[table]:
            bind.execute(update, {"id": row_id, "value": convert(cipher, value, table, column)})


def _encrypt(cipher: FieldCipher, value, table: str, column: str) -> bytes:
    if isinstance(value, bytes):  # text that was saved as a BLOB
        value = value.decode("utf-8")
    return cipher.encrypt(value, f"{table}.{column}")


def _decrypt(cipher: FieldCipher, value, table: str, column: str) -> str:
    return cipher.decrypt(value, f"{table}.{column}")


def upgrade() -> None:
    _rewrite(_encrypt)


def downgrade() -> None:
    _rewrite(_decrypt)
