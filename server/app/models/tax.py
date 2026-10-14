"""Tax items: donations, dividends, stock lots/sales, and other deductions. Amounts are integer
cents."""

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import DeductionKind, DonationKind

# Share counts can be fractional, so they're stored as whole millionths of a share
# (1.5 shares -> 1_500_000), never as floats. Gains and short/long-term are calculated, not
# stored (see app/services/investing/stock_gains.py).
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
    # Added by Budget Buddy for a repeat payment to a charity you gave to before (repeat_gifts.py).
    auto_added: Mapped[bool] = mapped_column(default=False, server_default="0")


class Dividend(TimestampMixin, Base):
    """A dividend paid into one of your accounts: a money-in transaction that looks like one, and
    the deposit sweep that moved the same cash on (if found). The date and amount are the
    transaction's, so they're never stored twice. See
    app/services/investing/dividend_matching.py."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    # Several can share one sweep (services/investing/combined_sweeps.py).
    sweep_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    payer: Mapped[str] = mapped_column(String(100))  # from the description: "JOHNSON & JOHNSON"
    # Linked by hand ("Deposit sweeps to check"): Match everything again keeps it.
    sweep_by_hand: Mapped[bool] = mapped_column(default=False, server_default="0")
    # "Not a dividend": kept so it isn't found again, but left out of lists and totals.
    dismissed: Mapped[bool] = mapped_column(default=False, server_default="0")


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
    # The transaction it was classified from (Transactions page), if any. No foreign key (see
    # migration 0020); deleting the transaction clears it.
    transaction_id: Mapped[int | None] = mapped_column(Integer, index=True, unique=True)
    import_id: Mapped[int | None] = mapped_column(Integer, index=True)  # the file it came from


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
    # The transaction it was classified from, like ``StockLot.transaction_id``.
    transaction_id: Mapped[int | None] = mapped_column(Integer, index=True, unique=True)
    import_id: Mapped[int | None] = mapped_column(Integer, index=True)  # the file it came from


class StockSale(TimestampMixin, Base):
    """Shares sold out of one lot: the part of a ``StockSaleOrder`` matched to that lot.

    Rebuilt by ``app.services.investing.stock_records.rematch`` whenever a lot or sale of the same
    symbol and account changes, so FIFO order always follows the dates.
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


class Position(TimestampMixin, Base):
    """One line of a broker's positions file: what an account held on ``as_of``. Importing a
    newer file for the account replaces all its lines (a snapshot). Separate from purchase lots,
    so it never changes gains. See app/services/investing/positions.py."""

    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("shares_micro > 0", name="shares_positive"),
        UniqueConstraint("account_id", "symbol", name="uq_positions_account_id_symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(16))
    shares_micro: Mapped[int]
    cost_basis_cents: Mapped[int | None]  # the file's total cost basis, if it has one
    value_cents: Mapped[int | None]  # the file's current value, if it has one
    as_of: Mapped[dt.date] = mapped_column(Date)
    import_id: Mapped[int | None] = mapped_column(Integer, index=True)  # the file it came from


class StockPrice(TimestampMixin, Base):
    """The latest price of a symbol, used to show what your holdings are worth. One row per symbol:
    typed in by you, or fetched from the price feed when you turned it on (ADR-0010)."""

    __tablename__ = "stock_prices"
    __table_args__ = (CheckConstraint("price_cents >= 0", name="price_not_negative"),)

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    price_cents: Mapped[int]  # per share
    as_of: Mapped[dt.date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(8), default="you", server_default="you")  # or "feed"
    fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime)  # UTC, feed prices only


class PriceFeed(TimestampMixin, Base):
    """Live prices from Finnhub (ADR-0010): off until turned on. One row (id 1). Only the symbols
    you hold are ever sent. The key is encrypted at rest and never returned by the API."""

    __tablename__ = "price_feed"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default="0")
    api_key: Mapped[str | None] = mapped_column(EncryptedString("price_feed.api_key"))


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
