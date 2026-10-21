"""The spending pace adds up each day exactly as the old way did: the monthly summary up to that
day, one summary per day. Random made-up ledgers, every month around them, several "todays"."""

import datetime as dt
import random

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.models.enums import TransactionKind, TransactionSource
from app.schemas.budget.summary import PaceDay, SpendingPace
from app.services.budget import spending_pace
from app.services.budget.summary import month_range, monthly_summary

MONTHS = [(2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4)]
TODAYS = [dt.date(2025, 11, 30), dt.date(2026, 1, 1), dt.date(2026, 2, 14), dt.date(2026, 2, 28),
          dt.date(2026, 3, 1), dt.date(2026, 3, 31), dt.date(2026, 6, 1)]  # fmt: skip
KINDS = [TransactionKind.NORMAL] * 6 + [TransactionKind.REFUND] * 2 + [
    TransactionKind.TRANSFER, TransactionKind.ADJUSTMENT]  # fmt: skip


def old_pace(session: Session, year: int, month: int, today: dt.date) -> SpendingPace:
    """The pace as it was worked out before: ``monthly_summary(through=day)`` for every day."""
    start, end = month_range(year, month)
    last = min(end - dt.timedelta(days=1), today)
    days, day = [], start
    while day <= last:
        spent = monthly_summary(session, year, month, through=day).spending_cents
        days.append(PaceDay(date=day, spent_cents=spent))
        day += dt.timedelta(days=1)
    whole = monthly_summary(session, year, month)
    return SpendingPace(month=whole.month, days_in_month=(end - start).days,
                        budget_cents=whole.spending_budget_cents, days=days,
                        complete=end <= today)  # fmt: skip


def random_ledger(client, make_account, add_txn, rng: random.Random) -> None:
    checking = make_account()["id"]
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    # Linked roles the summary leaves out: a dividend kept inside and its sweep.
    add_txn(ira, 130, date="2026-02-08", description="FAKECO CASH DIV")
    add_txn(ira, -130, date="2026-02-08", description="FAKE DEPOSIT SWEEP")
    if rng.random() < 0.5:
        client.put("/api/local/budget/plan", json={"planned_income_cents": rng.randint(0, 500_000)})
    with Session(client.app.state.engine) as session:
        categories = list(session.scalars(select(Category)))
        for category in categories:
            if rng.random() < 0.3:
                category.budget_percent_bp = rng.randint(0, 3_000)
            else:
                category.budget_cents = rng.randint(0, 50_000)
        ids = [c.id for c in categories] + [None] * 3
        first = dt.date(2025, 12, 1)
        for _ in range(250):
            kind = rng.choice(KINDS)
            amount = rng.randint(1, 30_000) * (1 if kind == TransactionKind.REFUND else
                                               rng.choice([-1, -1, -1, 1]))  # fmt: skip
            session.add(Transaction(
                account_id=rng.choice([checking, savings]), amount_cents=amount,
                date=first + dt.timedelta(days=rng.randrange(0, 151)), kind=kind,
                category_id=rng.choice(ids), source=TransactionSource.MANUAL,
                description="FAKE ITEM"))  # fmt: skip
        session.commit()
        # Leave March without spending: only income and money that isn't spending.
        march = (Transaction.date >= dt.date(2026, 3, 1), Transaction.date < dt.date(2026, 4, 1))
        for t in session.scalars(select(Transaction).where(*march)):
            category = session.get(Category, t.category_id) if t.category_id else None
            if category is not None and category.group in ("needs", "wants"):
                t.category_id = None
        session.commit()


@pytest.mark.parametrize("seed", [1, 2])
def test_same_as_one_summary_per_day(client, make_account, add_txn, monkeypatch, seed):
    random_ledger(client, make_account, add_txn, random.Random(seed))
    spent = {}
    with Session(client.app.state.engine) as session:
        for today in TODAYS:
            monkeypatch.setattr(spending_pace, "_today", lambda today=today: today)
            for year, month in MONTHS:
                new = spending_pace.spending_pace(session, year, month)
                assert new == old_pace(session, year, month, today), (today, year, month)
                spent[today, month] = {d.spent_cents for d in new.days}
    # The data really is varied: spending goes up and down, and March has none.
    assert len(spent[dt.date(2026, 6, 1), 2]) > 5 and spent[dt.date(2026, 6, 1), 3] == {0}
