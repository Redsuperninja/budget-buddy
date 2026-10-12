"""The tax part of the phone snapshot (sync contract §5): totals only, no names or notes."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Deduction, Donation
from app.services.investing import stock_sales
from app.services.tax.deductions import label

TAX_DISCLAIMER = "These totals help you get ready for tax time. They aren't tax advice."


def tax_summary(session: Session, year: int) -> dict:
    start, end = dt.date(year, 1, 1), dt.date(year, 12, 31)
    donations = session.scalar(
        select(func.coalesce(func.sum(Donation.amount_cents), 0)).where(
            Donation.date >= start, Donation.date <= end
        )
    )
    gains = stock_sales.gains_summary(session, year)
    by_kind = session.execute(
        select(Deduction.kind, func.sum(Deduction.amount_cents))
        .where(Deduction.tax_year == year)
        .group_by(Deduction.kind)
    ).all()
    deductions = sorted(
        (
            {
                "kind": kind.value,
                "label": label(kind),
                "amount_cents": total,
                "is_estimate": False,
            }
            for kind, total in by_kind
        ),
        key=lambda d: d["kind"],
    )
    return {
        "year": year,
        "donations_total_cents": donations,
        "realized_gains": {
            "short_term_cents": gains.short_term.gain_cents,
            "long_term_cents": gains.long_term.gain_cents,
            # A possible wash sale means the gain may change once the loss is adjusted.
            "is_estimate": gains.possible_wash_sale_count > 0,
        },
        "deductions": deductions,
        "disclaimer": TAX_DISCLAIMER,
    }
