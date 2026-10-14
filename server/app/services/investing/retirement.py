"""Retirement and HSA contributions for a year against the IRS limits. An estimate, not tax advice.

Every limit comes from that year's tax data file (``retirement`` and ``hsa`` sections), never from
here. What's counted:

- **401(k)/403(b) (your own contributions):** traditional plus Roth amounts from your pay stubs
  (``retirement_cents`` + ``roth_retirement_cents``), by pay date. They share one elective-deferral
  limit. Employer matches don't count toward it. A governmental 457(b) has its own separate limit;
  pay stubs have no plan type, so the note asks people to leave 457(b) amounts out.
- Limits are per person, but pay stubs and deductions have no owner: the totals add up everyone's,
  and the note says so.
- **IRA:** the "IRA contribution" deductions you entered for that tax year, plus money put into an
  account marked Roth IRA during the year (``_roth_ira_total``): linked transfers into it, and
  deposits there that say "contribution". Dividends, interest, stock sales and rollovers there
  don't count, and nor does a transfer from another retirement account or HSA (a conversion,
  rollover, or a move between IRAs: none of these use up the yearly limit). A Roth contribution
  made by the tax-filing deadline for the year before is counted in the year it was made, so the
  note asks you to check those.
- **HSA:** pay-stub HSA amounts plus "HSA contribution" deductions. The limit depends on
  self-only or family coverage, so both are shown.

Catch-up amounts depend on your age, which Budget Buddy doesn't know: they're listed, not added.
"""

import datetime as dt
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app import tax_data
from app.errors import ApiError
from app.models import (
    Account,
    AccountKind,
    Deduction,
    DeductionKind,
    Paycheck,
    RetirementType,
    Transaction,
    TransactionKind,
)
from app.schemas.investing.retirement import LimitOut, RetirementOut

NOTE = (
    "An estimate to help you stay under the limits, not tax advice. Catch-up amounts depend on "
    "your age, so they're listed but not added. Employer matches aren't included, and Roth IRA "
    "contributions only when the account is marked Roth IRA on the Accounts page. These totals "
    "add up everyone's pay stubs and deductions, but the 401(k) and IRA limits are for each "
    "person: if you entered a spouse's, compare each person separately. Higher incomes can lower "
    "or remove what you're allowed to put in a Roth IRA. Check with your plan or a tax "
    "professional."
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


_CONTRIBUTION = re.compile(r"(?<![a-z])contrib", re.I)
_ROLLOVER = re.compile(r"(?<![a-z])(roll.?over|conv|rechar|trustee|acat|transfer of assets)", re.I)
# Money from these accounts into a Roth IRA is a conversion or rollover, not a new contribution.
_FROM_RETIREMENT = (AccountKind.RETIREMENT, AccountKind.HSA)


def _roth_ira_total(session: Session, year: int) -> int:
    """Money put into Roth IRA accounts in ``year``: linked transfers in, and deposits that say
    "contribution" (not rollovers or conversions, which don't use up the limit)."""
    partner = aliased(Transaction)
    partner_account = aliased(Account)
    rows = session.execute(
        select(Transaction.kind, Transaction.description, Transaction.amount_cents)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(partner, partner.id == Transaction.transfer_pair_id)
        .outerjoin(partner_account, partner_account.id == partner.account_id)
        .where(
            partner_account.kind.is_(None) | partner_account.kind.not_in(_FROM_RETIREMENT),
            Account.kind == AccountKind.RETIREMENT,
            Account.retirement_type == RetirementType.ROTH_IRA.value,
            Transaction.amount_cents > 0,
            Transaction.date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)),
            Transaction.kind.in_([TransactionKind.TRANSFER, TransactionKind.NORMAL]),
        )
    )
    return sum(
        cents
        for kind, description, cents in rows
        if not _ROLLOVER.search(description)
        and (kind == TransactionKind.TRANSFER or _CONTRIBUTION.search(description))
    )


def _limit(
    name: str, contributed: int, limit: int, catch_up: list[tuple[int, str]], note: str
) -> LimitOut:
    """``catch_up``: (extra amount, who may add it), e.g. (800_000, "age 50 or older")."""
    return LimitOut(
        name=name,
        contributed_cents=contributed,
        limit_cents=limit,
        left_cents=max(limit - contributed, 0),
        over_cents=max(contributed - limit, 0),
        catch_up_cents=[cents for cents, _ in catch_up],
        catch_up_ages=[who for _, who in catch_up],
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
    ira = _deduction_total(session, year, DeductionKind.IRA) + _roth_ira_total(session, year)
    hsa_total = _paycheck_total(session, year, Paycheck.hsa_cents) + _deduction_total(
        session, year, DeductionKind.HSA
    )
    return RetirementOut(
        tax_year=year,
        is_estimate=True,
        note=NOTE,
        limits=[
            _limit(
                "401(k) or 403(b): your own contributions",
                deferrals,
                r.elective_deferral_401k_cents,
                [
                    (r.catch_up_50_plus_cents, "age 50 or older"),
                    (r.catch_up_age_60_to_63_cents, "ages 60 to 63"),
                ],
                "Traditional and Roth together, from your pay stubs. A 457(b) plan has its own "
                "separate limit: leave it out of this total.",
            ),
            _limit(
                "IRA",
                ira,
                r.ira_cents,
                [(r.ira_catch_up_50_plus_cents, "age 50 or older")],
                "From the IRA contributions you entered as deductions, plus money put into "
                "accounts marked Roth IRA this year (transfers in, and deposits that say "
                "contribution). "
                "Traditional and Roth IRAs share this limit, and it can't be more than your pay "
                "for the year. If part of a contribution wasn't deductible, add that part too. A "
                "Roth contribution made early this year for last year counts here; check those.",
            ),
            _limit(
                "HSA (self-only coverage)",
                hsa_total,
                hsa.self_only_cents,
                [(hsa.catch_up_55_plus_cents, "age 55 or older")],
                "From pay stubs and HSA deductions. Don't also enter pay-stub HSA amounts as a "
                "deduction: that counts them twice. Money your employer puts in counts too. If you "
                "weren't covered all year, your limit may be lower.",
            ),
            _limit(
                "HSA (family coverage)",
                hsa_total,
                hsa.family_cents,
                [(hsa.catch_up_55_plus_cents, "age 55 or older")],
                "Use this line instead if your health plan covers your family. Spouses share this "
                "one family limit.",
            ),
        ],
        tax_data_last_reviewed=data.last_reviewed,
    )
