"""Encrypt sensitive columns (roadmap #4, ADR-0003)

Account last-4 digits, every notes field, and the receipt file reference become AES-256-GCM
ciphertext. Any existing plain text is encrypted in place, and the downgrade decrypts it again.
Both directions need the data folder's encryption key, which the app gives the database engine
(see ``app.crypto.fields.set_field_cipher``).

The columns' declared SQL types are deliberately left as they are (TEXT/VARCHAR). SQLite keeps a
bytes value in a TEXT column as-is (a BLOB), so nothing needs changing. Changing the type would
mean SQLite rebuilding each table, and with foreign keys switched on that either fails or, worse,
fires the ``ON DELETE SET NULL`` rules and quietly unlinks transfers, receipts, and paychecks.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.crypto.errors import EncryptionError
from app.crypto.fields import FieldCipher, get_field_cipher

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENCRYPTED_COLUMNS: dict[str, list[str]] = {
    "accounts": ["last4", "notes"],
    "transactions": ["notes"],
    "paychecks": ["notes"],
    "receipts": ["image_path", "notes"],
    "donations": ["notes"],
}


def _rows(table: str, columns: list[str]) -> list[sa.Row]:
    cols = ", ".join(f'"{c}"' for c in columns)
    where = " OR ".join(f'"{c}" IS NOT NULL' for c in columns)
    return op.get_bind().execute(sa.text(f'SELECT id, {cols} FROM "{table}" WHERE {where}')).all()


def _cipher(needed: bool) -> FieldCipher | None:
    cipher = get_field_cipher(op.get_bind().dialect)
    if cipher is None and needed:
        raise EncryptionError(
            "This update needs the encryption key, but the database was opened without it."
        )
    return cipher


def _rewrite(convert) -> None:
    """Read every non-empty sensitive value, convert it, and write it back in place."""
    data = {table: _rows(table, cols) for table, cols in ENCRYPTED_COLUMNS.items()}
    cipher = _cipher(needed=any(data.values()))
    bind = op.get_bind()
    for table, columns in ENCRYPTED_COLUMNS.items():
        sets = ", ".join(f'"{c}" = :{c}' for c in columns)
        statement = sa.text(f'UPDATE "{table}" SET {sets} WHERE id = :id')
        for row_id, *values in data[table]:
            params = {
                column: None if value is None else convert(cipher, value, f"{table}.{column}")
                for column, value in zip(columns, values, strict=True)
            }
            bind.execute(statement, {"id": row_id, **params})


def _encrypt(cipher: FieldCipher, value, context: str) -> bytes:
    if isinstance(value, bytes):  # text that was saved as a BLOB
        value = value.decode("utf-8")
    return cipher.encrypt(value, context)


def _decrypt(cipher: FieldCipher, value, context: str) -> str:
    return cipher.decrypt(value, context)


def upgrade() -> None:
    _rewrite(_encrypt)


def downgrade() -> None:
    _rewrite(_decrypt)
