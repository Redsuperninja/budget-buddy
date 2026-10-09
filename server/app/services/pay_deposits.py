"""Pay deposits waiting for a paycheck: money into a checking or savings account that looks like
pay and isn't linked to a paycheck yet. The Paychecks page offers to fill each one in from the pay
stub, with the date, take-home pay and deposit already set.

Looks like pay: the description has a payroll word (``PAY_WORDS``), or it's in an income category
named like "Paycheck" (the starter category). Transfers, adjustments and refunds never count.
Nothing here logs descriptions or amounts.
"""

import datetime as dt
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, CategoryGroup, Paycheck, Transaction, TransactionKind
from app.schemas.paychecks import PayDeposit
from app.services.paychecks import DEPOSIT_ACCOUNT_KINDS

_PAY = "payroll|direct dep|dir dep|salary|paycheck|pay check|wages"
PAY_WORDS = re.compile(rf"(?<![a-z])({_PAY})(?![a-z])", re.I)
# Where the employer's name ends: "FAKECO INC PAYROLL PPD ID: 123" -> "FAKECO INC".
_EMPLOYER_END = re.compile(rf"\s+({_PAY}|ppd|des:).*$", re.I)
MAX_EMPLOYER = 200
MAX_LISTED = 100


def employer_guess(description: str) -> str:
    return (_EMPLOYER_END.sub("", description).strip(" -:,.") or description)[:MAX_EMPLOYER]


def waiting_deposits(session: Session, year: int) -> list[PayDeposit]:
    """Newest first, at most ``MAX_LISTED``."""
    pay_categories = {
        c.id
        for c in session.scalars(select(Category).where(Category.group == CategoryGroup.INCOME))
        if "pay" in c.name.casefold()
    }
    linked = select(Paycheck.deposit_transaction_id).where(
        Paycheck.deposit_transaction_id.is_not(None)
    )
    rows = session.scalars(
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.kind.in_(DEPOSIT_ACCOUNT_KINDS),
            Transaction.kind == TransactionKind.NORMAL,
            Transaction.transfer_pair_id.is_(None),
            Transaction.amount_cents > 0,
            Transaction.date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)),
            Transaction.id.not_in(linked),
        )
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    )
    found = [t for t in rows if t.category_id in pay_categories or PAY_WORDS.search(t.description)]
    return [
        PayDeposit(
            transaction_id=t.id,
            date=t.date,
            description=t.description,
            amount_cents=t.amount_cents,
            account_id=t.account_id,
            employer=employer_guess(t.description),
        )
        for t in found[:MAX_LISTED]
    ]
