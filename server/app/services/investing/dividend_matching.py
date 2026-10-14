"""Finding dividends among your transactions, filing them under "Dividends", and linking the
deposit sweep that moved the same cash on.

A transaction is a dividend when it's money in, a regular transaction (not a transfer, paycheck
deposit or donation), and its description has the word "dividend", or "div" in an investment,
retirement or HSA account (``looks_like_dividend``), like "JOHNSON & JOHNSON COMMON STOCK CASH DIV
ON 1 SHS REC 08/25/26 PAY 09/08/26". Return of capital ("non-dividend distribution"), tax-exempt
dividends, payroll and "DIV OF ..." (a government division) are left alone. It's put in the
income category "Dividends" (made the first time), unless you or an auto-sort rule already gave it
a category.

Inside a retirement account or HSA, a dividend and its sweep stay in the account, so the monthly
summary leaves both out (``transaction_roles.dividends_kept_inside``): they aren't take-home
income or new saving.

Its sweep is money out of the same account for exactly the same amount, from the day before to
three days after, with "sweep" in the description (``sweeps.py``), like "CHASE IRA DEPOSIT SWEEP
JPMORGAN CHASE BANK NA INTRA-DAY DEPOSIT". The closest date wins (then the one added first). A sweep
keeps its own category: the pair only moved cash inside the account.

It runs after a bank file is imported, after a transaction is added by hand, and when asked to
look through everything. Nothing here logs descriptions or amounts.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountKind,
    CategoryGroup,
    CategorySource,
    Dividend,
    Transaction,
)
from app.services.budget.named_categories import find_or_make
from app.services.investing.sweeps import link_sweeps, regular
from app.services.ledger.accounts import INVESTMENT_KINDS
from app.services.ledger.transaction_roles import dividends, none_of

CATEGORY = "Dividends"
DIVIDEND_WORDS = re.compile(r"(?<![a-z])dividends?(?![a-z])", re.I)
SHORT_WORDS = re.compile(r"(?<![a-z])divs?(?![a-z])", re.I)  # only in investment accounts
NOT_DIVIDEND_WORDS = re.compile(
    r"non-?\s?dividend|return of capital|exempt|(?<![a-z])div of(?![a-z])|division|payroll", re.I
)
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


def looks_like_dividend(description: str, account_kind: AccountKind) -> bool:
    if NOT_DIVIDEND_WORDS.search(description):
        return False
    short = account_kind in INVESTMENT_KINDS and SHORT_WORDS.search(description)
    return bool(DIVIDEND_WORDS.search(description) or short)


def _new_dividends(session: Session, ids: set[int] | None) -> list[Transaction]:
    query = (
        regular(select(Transaction, Account.kind))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Transaction.amount_cents > 0,
            *none_of(dividends(include_dismissed=True)),
        )
    )
    if ids is not None:
        query = query.where(Transaction.id.in_(ids))
    return [t for t, kind in session.execute(query) if looks_like_dividend(t.description, kind)]


def file_under_dividends(session: Session, payment: Transaction) -> None:
    """Put a dividend in the "Dividends" income category, unless you or a rule already gave it a
    category, or "Dividends" is the name of one of your spending or transfer categories."""
    if payment.category_source in (CategorySource.YOU.value, CategorySource.RULE.value):
        return
    category_id = find_or_make(session, CATEGORY, {CategoryGroup.INCOME}, CategoryGroup.INCOME)
    if category_id is not None:
        payment.category_id = category_id
        payment.category_source = None  # set by Budget Buddy, like a transfer's category
        payment.sorted_by_rule_id = None


def _link_sweeps(session: Session) -> int:
    """Give every dividend still without one its sweep, if there's exactly-matching money out."""
    waiting = session.execute(
        select(Dividend, Transaction)
        .join(Transaction, Transaction.id == Dividend.transaction_id)
        .where(Dividend.dismissed.is_(False), Dividend.sweep_transaction_id.is_(None))
        .order_by(Transaction.date, Transaction.id)
    ).all()
    return link_sweeps(session, list(waiting))


def find_dividends(session: Session, transaction_ids: set[int] | None = None) -> Found:
    """Record new dividends among ``transaction_ids`` (all transactions if None), file them under
    "Dividends", then link sweeps. Not saved until the caller commits. If another window is
    doing the same at that moment, this one adds nothing: the other one finds them."""
    found = Found()
    try:
        with session.begin_nested():
            for payment in _new_dividends(session, transaction_ids):
                session.add(
                    Dividend(transaction_id=payment.id, payer=payer_name(payment.description))
                )
                file_under_dividends(session, payment)
                found.dividends += 1
            session.flush()
            found.sweeps = _link_sweeps(session)
            session.flush()
    except IntegrityError:
        return Found()
    return found
