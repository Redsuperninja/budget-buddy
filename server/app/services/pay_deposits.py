"""Pay deposits waiting for a paycheck: money into a checking or savings account that looks like
pay and isn't linked to a paycheck yet. The Paychecks page offers to fill each one in from the pay
stub, with the date, take-home pay and deposit already set.

Looks like pay: it's in an income category with "pay", "paycheck", "payroll" or "salary" as a word
in its name (like the starter "Paycheck"), or it has no category and its description has a
payroll word (``PAY_WORDS``). Tax refunds, Social Security, unemployment and reimbursements
(``NOT_PAY_WORDS``), and anything in a non-income category, never count; nor do transfers,
adjustments and refunds.
Nothing here logs descriptions or amounts.
"""

import datetime as dt
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Category, CategoryGroup, Transaction, TransactionKind
from app.schemas.paychecks import PayDeposit
from app.services.paychecks import DEPOSIT_ACCOUNT_KINDS
from app.services.transaction_roles import none_of, paycheck_deposits

_PAY = "payroll|direct dep|dir dep|salary|paycheck|pay check|wages"
PAY_WORDS = re.compile(rf"(?<![a-z])({_PAY})(?![a-z])", re.I)
NOT_PAY_WORDS = re.compile(
    r"(?<![a-z])(tax ref|irs|treas|ssa|soc sec|social security|unemploy|reimb)", re.I
)
PAY_CATEGORY = re.compile(r"(?<![a-z])(pay|paycheck|payroll|salary)(?![a-z])", re.I)
# Where the employer's name ends: "FAKECO INC PAYROLL PPD ID: 123" -> "FAKECO INC".
_EMPLOYER_END = re.compile(rf"\s+({_PAY}|ppd|des:).*$", re.I)
MAX_EMPLOYER = 200
MAX_LISTED = 100


def employer_guess(description: str) -> str:
    return (_EMPLOYER_END.sub("", description).strip(" -:,.") or description)[:MAX_EMPLOYER]


def waiting_deposits(session: Session, year: int) -> list[PayDeposit]:
    """Newest first, at most ``MAX_LISTED``."""
    income = {
        c.id: bool(PAY_CATEGORY.search(c.name))
        for c in session.scalars(select(Category).where(Category.group == CategoryGroup.INCOME))
    }
    rows = session.scalars(
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.kind.in_(DEPOSIT_ACCOUNT_KINDS),
            Transaction.kind == TransactionKind.NORMAL,
            Transaction.transfer_pair_id.is_(None),
            Transaction.amount_cents > 0,
            Transaction.date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)),
            *none_of(paycheck_deposits()),
        )
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    )
    found = []
    for t in rows:
        if NOT_PAY_WORDS.search(t.description):
            continue
        if income.get(t.category_id, False) if t.category_id else PAY_WORDS.search(t.description):
            found.append(t)
            if len(found) == MAX_LISTED:
                break
    return [
        PayDeposit(
            transaction_id=t.id,
            date=t.date,
            description=t.description,
            amount_cents=t.amount_cents,
            account_id=t.account_id,
            employer=employer_guess(t.description),
        )
        for t in found
    ]
