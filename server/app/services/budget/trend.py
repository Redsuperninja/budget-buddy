"""Month-by-month totals for the dashboard's charts: money in, spending and saving, using the
monthly summary's own rules (services/budget/summary.py), so the charts match the monthly page;
and net worth at each month's end, the sum of every transaction dated before the next month (the
balances on Home are the same sums, up to today)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.schemas.budget.summary import MonthlyTrend, TrendMonth
from app.services.budget.summary import month_range, monthly_summary


def months_ending(year: int, month: int, count: int) -> list[tuple[int, int]]:
    """``count`` months up to and including ``year-month``, oldest first, as (year, month)."""
    last = year * 12 + (month - 1)
    return [(i // 12, i % 12 + 1) for i in range(last - count + 1, last + 1)]


def monthly_trend(session: Session, year: int, month: int, count: int) -> MonthlyTrend:
    months = []
    for y, m in months_ending(year, month, count):
        s = monthly_summary(session, y, m)
        end = month_range(y, m)[1]
        total = func.coalesce(func.sum(Transaction.amount_cents), 0)
        worth = session.scalar(select(total).where(Transaction.date < end))
        months.append(
            TrendMonth(
                month=s.month,
                income_cents=s.income_cents,
                spending_cents=s.spending_cents,
                saved_cents=s.saved_cents,
                net_worth_cents=worth,
            )
        )
    return MonthlyTrend(months=months)
