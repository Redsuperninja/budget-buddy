"""File imports you can look back at and undo (services/imports.py)."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ImportBatch(TimestampMixin, Base):
    """One file you imported: a bank file, stock trades, a brokerage activity file or a positions
    file. What it added carries its ``import_id``, so removing it undoes the import."""

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # "bank", "stocks", "activity" or "positions"
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    file_name: Mapped[str] = mapped_column(String(200))  # as the browser gave it, may be ""
    rows_added: Mapped[int]
