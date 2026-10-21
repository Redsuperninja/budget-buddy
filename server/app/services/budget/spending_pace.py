"""Spending pace: how much you'd spent by each day of a month, against the month's spending budget,
for the Home chart. Days after today aren't listed.

Spent by a day is the monthly summary's ``spending_cents`` up to that day (as with
``monthly_summary(through=)``), worked out in one pass: one grouped query of each day's needs +
wants total over the summary's ``counted()`` transactions (a refund or reimbursement lowers it),
then a running total. The budget comes from one whole-month summary, as before.
tests/budget/test_spending_pace_equivalence.py checks this against one summary per day."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.schemas.budget.summary import PaceDay, SpendingPace
from app.services.budget.summary import SPENDING, counted, month_range, monthly_summary


def _today() -> dt.date:
    return dt.date.today()


def _net_by_day(session: Session, start: dt.date, end: dt.date) -> dict[dt.date, int]:
    """Signed sum of needs + wants amounts on each day in [start, end): the same rows the summary
    places in a spending category."""
    return dict(
        session.execute(
            select(Transaction.date, func.sum(Transaction.amount_cents))
            .join(Category, Category.id == Transaction.category_id)
            .where(
                Transaction.date >= start,
                Transaction.date < end,
                Category.group.in_(SPENDING),
                *counted(),
            )
            .group_by(Transaction.date)
        ).all()
    )


def spending_pace(session: Session, year: int, month: int) -> SpendingPace:
    today = _today()
    start, end = month_range(year, month)
    last = min(end - dt.timedelta(days=1), today)
    days = []
    if start <= last:
        net = _net_by_day(session, start, last + dt.timedelta(days=1))
        running, day = 0, start
        while day <= last:
            running += net.get(day, 0)
            days.append(PaceDay(date=day, spent_cents=-running))  # money out is positive
            day += dt.timedelta(days=1)
    whole = monthly_summary(session, year, month)
    return SpendingPace(
        month=whole.month,
        days_in_month=(end - start).days,
        budget_cents=whole.spending_budget_cents,
        days=days,
        complete=end <= today,
    )
