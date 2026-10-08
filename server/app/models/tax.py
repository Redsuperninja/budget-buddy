"""Tax items: donations, stock lots/sales, and other deductions. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import DeductionKind, DonationKind

# Share counts can be fractional, so they're stored as whole millionths of a share
# (1.5 shares -> 1_500_000), never as floats. Gains and short/long-term are calculated, not
# stored (see app/services/stock_gains.py).
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
    # The bank or card payment this gift was (a charity transaction). One payment backs at most
    # one gift; deleting the payment keeps the gift.
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True, unique=True
    )
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


class StockSaleOrder(TimestampMixin, Base):
    """One sale as the user entered it: a symbol, a date, a number of shares, and the money
    received after fees. FIFO matching splits it into ``StockSale`` rows, one per lot used."""

    __tablename__ = "stock_sale_orders"
    __table_args__ = (
        CheckConstraint("shares_micro > 0", name="shares_positive"),
        CheckConstraint("proceeds_cents >= 0", name="proceeds_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    sold_on: Mapped[dt.date] = mapped_column(Date)
    shares_micro: Mapped[int]
    proceeds_cents: Mapped[int]  # total received, after fees


class StockSale(TimestampMixin, Base):
    """Shares sold out of one lot: the part of a ``StockSaleOrder`` matched to that lot.

    Rebuilt by ``app.services.stock_records.rematch`` whenever a lot or sale of the same symbol
    and account changes, so FIFO order always follows the dates.
    """

    __tablename__ = "stock_sales"
    __table_args__ = (
        CheckConstraint("shares_micro > 0", name="shares_positive"),
        CheckConstraint("proceeds_cents >= 0", name="proceeds_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("stock_sale_orders.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lots.id"), index=True)
    sold_on: Mapped[dt.date] = mapped_column(Date)
    shares_micro: Mapped[int]
    proceeds_cents: Mapped[int]  # this lot's share of the order's proceeds


class Deduction(TimestampMixin, Base):
    __tablename__ = "deductions"
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_not_negative"),
        CheckConstraint("tax_year BETWEEN 2000 AND 2100", name="tax_year_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(index=True)
    kind: Mapped[DeductionKind] = mapped_column(str_enum(DeductionKind, "deduction_kind"))
    # Encrypted: it can hold health details (migration 0011).
    description: Mapped[str | None] = mapped_column(EncryptedString("deductions.description"))
    date: Mapped[dt.date | None] = mapped_column(Date)
    amount_cents: Mapped[int]
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id", ondelete="SET NULL"))
