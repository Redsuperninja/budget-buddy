"""Tax items: donations, stock lots/sales, and other deductions. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import DeductionKind, DonationKind

# Share counts can be fractional, so they're stored as whole millionths of a share
# (1.5 shares -> 1_500_000). Gains and short/long-term are calculated, not stored (roadmap #12).
SHARES_SCALE = 1_000_000


class Donation(TimestampMixin, Base):
    __tablename__ = "donations"
    __table_args__ = (CheckConstraint("amount_cents >= 0", name="amount_not_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    organization: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int]  # for goods: fair market value
    kind: Mapped[DonationKind] = mapped_column(str_enum(DonationKind, "donation_kind"))
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(EncryptedString("donations.notes"))


class StockLot(TimestampMixin, Base):
    """Shares bought in one purchase."""

    __tablename__ = "stock_lots"
    __table_args__ = (
        CheckConstraint("shares_micro > 0", name="shares_positive"),
        CheckConstraint("cost_basis_cents >= 0", name="cost_basis_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    shares_micro: Mapped[int]
    acquired_on: Mapped[dt.date] = mapped_column(Date)
    cost_basis_cents: Mapped[int]  # total paid, including fees


class StockSale(TimestampMixin, Base):
    """Shares sold out of one lot."""

    __tablename__ = "stock_sales"
    __table_args__ = (
        CheckConstraint("shares_micro > 0", name="shares_positive"),
        CheckConstraint("proceeds_cents >= 0", name="proceeds_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lots.id"), index=True)
    sold_on: Mapped[dt.date] = mapped_column(Date)
    shares_micro: Mapped[int]
    proceeds_cents: Mapped[int]  # total received, after fees


class Deduction(TimestampMixin, Base):
    __tablename__ = "deductions"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_not_negative"),
        CheckConstraint("tax_year BETWEEN 2000 AND 2100", name="tax_year_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(index=True)
    kind: Mapped[DeductionKind] = mapped_column(str_enum(DeductionKind, "deduction_kind"))
    description: Mapped[str | None] = mapped_column(String(200))
    date: Mapped[dt.date | None] = mapped_column(Date)
    amount_cents: Mapped[int]
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id", ondelete="SET NULL"))
