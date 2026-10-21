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

from app.migrations._encrypt_columns import rewrite_columns

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENCRYPTED_COLUMNS: dict[str, list[str]] = {
    "donations": ["organization"],
    "paychecks": ["employer"],
    "accounts": ["institution"],
    "receipts": ["merchant"],
}


def upgrade() -> None:
    rewrite_columns(ENCRYPTED_COLUMNS, encrypt=True)


def downgrade() -> None:
    rewrite_columns(ENCRYPTED_COLUMNS, encrypt=False)
