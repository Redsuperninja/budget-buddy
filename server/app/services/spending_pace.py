"""Spending pace: how much you'd spent by each day of a month, against the month's spending budget,
for the Home chart. Each day is the monthly summary up to that day (``monthly_summary(through=)``),
so the numbers always match the summary's rules. Days after today aren't listed."""

import datetime as dt

from sqlalchemy.orm import Session

from app.schemas.summary import PaceDay, SpendingPace
from app.services.summary import month_range, monthly_summary


def _today() -> dt.date:
    return dt.date.today()


def spending_pace(session: Session, year: int, month: int) -> SpendingPace:
    today = _today()
    start, end = month_range(year, month)
    last = min(end - dt.timedelta(days=1), today)
    days = []
    day = start
    while day <= last:
        spent = monthly_summary(session, year, month, through=day).spending_cents
        days.append(PaceDay(date=day, spent_cents=spent))
        day += dt.timedelta(days=1)
    whole = monthly_summary(session, year, month)
    return SpendingPace(
        month=whole.month,
        days_in_month=(end - start).days,
        budget_cents=whole.spending_budget_cents,
        days=days,
        complete=end <= today,
    )
