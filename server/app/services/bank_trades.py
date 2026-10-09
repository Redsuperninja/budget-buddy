"""Stock trades in a bank-style file, and the deposit sweep that paid for them (or took the money).

Some brokers' files (J.P. Morgan / Chase, for one) show a trade only as a line naming the company,
with no ticker, share count or price, like "ABBOTT LABORATORIES UNSOLICITED WE ARE ACTING AS
PRINCIPAL COMMISSION FIELD IS A COMMISSION EQUIVALENT ...". Money out is a buy, money in a sale.
Next to it the sweep moves the same cash: "CHASE DEPOSIT SWEEP ... INTRA-DAY WITHDRWAL" (money in)
pays for a buy, "... INTRA-DAY DEPOSIT" (money out) parks a sale's proceeds. (A dividend's sweep is
handled by ``dividend_matching``, which runs first.)

- **A trade** is a regular transaction in a brokerage, retirement or HSA account whose description
  has trade-confirmation wording (``TRADE_WORDS``), and isn't a sweep or a dividend.
- **Its sweep**: the opposite amount in the same account, from the day before to three days after,
  with "sweep" in it, not already a dividend's or another trade's. Closest date wins, then the one
  added first.
- A trade and its sweep only move cash into shares (or back) inside the account, so the monthly
  summary, "needs a category" and transfer matching leave both out (``inside_account_ids``).
- The shares, ticker and price come from the stock purchase or sale recorded from the trade
  (``StockLot`` / ``StockSaleOrder.transaction_id``): on the Investments page you type the ticker
  (remembered per company, ``SecuritySymbol``) and the shares; the price is the amount / shares.

It runs after a bank file is imported, after a transaction is added by hand, and when asked.
Nothing here logs descriptions or amounts.
"""

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, BankTrade, Dividend, SecuritySymbol, Transaction
from app.services.accounts import INVESTMENT_KINDS
from app.services.dividend_matching import (
    SWEEP_DAYS_AFTER,
    SWEEP_DAYS_BEFORE,
    SWEEP_WORDS,
    looks_like_dividend,
    regular,
)

TRADE_WORDS = re.compile(
    r"acting as (principal|agent)|(?<![a-z])(un)?solicited(?![a-z])|commission (field|equivalent)"
    r"|(?<![a-z])(you )?(bought|sold)(?![a-z])",
    re.I,
)
_LEADING_ACTION = re.compile(r"^\s*(you\s+)?(bought|sold|buy|sell)\s+", re.I)
# Where the company's name ends: "ABBOTT LABORATORIES UNSOLICITED ..." -> "ABBOTT LABORATORIES".
_NAME_END = re.compile(
    r"\s+((un)?solicited|we are acting|common stock|commission|@|\(|\d).*$", re.I
)
_TICKER_IN_TEXT = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")
MAX_NAME = 100


@dataclass
class Found:
    trades: int = 0
    sweeps: int = 0


def security_name(description: str) -> str:
    name = _NAME_END.sub("", _LEADING_ACTION.sub("", description)).strip(" -:,.")
    return (name or description)[:MAX_NAME]


def ticker_in(description: str) -> str | None:
    """A ticker the description gives in brackets, like "YOU BOUGHT FAKE FUND (FAKE)"."""
    found = _TICKER_IN_TEXT.search(description)
    return found.group(1) if found else None


def looks_like_trade(description: str) -> bool:
    return bool(TRADE_WORDS.search(description)) and not SWEEP_WORDS.search(description)


def _used_sweeps():
    return (
        select(Dividend.sweep_transaction_id)
        .where(Dividend.sweep_transaction_id.is_not(None))
        .union(
            select(BankTrade.sweep_transaction_id).where(
                BankTrade.sweep_transaction_id.is_not(None)
            )
        )
    )


def _new_trades(session: Session, ids: set[int] | None) -> list[Transaction]:
    query = (
        regular(select(Transaction, Account.kind))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.kind.in_(INVESTMENT_KINDS),
            Transaction.amount_cents != 0,
            Transaction.id.not_in(select(BankTrade.transaction_id)),
            Transaction.id.not_in(select(Dividend.transaction_id)),
        )
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    return [
        t
        for t, kind in session.execute(query)
        if looks_like_trade(t.description) and not looks_like_dividend(t.description, kind)
    ]


def _link_sweeps(session: Session) -> int:
    open_trades = session.execute(
        select(BankTrade, Transaction)
        .join(Transaction, Transaction.id == BankTrade.transaction_id)
        .where(BankTrade.dismissed.is_(False), BankTrade.sweep_transaction_id.is_(None))
        .order_by(Transaction.date, Transaction.id)
    ).all()
    if not open_trades:
        return 0
    sweeps = [
        t
        for t in session.scalars(
            regular(select(Transaction)).where(
                Transaction.account_id.in_({t.account_id for _, t in open_trades}),
                Transaction.id.not_in(_used_sweeps()),
                Transaction.id.not_in(select(BankTrade.transaction_id)),
            )
        )
        if SWEEP_WORDS.search(t.description)
    ]
    linked = 0
    taken: set[int] = set()
    for trade, paid in open_trades:
        start = paid.date - dt.timedelta(days=SWEEP_DAYS_BEFORE)
        end = paid.date + dt.timedelta(days=SWEEP_DAYS_AFTER)
        fits = [
            s
            for s in sweeps
            if s.id not in taken
            and s.account_id == paid.account_id
            and s.amount_cents == -paid.amount_cents
            and start <= s.date <= end
        ]
        if fits:
            best = min(fits, key=lambda s: (abs((s.date - paid.date).days), s.id))
            trade.sweep_transaction_id = best.id
            taken.add(best.id)
            linked += 1
    return linked


def find_trades(session: Session, transaction_ids: set[int] | None = None) -> Found:
    """Record new trades among ``transaction_ids`` (all transactions if None) and link sweeps. Not
    saved until the caller commits. Run after ``find_dividends``, so a dividend's sweep is taken
    first. Two runs at once: the second adds nothing."""
    found = Found()
    try:
        with session.begin_nested():
            for paid in _new_trades(session, transaction_ids):
                session.add(
                    BankTrade(transaction_id=paid.id, security=security_name(paid.description))
                )
                found.trades += 1
            session.flush()
            found.sweeps = _link_sweeps(session)
            session.flush()
    except IntegrityError:
        return Found()
    return found


def inside_account_ids():
    """Ids of trades and their sweeps: cash turning into shares or back inside an account, never
    spending, income or a transfer."""
    shown = BankTrade.dismissed.is_(False)
    return (
        select(BankTrade.transaction_id)
        .where(shown)
        .union(
            select(BankTrade.sweep_transaction_id).where(
                shown, BankTrade.sweep_transaction_id.is_not(None)
            )
        )
    )


def remember_symbol(session: Session, transaction_id: int | None, symbol: str) -> None:
    """When a trade from the bank file is recorded with a ticker, keep it for that company's next
    trade. Not saved until the caller commits."""
    if transaction_id is None:
        return
    security = session.scalar(
        select(BankTrade.security).where(BankTrade.transaction_id == transaction_id)
    )
    if security is None:
        return
    saved = session.scalar(select(SecuritySymbol).where(SecuritySymbol.security == security))
    if saved is None:
        session.add(SecuritySymbol(security=security, symbol=symbol))
    else:
        saved.symbol = symbol
