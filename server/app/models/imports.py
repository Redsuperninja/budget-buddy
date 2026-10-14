"""File imports you can look back at and undo (services/imports/history.py)."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin


class ImportBatch(TimestampMixin, Base):
    """One file you imported: a bank file, stock trades, a brokerage activity file or a positions
    file. What it added carries its ``import_id``, so removing it undoes the import."""

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # "bank", "stocks", "activity" or "positions"
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    # As the browser gave it, may be "". Encrypted: bank file names often hold account digits.
    file_name: Mapped[str] = mapped_column(EncryptedString("imports.file_name"))
    rows_added: Mapped[int]
