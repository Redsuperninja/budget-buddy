"""Paychecks: what you earned, what was taken out, and what reached your bank.

Rules (see docs/dev/architecture/paychecks.md):
- Gross minus every tax and deduction must equal net, to the cent. No rounding anywhere.
- A paycheck is never income in budget totals. Income comes only from bank transactions, so a
  paycheck linked to its deposit is counted once (the deposit), and an unlinked one adds nothing.
- Nothing here logs amounts or employer names.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Account, AccountKind, Paycheck, Transaction, TransactionKind
from app.money import cents_to_display
from app.schemas.tax.paychecks import (
    PaycheckCreate,
    PaycheckPage,
    PaycheckSummary,
    PaycheckUpdate,
    SocialSecurityCheck,
)
from app.services.ledger.accounts import get_account
from app.services.ledger.transactions import get_transaction
from app.tax_data import UnsupportedTaxYearError, load_tax_year

TAX_FIELDS = ("federal_tax_cents", "state_tax_cents", "social_security_cents", "medicare_cents")
PRE_TAX_FIELDS = ("retirement_cents", "hsa_cents", "health_insurance_cents")
AFTER_TAX_FIELDS = ("roth_retirement_cents", "other_deductions_cents")
TAKEN_OUT_FIELDS = TAX_FIELDS + PRE_TAX_FIELDS + AFTER_TAX_FIELDS
AMOUNT_FIELDS = ("gross_cents", *TAKEN_OUT_FIELDS, "net_cents")
DEPOSIT_ACCOUNT_KINDS = (AccountKind.CHECKING, AccountKind.SAVINGS)


def check_adds_up(values: dict) -> None:
    """Raise a 422 naming the difference if gross - taxes - deductions != net."""
    expected = values["gross_cents"] - sum(values[f] for f in TAKEN_OUT_FIELDS)
    difference = values["net_cents"] - expected
    if difference:
        more_or_less = "more" if difference > 0 else "less"
        raise ApiError(
            422,
            "net_mismatch",
            f"This paycheck doesn't add up: net pay is {cents_to_display(abs(difference))} "
            f"{more_or_less} than gross pay minus all taxes and deductions. "
            "Check each line against your pay stub.",
            expected_net_cents=expected,
            difference_cents=difference,
        )


def get_paycheck(session: Session, paycheck_id: int) -> Paycheck:
    paycheck = session.get(Paycheck, paycheck_id)
    if paycheck is None:
        raise not_found("paycheck")
    return paycheck


def list_paychecks(session: Session, year: int | None, limit: int, offset: int) -> PaycheckPage:
    """Newest first."""
    query = select(Paycheck)
    if year is not None:
        query = query.where(Paycheck.pay_date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(
        query.order_by(Paycheck.pay_date.desc(), Paycheck.id.desc()).limit(limit).offset(offset)
    ).all()
    return PaycheckPage.model_validate(
        {"items": items, "total": total, "limit": limit, "offset": offset}
    )


def create_paycheck(session: Session, data: PaycheckCreate) -> Paycheck:
    """Add a paycheck, linked to its deposit straight away when ``deposit_transaction_id`` is
    given (from a pay deposit waiting on the Paychecks page). All or nothing."""
    values = data.model_dump()
    deposit_id = values.pop("deposit_transaction_id")
    check_adds_up(values)
    if values["account_id"] is not None:
        get_account(session, values["account_id"])
    paycheck = Paycheck(**values)
    session.add(paycheck)
    if deposit_id is not None:
        session.flush()
        _attach_deposit(session, paycheck, get_transaction(session, deposit_id))
    session.commit()
    return paycheck


def update_paycheck(session: Session, paycheck_id: int, data: PaycheckUpdate) -> Paycheck:
    paycheck = get_paycheck(session, paycheck_id)
    changes = data.changes()
    final = {f: changes.get(f, getattr(paycheck, f)) for f in AMOUNT_FIELDS}
    check_adds_up(final)
    if paycheck.deposit_transaction_id is not None:
        deposit = session.get(Transaction, paycheck.deposit_transaction_id)
        account_id = changes.get("account_id", paycheck.account_id)
        if final["net_cents"] != deposit.amount_cents or account_id != deposit.account_id:
            raise ApiError(
                409,
                "linked_to_deposit",
                "This paycheck is linked to a bank deposit, so its net pay and account must "
                "match that deposit. Remove the link before changing them.",
            )
    if changes.get("account_id") is not None:
        get_account(session, changes["account_id"])
    for field, value in changes.items():
        setattr(paycheck, field, value)
    session.commit()
    return paycheck


def delete_paycheck(session: Session, paycheck_id: int) -> None:
    """Delete the paycheck. Its linked deposit, if any, stays in the bank account."""
    session.delete(get_paycheck(session, paycheck_id))
    session.commit()


def link_deposit(session: Session, paycheck_id: int, transaction_id: int) -> Paycheck:
    """Link a paycheck to the deposit of its net pay in a checking or savings account.

    The deposit must be a regular transaction (kind "normal") for exactly the net pay, and not
    already linked to another paycheck. The paycheck's account becomes the deposit's account.
    """
    paycheck = get_paycheck(session, paycheck_id)
    deposit = get_transaction(session, transaction_id)
    if paycheck.deposit_transaction_id == deposit.id:
        return paycheck  # already linked
    _attach_deposit(session, paycheck, deposit)
    session.commit()
    return paycheck


def _attach_deposit(session: Session, paycheck: Paycheck, deposit: Transaction) -> None:
    """``link_deposit``'s checks and the link itself, not saved yet."""
    if paycheck.deposit_transaction_id is not None:
        raise ApiError(
            409, "already_linked", "This paycheck is already linked to a deposit. Remove it first."
        )
    other = session.scalar(select(Paycheck.id).where(Paycheck.deposit_transaction_id == deposit.id))
    if other is not None:
        raise ApiError(409, "already_linked", "That deposit is already linked to another paycheck.")
    if deposit.kind != TransactionKind.NORMAL:
        raise ApiError(
            422, "invalid_deposit", "Only a regular deposit can be linked to a paycheck."
        )
    if session.get(Account, deposit.account_id).kind not in DEPOSIT_ACCOUNT_KINDS:
        raise ApiError(
            422,
            "invalid_deposit",
            "A paycheck can only be linked to a deposit in a checking or savings account.",
        )
    if deposit.amount_cents != paycheck.net_cents:
        raise ApiError(
            422,
            "invalid_deposit",
            "The deposit must be money coming in for exactly this paycheck's net pay.",
        )
    paycheck.deposit_transaction_id = deposit.id
    paycheck.account_id = deposit.account_id


def unlink_deposit(session: Session, paycheck_id: int) -> Paycheck:
    paycheck = get_paycheck(session, paycheck_id)
    if paycheck.deposit_transaction_id is None:
        raise ApiError(409, "not_linked", "This paycheck isn't linked to a deposit.")
    paycheck.deposit_transaction_id = None
    session.commit()
    return paycheck


def max_social_security_tax(wage_base_cents: int, rate: Decimal) -> int:
    """Most Social Security tax one person can owe on wages in a year, in cents.

    wage base x rate, rounded half up to the cent. Both 2025 and 2026 come out exact.
    """
    return int((Decimal(wage_base_cents) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def year_summary(session: Session, year: int) -> PaycheckSummary:
    """Year-to-date totals for paychecks paid in ``year`` (wages count in the year they're paid)."""
    paychecks = session.scalars(
        select(Paycheck).where(
            Paycheck.pay_date.between(dt.date(year, 1, 1), dt.date(year, 12, 31))
        )
    ).all()
    totals = {f: sum(getattr(p, f) for p in paychecks) for f in AMOUNT_FIELDS}
    # Employers are grouped ignoring case and spacing, under the first spelling seen.
    by_employer: dict[str, tuple[str, int]] = {}
    for p in sorted(paychecks, key=lambda p: (p.pay_date, p.id)):
        key = " ".join(p.employer.casefold().split())
        name, cents = by_employer.get(key, (p.employer, 0))
        by_employer[key] = (name, cents + p.social_security_cents)
    ss_by_employer = dict(by_employer.values())

    check, message = None, None
    try:
        fica = load_tax_year(year).fica
    except UnsupportedTaxYearError:
        message = (
            f"Budget Buddy doesn't have {year} tax figures yet, so it can't check Social Security "
            "against the yearly maximum."
        )
    else:
        check = _social_security_check(
            fica.social_security_wage_base_cents, fica.social_security_rate, ss_by_employer
        )
    return PaycheckSummary(
        year=year,
        paycheck_count=len(paychecks),
        totals=totals,
        taxes_withheld_cents=sum(totals[f] for f in TAX_FIELDS),
        pre_tax_deductions_cents=sum(totals[f] for f in PRE_TAX_FIELDS),
        after_tax_deductions_cents=sum(totals[f] for f in AFTER_TAX_FIELDS),
        social_security_by_employer=ss_by_employer,
        social_security_check=check,
        message=message,
    )


def _social_security_check(
    wage_base_cents: int, rate: Decimal, by_employer: dict[str, int]
) -> SocialSecurityCheck:
    max_tax = max_social_security_tax(wage_base_cents, rate)
    withheld = sum(by_employer.values())
    over = max(0, withheld - max_tax)
    limit = cents_to_display(max_tax)
    if not over:
        message = f"Social Security withheld is within this year's maximum of {limit}."
    elif any(cents > max_tax for cents in by_employer.values()):
        message = (
            f"One employer withheld more Social Security tax than this year's maximum of {limit}. "
            "Ask that employer to fix it; this kind of overpayment can't be claimed back on your "
            "tax return."
        )
    else:
        message = (
            f"Together your employers withheld {cents_to_display(over)} more Social Security tax "
            f"than this year's maximum of {limit}. This can happen when you have more than one "
            "job. You can usually claim it back as a credit on your federal tax return. "
            "This is an estimate, not tax advice."
        )
    if over:
        message += (
            " This check assumes every paycheck here is yours; the maximum applies to each person "
            "separately."
        )
    return SocialSecurityCheck(
        wage_base_cents=wage_base_cents,
        rate=str(rate),
        max_tax_cents=max_tax,
        withheld_cents=withheld,
        over_max_cents=over,
        message=message,
    )
