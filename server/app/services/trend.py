"""Month-by-month totals for the dashboard's charts: money in, spending and saving, using the
monthly summary's own rules (services/summary.py), so the charts match the monthly page."""

from sqlalchemy.orm import Session

from app.schemas.summary import MonthlyTrend, TrendMonth
from app.services.summary import monthly_summary


def months_ending(year: int, month: int, count: int) -> list[tuple[int, int]]:
    """``count`` months up to and including ``year-month``, oldest first, as (year, month)."""
    last = year * 12 + (month - 1)
    return [(i // 12, i % 12 + 1) for i in range(last - count + 1, last + 1)]


def monthly_trend(session: Session, year: int, month: int, count: int) -> MonthlyTrend:
    months = []
    for y, m in months_ending(year, month, count):
        s = monthly_summary(session, y, m)
        months.append(
            TrendMonth(
                month=s.month,
                income_cents=s.income_cents,
                spending_cents=s.spending_cents,
                saved_cents=s.saved_cents,
            )
        )
    return MonthlyTrend(months=months)
