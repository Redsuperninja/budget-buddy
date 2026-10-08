"""Monthly income and spending, worked out from the transactions.

Rules (docs/dev/architecture/ledger.md, "Transaction kinds"; budget-summary.md):
- Only ``normal`` and ``refund`` transactions count. Transfers and adjustments (including
  opening balances) change balances but are never income or spending.
- A normal transaction's category group decides: ``income`` is income; ``needs``, ``wants`` and
  ``savings`` are spending. Transfer-group categories are ignored.
- Spending is shown as money out = positive: ``-sum(amount_cents)``. A refund (always positive)
  or a reimbursement in a spending category lowers it. A refund is never income.
- Normal/refund transactions with no category (or a refund filed under an income or transfer
  category) can't be placed, so they go in ``unassigned`` (money in and money out
  separately, both positive) instead of being guessed at.
- A month runs from its first day through its last day, by the transaction's own date.
"""

import datetime as dt

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Category, CategoryGroup, Transaction, TransactionKind
from app.schemas.summary import CategoryTotal, GroupTotal, MonthlySummary

_SPENDING = (CategoryGroup.NEEDS, CategoryGroup.WANTS)
_REPORTED = (CategoryGroup.NEEDS, CategoryGroup.WANTS, CategoryGroup.SAVINGS, CategoryGroup.INCOME)


def month_range(year: int, month: int) -> tuple[dt.date, dt.date]:
    """First day of the month and first day of the next one (end is exclusive)."""
    start = dt.date(year, month, 1)
    end = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    return start, end


def monthly_summary(
    session: Session, year: int, month: int, *, through: dt.date | None = None
) -> MonthlySummary:
    """Totals for a month; with ``through``, only transactions dated up to that day."""
    start, end = month_range(year, month)
    if through is not None:
        end = min(end, through + dt.timedelta(days=1))
    rows = session.execute(
        select(
            Transaction.category_id,
            Transaction.kind,
            func.sum(case((Transaction.amount_cents > 0, Transaction.amount_cents), else_=0)),
            func.sum(case((Transaction.amount_cents < 0, Transaction.amount_cents), else_=0)),
            func.count(Transaction.id),
        )
        .where(
            Transaction.date >= start,
            Transaction.date < end,
            Transaction.kind.in_([TransactionKind.NORMAL, TransactionKind.REFUND]),
        )
        .group_by(Transaction.category_id, Transaction.kind)
    ).all()
    categories = list(session.scalars(select(Category).order_by(Category.group, Category.name)))
    by_id = {c.id: c for c in categories}

    sums = {c.id: 0 for c in categories}  # signed sum of amounts per placed category
    unassigned_in, unassigned_out, unassigned_count = 0, 0, 0
    for category_id, kind, money_in, money_out, count in rows:
        category = by_id.get(category_id)
        is_refund = kind == TransactionKind.REFUND
        placeable = category is not None and category.group in _REPORTED
        if placeable and is_refund and category.group == CategoryGroup.INCOME:
            placeable = False  # a refund is never income
        if placeable:
            sums[category_id] += money_in + money_out
        elif category is None or is_refund:
            unassigned_in += money_in
            unassigned_out -= money_out
            unassigned_count += count
        # else: a normal transaction in a transfer-group category: ignored on purpose.

    def actual(category: Category) -> int:
        total = sums[category.id]
        return total if category.group == CategoryGroup.INCOME else -total

    totals = [
        CategoryTotal(
            category_id=c.id,
            name=c.name,
            group=c.group,
            budget_cents=c.budget_cents,
            actual_cents=actual(c),
        )
        for c in categories
        if c.group in _REPORTED
    ]
    groups = [
        GroupTotal(
            group=g,
            budget_cents=sum(t.budget_cents for t in totals if t.group == g),
            actual_cents=sum(t.actual_cents for t in totals if t.group == g),
        )
        for g in _REPORTED
    ]
    by_group = {g.group: g for g in groups}
    return MonthlySummary(
        month=f"{year:04d}-{month:02d}",
        income_cents=by_group[CategoryGroup.INCOME].actual_cents,
        spending_cents=sum(by_group[g].actual_cents for g in _SPENDING),
        saved_cents=by_group[CategoryGroup.SAVINGS].actual_cents,
        spending_budget_cents=sum(by_group[g].budget_cents for g in _SPENDING),
        groups=groups,
        categories=totals,
        unassigned_in_cents=unassigned_in,
        unassigned_out_cents=unassigned_out,
        unassigned_count=unassigned_count,
    )
