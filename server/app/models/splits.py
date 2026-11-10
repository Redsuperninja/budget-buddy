"""The parts of a split transaction (ADR-0017). Amounts are integer cents."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin


class TransactionSplit(TimestampMixin, Base):
    """One part of a transaction that covers several categories.

    A transaction with parts is split; its own ``category_id`` is then NULL and ignored. The
    parts add up to its amount exactly and share its sign; SQLite can't check a sum across rows,
    so ``services/ledger/splits.py`` enforces that. The amount isn't encrypted (like
    ``transactions.amount_cents``); the note is.
    """

    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    amount_cents: Mapped[int]
    note: Mapped[str | None] = mapped_column(EncryptedString("transaction_splits.note"))

    transaction = relationship("Transaction", back_populates="splits")
