"""The yearly tax summary (roadmap #13): pay, donations, stock gains and other deductions for one
tax year, built from the existing services so it shows the same numbers as their own pages.

Nothing here adds different kinds of deductions together: they follow different rules (see
``services/deductions.py``). The standard deduction is shown from the year's tax data file only for
comparison. An estimate to get records together, not tax advice.
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tax_data
from app.models import Deduction, Donation, DonationKind
from app.schemas.tax_summary import DeductionTotal, Line, TaxSummary
from app.services import deductions, paychecks
from app.services.investing import stock_sales

DISCLAIMER = (
    "These totals help you gather your records for tax time. They are estimates, not tax advice, "
    "and they don't say what you can deduct: limits depend on your income, your filing status and "
    "whether you itemize. Check the IRS instructions or ask a tax professional before you file."
)

PAY_LABELS = {
    "gross_cents": "Gross pay",
    "federal_tax_cents": "Federal income tax withheld",
    "state_tax_cents": "State income tax withheld",
    "social_security_cents": "Social Security tax withheld",
    "medicare_cents": "Medicare tax withheld",
    "retirement_cents": "Pre-tax retirement (401(k), 403(b), 457)",
    "hsa_cents": "HSA through your paycheck",
    "health_insurance_cents": "Pre-tax health benefits",
    "roth_retirement_cents": "Roth retirement",
    "other_deductions_cents": "Other after-tax deductions",
    "net_cents": "Take-home pay",
}


def _deduction_totals(session: Session, year: int) -> list[DeductionTotal]:
    rows = session.execute(
        select(Deduction.kind, func.count(Deduction.id), func.sum(Deduction.amount_cents))
        .where(Deduction.tax_year == year)
        .group_by(Deduction.kind)
        .order_by(Deduction.kind)
    ).all()
    return [
        DeductionTotal(
            kind=kind,
            label=deductions.label(kind),
            count=count,
            amount_cents=total,
            where=deductions.WHERE[kind],
            where_text=deductions.hint(kind),
        )
        for kind, count, total in rows
    ]


def _donation_totals(session: Session, year: int) -> tuple[int, dict[DonationKind, int]]:
    """How many gifts dated in ``year``, and their total by kind (no tax data needed)."""
    rows = session.execute(
        select(Donation.kind, func.count(Donation.id), func.sum(Donation.amount_cents))
        .where(Donation.date >= dt.date(year, 1, 1), Donation.date <= dt.date(year, 12, 31))
        .group_by(Donation.kind)
    ).all()
    return sum(r[1] for r in rows), {kind: total for kind, _, total in rows}


def _standard_deduction(year: int) -> dict[str, int] | None:
    try:
        basic = tax_data.load_tax_year(year).standard_deduction.basic_cents
    except tax_data.UnsupportedTaxYearError:
        return None
    return {status: basic.for_status(status) for status in tax_data.FILING_STATUSES}


def build(session: Session, year: int) -> TaxSummary:
    pay = paychecks.year_summary(session, year)
    gift_count, gifts = _donation_totals(session, year)
    cash, goods = gifts.get(DonationKind.CASH, 0), gifts.get(DonationKind.GOODS, 0)
    gains = stock_sales.gains_summary(session, year)
    return TaxSummary(
        tax_year=year,
        generated_on=dt.date.today(),
        disclaimer=DISCLAIMER,
        paycheck_count=pay.paycheck_count,
        pay=[Line(label=text, amount_cents=pay.totals.get(f, 0)) for f, text in PAY_LABELS.items()],
        donation_count=gift_count,
        donations=[
            Line(label="Cash gifts", amount_cents=cash),
            Line(label="Goods (value when given)", amount_cents=goods),
            Line(label="All gifts", amount_cents=cash + goods),
        ],
        stock_sale_count=len(gains.sales),
        stocks=[
            Line(label="Short-term gain or loss", amount_cents=gains.short_term.gain_cents),
            Line(label="Long-term gain or loss", amount_cents=gains.long_term.gain_cents),
            Line(label="Total gain or loss", amount_cents=gains.total_gain_cents),
        ],
        possible_wash_sale_count=gains.possible_wash_sale_count,
        deductions=_deduction_totals(session, year),
        standard_deduction_cents=_standard_deduction(year),
    )
