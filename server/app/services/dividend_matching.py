"""Finding dividends among your transactions, filing them under "Dividends", and linking the
deposit sweep that moved the same cash on.

A transaction is a dividend when it's money in, a regular transaction (not a transfer, paycheck
deposit or donation), and its description has the word "div" or "dividend" (``DIVIDEND_WORDS``),
like "JOHNSON & JOHNSON COMMON STOCK CASH DIV ON 1 SHS REC 08/25/26 PAY 09/08/26". It's put in the
income category "Dividends" (made the first time), unless you picked its category yourself.

Its sweep is money out of the same account for exactly the same amount, from the day before to
``SWEEP_DAYS_AFTER`` days after, with "sweep" in the description, like "CHASE IRA DEPOSIT SWEEP
JPMORGAN CHASE BANK NA INTRA-DAY DEPOSIT". The closest date wins (then the one added first). A sweep
keeps its own category: the pair only moved cash inside the account.

It runs after a bank file is imported, after a transaction is added by hand, and when asked to
look through everything. Nothing here logs descriptions or amounts.
"""

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CategoryGroup,
    CategorySource,
    Dividend,
    Donation,
    Paycheck,
    Transaction,
    TransactionKind,
)
from app.services.named_categories import find_or_make

CATEGORY = "Dividends"
SWEEP_DAYS_BEFORE = 1
SWEEP_DAYS_AFTER = 3
DIVIDEND_WORDS = re.compile(r"(?<![a-z])(div|divs|dividend|dividends)(?![a-z])", re.I)
SWEEP_WORDS = re.compile(r"(?<![a-z])sweep(?![a-z])", re.I)
# Where the payer's name ends: "JOHNSON & JOHNSON COMMON STOCK CASH DIV ..." -> "JOHNSON & JOHNSON".
_PAYER_END = re.compile(
    r"\s+(common stock|((cash|qualified|ordinary) )?(dividends?|divs?))(?![a-z]).*$", re.I
)
MAX_PAYER = 100


@dataclass
class Found:
    dividends: int = 0
    sweeps: int = 0


def payer_name(description: str) -> str:
    return (_PAYER_END.sub("", description).strip(" -:,.") or description)[:MAX_PAYER]


def _regular(query):
    """Regular transactions not already a transfer, a paycheck's deposit or a donation."""
    return query.where(
        Transaction.kind == TransactionKind.NORMAL,
        Transaction.transfer_pair_id.is_(None),
        Transaction.id.not_in(
            select(Paycheck.deposit_transaction_id).where(
                Paycheck.deposit_transaction_id.is_not(None)
            )
        ),
        Transaction.id.not_in(
            select(Donation.transaction_id).where(Donation.transaction_id.is_not(None))
        ),
    )


def _new_dividends(session: Session, ids: set[int] | None) -> list[Transaction]:
    query = _regular(select(Transaction)).where(
        Transaction.amount_cents > 0,
        Transaction.id.not_in(select(Dividend.transaction_id)),
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    return [t for t in session.scalars(query) if DIVIDEND_WORDS.search(t.description)]


def file_under_dividends(session: Session, payment: Transaction) -> None:
    """Put a dividend in the "Dividends" income category, unless you picked its category
    yourself, or "Dividends" is the name of one of your spending or transfer categories."""
    if payment.category_source == CategorySource.YOU.value:
        return
    category_id = find_or_make(session, CATEGORY, {CategoryGroup.INCOME}, CategoryGroup.INCOME)
    if category_id is not None:
        payment.category_id = category_id
        payment.category_source = None  # set by Budget Buddy, like a transfer's category
        payment.sorted_by_rule_id = None


def _link_sweeps(session: Session) -> int:
    """Give every dividend still without one its sweep, if there's exactly-matching money out."""
    open_dividends = session.execute(
        select(Dividend, Transaction)
        .join(Transaction, Transaction.id == Dividend.transaction_id)
        .where(Dividend.dismissed.is_(False), Dividend.sweep_transaction_id.is_(None))
        .order_by(Transaction.date, Transaction.id)
    ).all()
    if not open_dividends:
        return 0
    used = select(Dividend.sweep_transaction_id).where(Dividend.sweep_transaction_id.is_not(None))
    sweeps = [
        t
        for t in session.scalars(
            _regular(select(Transaction)).where(
                Transaction.amount_cents < 0,
                Transaction.account_id.in_({t.account_id for _, t in open_dividends}),
                Transaction.id.not_in(used),
            )
        )
        if SWEEP_WORDS.search(t.description)
    ]
    linked = 0
    taken: set[int] = set()
    for dividend, paid in open_dividends:
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
            dividend.sweep_transaction_id = best.id
            taken.add(best.id)
            linked += 1
    return linked


def find_dividends(session: Session, transaction_ids: set[int] | None = None) -> Found:
    """Record new dividends among ``transaction_ids`` (all transactions if None), file them under
    "Dividends", then link sweeps. Not saved until the caller commits."""
    found = Found()
    for payment in _new_dividends(session, transaction_ids):
        session.add(Dividend(transaction_id=payment.id, payer=payer_name(payment.description)))
        file_under_dividends(session, payment)
        found.dividends += 1
    session.flush()
    found.sweeps = _link_sweeps(session)
    session.flush()
    return found
