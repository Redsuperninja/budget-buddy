"""Stock trades seen in a bank-style file, and the ticker you gave each company once. See
app/services/investing/bank_trades.py."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BankTrade(TimestampMixin, Base):
    """A buy (money out) or sale (money in) of shares in an investment account, read from
    a description like "ABBOTT LABORATORIES UNSOLICITED WE ARE ACTING AS PRINCIPAL ...", and the
    deposit sweep that moved the same cash (if found). The date, amount and account are the
    transaction's, never copied. The shares, ticker and price live on the stock purchase or sale
    recorded from the transaction (``StockLot`` / ``StockSaleOrder.transaction_id``)."""

    __tablename__ = "bank_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    # Several can share one sweep (services/investing/combined_sweeps.py).
    sweep_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    security: Mapped[str] = mapped_column(String(100))  # "ABBOTT LABORATORIES"
    # Linked by hand ("Deposit sweeps to check"): Match everything again keeps it.
    sweep_by_hand: Mapped[bool] = mapped_column(default=False, server_default="0")
    # "Not a trade": kept so it isn't found again, but left out of lists.
    dismissed: Mapped[bool] = mapped_column(default=False, server_default="0")


class SecuritySymbol(TimestampMixin, Base):
    """The ticker you gave a company's trades once ("ABBOTT LABORATORIES" -> "ABT"), offered again
    for its next trade."""

    __tablename__ = "security_symbols"

    id: Mapped[int] = mapped_column(primary_key=True)
    security: Mapped[str] = mapped_column(String(100), unique=True)
    symbol: Mapped[str] = mapped_column(String(16))
