"""Stock trades in a bank-style file, and the deposit sweep that paid for them (or took the money).

Some brokers' files (J.P. Morgan / Chase, for one) show a trade only as a line naming the company,
with no ticker, share count or price, like "ABBOTT LABORATORIES UNSOLICITED WE ARE ACTING AS
PRINCIPAL COMMISSION FIELD IS A COMMISSION EQUIVALENT ...". Money out is a buy, money in a sale.
Next to it the sweep moves the same cash: "CHASE DEPOSIT SWEEP ... INTRA-DAY WITHDRWAL" (money in)
pays for a buy, "... INTRA-DAY DEPOSIT" (money out) parks a sale's proceeds. (A dividend's sweep is
handled by ``dividend_matching``, which runs first.)

- **A trade** is a regular transaction in a brokerage, retirement or HSA account whose description
  has trade-confirmation wording (``TRADE_WORDS``), and isn't a sweep or a dividend. A trade you
  recorded yourself from a transaction (a stock purchase or sale linked to it) becomes one too,
  but only once its sweep is found, so its sweep is left out the same way.
- **Its sweep**: the opposite amount in the same account, from the day before to three days after,
  with "sweep" in it, not already a dividend's or another trade's. Closest date wins, then the one
  added first.
- A trade and its sweep only move cash into shares (or back) inside the account, so the monthly
  summary, "needs a category" and transfer matching leave both out
  (``transaction_roles.cash_inside_account``).
- The shares, ticker and price come from the stock purchase or sale recorded from the trade
  (``StockLot`` / ``StockSaleOrder.transaction_id``): on the Investments page you type the ticker
  (remembered per company, ``SecuritySymbol``) and the shares; the price is the amount / shares.

It runs after a bank file is imported, after a transaction is added by hand, and when asked.
Nothing here logs descriptions or amounts.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, BankTrade, SecuritySymbol, Transaction
from app.services.accounts import INVESTMENT_KINDS
from app.services.dividend_matching import looks_like_dividend
from app.services.sweeps import SWEEP_WORDS, candidates, in_window, link_sweeps, regular
from app.services.transaction_roles import bank_trades, dividends, none_of, stock_trades

# Trade-confirmation wording, which only trades carry.
CONFIRMATION_WORDS = re.compile(
    r"acting as (principal|agent)|(?<![a-z])(un)?solicited(?![a-z])|commission (field|equivalent)",
    re.I,
)
# A plain "bought" or "sold" counts too, unless the line is about cash funds or bonds coming due.
BOUGHT_SOLD = re.compile(r"(?<![a-z])(bought|sold)(?![a-z])", re.I)
NOT_STOCK_WORDS = re.compile(
    r"money market|mmkt|(?<![a-z])mmf(?![a-z])|redemption|redeem|matur|to cover", re.I
)
# A cancelled or corrected trade reverses money: it mustn't look like the opposite trade.
REVERSAL_WORDS = re.compile(r"cancel|(?<![a-z])cxl(?![a-z])|correct|revers|rebill|adjust", re.I)
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
    if SWEEP_WORDS.search(description) or REVERSAL_WORDS.search(description):
        return False
    if CONFIRMATION_WORDS.search(description):
        return True
    return bool(BOUGHT_SOLD.search(description)) and not NOT_STOCK_WORDS.search(description)


def _new_trades(session: Session, ids: set[int] | None) -> list[Transaction]:
    query = (
        regular(select(Transaction, Account.kind))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.kind.in_(INVESTMENT_KINDS),
            Transaction.amount_cents != 0,
            *none_of(bank_trades(include_dismissed=True), dividends(include_dismissed=True)),
        )
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    return [
        t
        for t, kind in session.execute(query)
        if looks_like_trade(t.description) and not looks_like_dividend(t.description, kind)
    ]


def _recorded_without_one(session: Session) -> list[Transaction]:
    """Trades you recorded yourself (a stock purchase or sale linked to the transaction) in an
    investment account that aren't a bank-file trade yet, with a free sweep near them: their
    sweep is looked for too."""
    recorded = list(
        session.scalars(
            regular(select(Transaction))
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.kind.in_(INVESTMENT_KINDS),
                Transaction.amount_cents != 0,
                Transaction.id.in_(stock_trades()),
                *none_of(bank_trades(include_dismissed=True)),
            )
        )
    )
    if not recorded:
        return []
    sweeps = candidates(session, {t.account_id for t in recorded})
    return [
        t for t in recorded if any(s.account_id == t.account_id and in_window(s, t) for s in sweeps)
    ]


def forget_recorded(session: Session, transaction_id: int | None) -> None:
    """The purchase or sale recorded from this transaction was deleted: if it was a bank-file
    trade only because you recorded it (no trade wording), drop that too, freeing its sweep, so
    the payment counts like any other again. Not saved until the caller commits."""
    if transaction_id is None:
        return
    trade = session.scalar(select(BankTrade).where(BankTrade.transaction_id == transaction_id))
    if trade is not None and not looks_like_trade(
        session.get(Transaction, transaction_id).description
    ):
        session.delete(trade)


def _link_sweeps(session: Session) -> int:
    waiting = session.execute(
        select(BankTrade, Transaction)
        .join(Transaction, Transaction.id == BankTrade.transaction_id)
        .where(BankTrade.dismissed.is_(False), BankTrade.sweep_transaction_id.is_(None))
        .order_by(Transaction.date, Transaction.id)
    ).all()
    return link_sweeps(session, list(waiting))


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
            # Every recorded trade, not only ``transaction_ids``: its sweep may come in later.
            adopted = [
                BankTrade(transaction_id=paid.id, security=security_name(paid.description))
                for paid in _recorded_without_one(session)
            ]
            session.add_all(adopted)
            session.flush()
            found.sweeps = _link_sweeps(session)
            for trade in adopted:  # kept only with a sweep, so it isn't listed for nothing
                if trade.sweep_transaction_id is None:
                    session.delete(trade)
            session.flush()
    except IntegrityError:
        return Found()
    return found


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
