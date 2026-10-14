"""Checking your recorded stock purchases and sales against what backs them up.

- **Against the broker's positions file:** for each account with one, the shares your purchases
  minus sales add up to on the file's day, per symbol, both ways: every symbol in the file, and
  any symbol you hold by your records that the file doesn't list (``Snapshot.compare``).
- **Each purchase and sale** is checked (``checked_by``) when it's linked to a transaction (a bank
  or brokerage line), or when the account's positions file agrees for that symbol (the same
  shares, or none on both sides) and is dated on or after it. Otherwise it's not verified yet.
- **Trades from a bank file still waiting for their shares** (``bank_trades``) in an account,
  dated on or before the file, are counted: they're the usual reason the shares don't match.

Nothing is stored: it's worked out each time, so adding a trade or a newer file updates it.
"""

import datetime as dt
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BankTrade, Position, StockLot, StockSaleOrder, Transaction
from app.services.ledger.transaction_roles import none_of, stock_trades

CheckedBy = Literal["transaction", "positions_file"] | None


def _sum_by_symbol(
    session: Session, model, date_column, account_id: int, as_of: dt.date
) -> dict[str, int]:
    rows = session.execute(
        select(model.symbol, func.sum(model.shares_micro))
        .where(model.account_id == account_id, date_column <= as_of)
        .group_by(model.symbol)
    )
    return dict(rows.all())


def recorded_shares(session: Session, account_id: int, as_of: dt.date) -> dict[str, int]:
    """Symbol -> shares bought minus sold in the account, dated on or before ``as_of`` (so a trade
    recorded after the file doesn't look missing)."""
    bought = _sum_by_symbol(session, StockLot, StockLot.acquired_on, account_id, as_of)
    sold = _sum_by_symbol(session, StockSaleOrder, StockSaleOrder.sold_on, account_id, as_of)
    return {s: bought.get(s, 0) - sold.get(s, 0) for s in bought.keys() | sold.keys()}


def waiting_bank_trades(session: Session, account_id: int, as_of: dt.date) -> int:
    """Trades named in a bank file in this account, on or before ``as_of``, with no shares yet."""
    return int(
        session.scalar(
            select(func.count(BankTrade.id))
            .join(Transaction, Transaction.id == BankTrade.transaction_id)
            .where(
                BankTrade.dismissed.is_(False),
                Transaction.account_id == account_id,
                Transaction.date <= as_of,
                *none_of(stock_trades()),
            )
        )
        or 0
    )


@dataclass
class Snapshot:
    """One account's positions file and what your records say on its day."""

    as_of: dt.date
    in_file: dict[str, int]  # symbol -> shares the broker lists
    recorded: dict[str, int] = field(default_factory=dict)

    def compare(self) -> list[tuple[str, int | None, int]]:
        """(symbol, file shares or None if the file doesn't list it, recorded shares): every
        symbol in the file, then every symbol you hold by your records that the file leaves out."""
        rows: list[tuple[str, int | None, int]] = [
            (s, shares, self.recorded.get(s, 0)) for s, shares in sorted(self.in_file.items())
        ]
        rows += [
            (s, None, shares)
            for s, shares in sorted(self.recorded.items())
            if s not in self.in_file and shares != 0
        ]
        return rows

    def confirms(self, symbol: str, on: dt.date) -> bool:
        """The file agrees with your records for ``symbol`` and is dated on or after ``on``."""
        return on <= self.as_of and self.in_file.get(symbol, 0) == self.recorded.get(symbol, 0)


def snapshots(session: Session) -> dict[int, Snapshot]:
    """Account id -> its positions file compared with your records."""
    found: dict[int, Snapshot] = {}
    for p in session.scalars(select(Position)):
        snap = found.setdefault(p.account_id, Snapshot(p.as_of, {}))
        snap.in_file[p.symbol] = snap.in_file.get(p.symbol, 0) + p.shares_micro
    for account_id, snap in found.items():
        snap.recorded = recorded_shares(session, account_id, snap.as_of)
    return found


def checked_by(
    files: dict[int, Snapshot],
    account_id: int | None,
    symbol: str,
    on: dt.date,
    transaction_id: int | None,
) -> CheckedBy:
    """What backs up a purchase or sale: its transaction, a matching positions file, or nothing."""
    if transaction_id is not None:
        return "transaction"
    snap = files.get(account_id) if account_id is not None else None
    if snap is not None and snap.confirms(symbol, on):
        return "positions_file"
    return None
