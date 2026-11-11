"""What each extra pay-stub line does (issue #13, designed with the finance review).

``effect`` says how a line moves take-home pay:
- ``subtracts``: taken out of pay (a tax, or a deduction without a column of its own).
- ``adds``: paid on top of gross pay (a reimbursement).
- ``none``: shown on the stub but never part of the take-home sum (an employer contribution, or
  imputed income, which sits in gross and is withheld again at the same amount). Qualified tips
  and qualified overtime premium are also ``none``: they are part of gross pay already, picked
  out so the tax summary can total them. Both are still taxed for FICA and federal withholding
  (the deduction is claimed on the return), so neither flag is set.

``pre_tax_federal`` / ``pre_tax_fica`` say whether the amount came out before income tax /
Social Security and Medicare tax. They follow from the kind, so they can't be entered wrongly.
The tax summary does not use the flags yet.

The deductions that already have a column (pre-tax and Roth retirement, HSA, health insurance,
other after-tax deductions) stay in that column. Use a line only for something with no column.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Paycheck, PaycheckLine
from app.models import PaycheckLineKind as K


@dataclass(frozen=True)
class LineRule:
    effect: Literal["subtracts", "adds", "none"]
    pre_tax_federal: bool
    pre_tax_fica: bool


LINE_RULES: dict[K, LineRule] = {
    K.LOCAL_TAX: LineRule("subtracts", False, False),
    K.STATE_DISABILITY: LineRule("subtracts", False, False),
    K.PAID_FAMILY_LEAVE: LineRule("subtracts", False, False),
    K.HEALTH_FSA: LineRule("subtracts", True, True),  # Section 125
    K.DEPENDENT_CARE_FSA: LineRule("subtracts", True, True),  # Section 129
    K.EMPLOYER_HSA: LineRule("none", False, False),
    K.IMPUTED_INCOME: LineRule("none", False, False),
    K.REIMBURSEMENT: LineRule("adds", False, False),
    K.QUALIFIED_TIPS: LineRule("none", False, False),
    K.QUALIFIED_OVERTIME: LineRule("none", False, False),  # the premium part only
}

# Lines totalled for the year summary: income already in gross, shown so it isn't missed.
YEAR_TOTAL_KINDS = (K.QUALIFIED_TIPS, K.QUALIFIED_OVERTIME)


def year_totals(session: Session, year: int) -> dict[str, int]:
    """Total of each ``YEAR_TOTAL_KINDS`` line on paychecks paid in ``year`` (0 if none)."""
    rows = session.execute(
        select(PaycheckLine.kind, func.sum(PaycheckLine.amount_cents))
        .join(Paycheck)
        .where(Paycheck.pay_date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)))
        .where(PaycheckLine.kind.in_(YEAR_TOTAL_KINDS))
        .group_by(PaycheckLine.kind)
    ).all()
    found = dict(rows)
    return {kind.value: found.get(kind, 0) for kind in YEAR_TOTAL_KINDS}


def net_effect_cents(lines: list[tuple[K, int]]) -> int:
    """How much the lines change take-home pay (negative = taken out)."""
    total = 0
    for kind, amount in lines:
        effect = LINE_RULES[kind].effect
        total += amount if effect == "adds" else -amount if effect == "subtracts" else 0
    return total
