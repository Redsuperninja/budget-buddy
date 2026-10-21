"""Shared by migrations that encrypt (or decrypt) existing columns in place (ADR-0003).

Safe to run twice: on the way up, a value that is already ciphertext for its column is left alone
(it isn't encrypted again); on the way down, a value that is already text is left alone. The
columns' declared SQL types stay as they are (see migration 0003 for why).
"""

import sqlalchemy as sa
from alembic import op

from app.crypto.errors import DecryptionError, EncryptionError
from app.crypto.fields import FIELD_FORMAT_V1, FieldCipher, get_field_cipher


def _is_ciphertext(cipher: FieldCipher, value, context: str) -> bool:
    if not isinstance(value, bytes | bytearray | memoryview):
        return False
    if bytes(value)[:1] != bytes([FIELD_FORMAT_V1]):
        return False
    try:
        cipher.decrypt(bytes(value), context)
    except DecryptionError:
        return False  # text that merely happened to be saved as a BLOB
    return True


def _encrypt(cipher: FieldCipher, value, context: str) -> bytes | None:
    if _is_ciphertext(cipher, value, context):
        return None
    if isinstance(value, bytes):  # text that was saved as a BLOB
        value = value.decode("utf-8")
    return cipher.encrypt(value, context)


def _decrypt(cipher: FieldCipher, value, context: str) -> str | None:
    if isinstance(value, str):
        return None
    return cipher.decrypt(bytes(value), context)


def rewrite_columns(columns: dict[str, list[str]], *, encrypt: bool) -> None:
    """Encrypt (or decrypt) every non-empty value of ``{table: [column, ...]}`` in place."""
    bind = op.get_bind()
    data = {}
    for table, cols in columns.items():
        names = ", ".join(f'"{c}"' for c in cols)
        where = " OR ".join(f'"{c}" IS NOT NULL' for c in cols)
        data[table] = bind.execute(
            sa.text(f'SELECT id, {names} FROM "{table}" WHERE {where}')
        ).all()
    if not any(data.values()):
        return
    cipher = get_field_cipher(bind.dialect)
    if cipher is None:
        raise EncryptionError(
            "This update needs the encryption key, but the database was opened without it."
        )
    convert = _encrypt if encrypt else _decrypt
    for table, cols in columns.items():
        for row_id, *values in data[table]:
            changes = {}
            for column, value in zip(cols, values, strict=True):
                if value is None:
                    continue
                new = convert(cipher, value, f"{table}.{column}")
                if new is not None:
                    changes[column] = new
            if changes:
                sets = ", ".join(f'"{c}" = :{c}' for c in changes)
                bind.execute(
                    sa.text(f'UPDATE "{table}" SET {sets} WHERE id = :id'),
                    {"id": row_id, **changes},
                )
