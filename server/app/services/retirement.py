"""Retirement and HSA contributions for a year against the IRS limits. An estimate, not tax advice.

Every limit comes from that year's tax data file (``retirement`` and ``hsa`` sections), never from
here. What's counted:

- **401(k)/403(b)/457 (your own contributions):** traditional plus Roth amounts from your pay stubs
  (``retirement_cents`` + ``roth_retirement_cents``), by pay date. They share one elective-deferral
  limit. Employer matches don't count toward it.
- **IRA:** the "IRA contribution" deductions you entered for that tax year. Roth IRA contributions
  aren't deductions, so they aren't seen here; the note says so.
- **HSA:** pay-stub HSA amounts plus "HSA contribution" deductions. The limit depends on
  self-only or family coverage, so both are shown.

Catch-up amounts depend on your age, which Budget Buddy doesn't know: they're listed, not added.
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tax_data
from app.errors import ApiError
from app.models import Deduction, DeductionKind, Paycheck
from app.schemas.retirement import LimitOut, RetirementOut

NOTE = (
    "An estimate to help you stay under the limits, not tax advice. Catch-up amounts depend on "
    "your age, so they're listed but not added. Roth IRA contributions and employer matches aren't "
    "included. Check with your plan or a tax professional."
)


def _paycheck_total(session: Session, year: int, *columns) -> int:
    start, end = dt.date(year, 1, 1), dt.date(year, 12, 31)
    total = sum(func.coalesce(func.sum(c), 0) for c in columns)
    return int(
        session.scalar(select(total).where(Paycheck.pay_date >= start, Paycheck.pay_date <= end))
        or 0
    )


def _deduction_total(session: Session, year: int, kind: DeductionKind) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(Deduction.amount_cents), 0)).where(
                Deduction.tax_year == year, Deduction.kind == kind
            )
        )
        or 0
    )


def _limit(name: str, contributed: int, limit: int, catch_up: list[int], note: str) -> LimitOut:
    return LimitOut(
        name=name,
        contributed_cents=contributed,
        limit_cents=limit,
        left_cents=max(limit - contributed, 0),
        over_cents=max(contributed - limit, 0),
        catch_up_cents=catch_up,
        note=note,
    )


def contributions(session: Session, year: int) -> RetirementOut:
    try:
        data = tax_data.load_tax_year(year)
    except tax_data.UnsupportedTaxYearError as exc:
        years = ", ".join(str(y) for y in exc.supported) or "none yet"
        raise ApiError(
            404,
            "no_tax_data",
            f"Budget Buddy doesn't have tax rules for {year} yet. Years it has: {years}.",
        ) from None
    r, hsa = data.retirement, data.hsa
    deferrals = _paycheck_total(
        session, year, Paycheck.retirement_cents, Paycheck.roth_retirement_cents
    )
    ira = _deduction_total(session, year, DeductionKind.IRA)
    hsa_total = _paycheck_total(session, year, Paycheck.hsa_cents) + _deduction_total(
        session, year, DeductionKind.HSA
    )
    return RetirementOut(
        tax_year=year,
        is_estimate=True,
        note=NOTE,
        limits=[
            _limit(
                "401(k), 403(b) or 457: your own contributions",
                deferrals,
                r.elective_deferral_401k_cents,
                [r.catch_up_50_plus_cents, r.catch_up_age_60_to_63_cents],
                "Traditional and Roth together, from your pay stubs. Age 50 or older can add a "
                "catch-up; ages 60 to 63 a larger one.",
            ),
            _limit(
                "IRA",
                ira,
                r.ira_cents,
                [r.ira_catch_up_50_plus_cents],
                "From the IRA contributions you entered as deductions. Traditional and Roth IRAs "
                "share this limit.",
            ),
            _limit(
                "HSA (self-only coverage)",
                hsa_total,
                hsa.self_only_cents,
                [hsa.catch_up_55_plus_cents],
                "From pay stubs and HSA deductions. Money your employer puts in counts toward this "
                "limit too, so add it if it isn't on your stubs.",
            ),
            _limit(
                "HSA (family coverage)",
                hsa_total,
                hsa.family_cents,
                [hsa.catch_up_55_plus_cents],
                "Use this line instead if your health plan covers your family.",
            ),
        ],
        tax_data_last_reviewed=data.last_reviewed,
    )
