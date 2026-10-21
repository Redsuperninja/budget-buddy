"""Month-by-month totals for the dashboard's charts: money in, spending and saving, using the
monthly summary's own rules (services/budget/summary.py), so the charts match the monthly page;
and net worth at each month's end, the sum of every transaction dated before the next month. For
this month (and any later one) that stops at today, so a bill dated later this month doesn't count
yet: the same as Home's balances (``current_balance_cents``)."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.schemas.budget.summary import MonthlyTrend, TrendMonth
from app.services.budget.summary import month_range, monthly_summary


def months_ending(year: int, month: int, count: int) -> list[tuple[int, int]]:
    """``count`` months up to and including ``year-month``, oldest first, as (year, month)."""
    last = year * 12 + (month - 1)
    return [(i // 12, i % 12 + 1) for i in range(last - count + 1, last + 1)]


def _net_worths(session: Session, spans: list[tuple[int, int]]) -> list[int]:
    """Net worth at each of these (year, month)s: everything dated before the month's end (capped
    at tomorrow). One total before the first month plus one grouped query for the months, then a
    running total, instead of a whole-table sum per month."""
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    ends = [min(month_range(y, m)[1], tomorrow) for y, m in spans]
    first = min(month_range(*spans[0])[0], tomorrow)
    month_key = func.strftime("%Y-%m", Transaction.date)
    before = session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.date < first)
    )
    per_month = dict(
        session.execute(
            select(month_key, func.sum(Transaction.amount_cents))
            .where(Transaction.date >= first, Transaction.date < ends[-1])
            .group_by(month_key)
        ).all()
    )
    worths, running = [], before
    for y, m in spans:
        running += per_month.get(f"{y:04d}-{m:02d}", 0)
        worths.append(running)
    return worths


def monthly_trend(session: Session, year: int, month: int, count: int) -> MonthlyTrend:
    spans = months_ending(year, month, count)
    worths = _net_worths(session, spans) if spans else []
    months = []
    for (y, m), worth in zip(spans, worths, strict=True):
        s = monthly_summary(session, y, m)
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
