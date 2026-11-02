"""What each extra pay-stub line does (issue #13, designed with the finance review).

``effect`` says how a line moves take-home pay:
- ``subtracts``: taken out of pay (a tax, or a deduction without a column of its own).
- ``adds``: paid on top of gross pay (a reimbursement).
- ``none``: shown on the stub but never part of the take-home sum (an employer contribution, or
  imputed income, which sits in gross and is withheld again at the same amount).

``pre_tax_federal`` / ``pre_tax_fica`` say whether the amount came out before income tax /
Social Security and Medicare tax. They follow from the kind, so they can't be entered wrongly.
The tax summary does not use them yet.

The deductions that already have a column (pre-tax and Roth retirement, HSA, health insurance,
other after-tax deductions) stay in that column. Use a line only for something with no column.
"""

from dataclasses import dataclass
from typing import Literal

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
}


def net_effect_cents(lines: list[tuple[K, int]]) -> int:
    """How much the lines change take-home pay (negative = taken out)."""
    total = 0
    for kind, amount in lines:
        effect = LINE_RULES[kind].effect
        total += amount if effect == "adds" else -amount if effect == "subtracts" else 0
    return total
