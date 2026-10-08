"""The budget snapshot the Home Base sends to a paired phone (sync contract §5).

Everything here is read-only and built from the existing services, so the phone sees the same
numbers as the dashboard. The snapshot is the whole list of what a phone may see: month totals
per budget category, the last 60 days of transactions (date, short description, amount,
category, account), account names and balances, and tax totals. It never includes account
numbers, notes, receipt photos, employer names, or any other field the contract doesn't list.

Money is integer cents; dates are ISO ``YYYY-MM-DD``. Nothing is logged.
"""

import calendar
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CategoryGroup, Paycheck, Transaction
from app.schemas.summary import MonthlySummary
from app.services import accounts as account_service
from app.services.pairing import CONTRACT
from app.services.snapshot_tax import tax_summary
from app.services.summary import monthly_summary

CURRENCY = "USD"  # the app has no currency setting yet; amounts are US dollars
TRANSACTION_DAYS = 60
MAX_TRANSACTIONS = 500
DESCRIPTION_MAX = 100
REMINDER_DAYS_DEFAULT = 2
REMINDER_DAYS_ALLOWED = [1, 2, 3]

_GROUPS = (
    (CategoryGroup.NEEDS, "Needs"),
    (CategoryGroup.WANTS, "Wants"),
    (CategoryGroup.SAVINGS, "Savings"),
)


def local_today(now: int) -> dt.date:
    """Today's date on this computer's calendar (``now`` is Unix seconds)."""
    return dt.datetime.fromtimestamp(now).date()


def utc_timestamp(now: int) -> str:
    """RFC 3339 UTC with a ``Z``, e.g. ``2026-10-02T18:30:00Z``."""
    moment = dt.datetime.fromtimestamp(now, dt.UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_snapshot(session: Session, *, now: int, server_id: str) -> dict:
    today = local_today(now)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    summary = monthly_summary(session, today.year, today.month)
    return {
        "contract": CONTRACT,
        "server_id": server_id,
        "generated_at": utc_timestamp(now),
        "currency": CURRENCY,
        "period": {
            "month": f"{today.year:04d}-{today.month:02d}",
            "start": today.replace(day=1).isoformat(),
            "end": today.replace(day=days_in_month).isoformat(),
            "days_elapsed": today.day,
            "days_in_month": days_in_month,
        },
        "income": _income(session, today),
        "budget": _budget(summary),
        "transactions": _transactions(session, today),
        "accounts": _accounts(session, today),
        "tax": tax_summary(session, today.year),
        "settings": {
            "reminder_days_default": REMINDER_DAYS_DEFAULT,
            "reminder_days_allowed": REMINDER_DAYS_ALLOWED,
        },
    }


def _income(session: Session, today: dt.date) -> dict:
    """Take-home pay only: refunds, transfers and adjustments never count as income.

    ``received`` is the income transactions dated up to today (never below zero, the phone rejects
    negatives). ``expected`` is the larger of received so far and this month's paycheck take-home.
    """
    start = today.replace(day=1)
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    received_so_far = monthly_summary(session, today.year, today.month, through=today)
    received = max(0, received_so_far.income_cents)
    this_month = session.scalar(
        select(func.coalesce(func.sum(Paycheck.net_cents), 0)).where(
            Paycheck.pay_date >= start, Paycheck.pay_date <= end
        )
    )
    last = session.execute(
        select(Paycheck.pay_date, Paycheck.net_cents)
        .where(Paycheck.pay_date <= today)
        .order_by(Paycheck.pay_date.desc(), Paycheck.id.desc())
        .limit(1)
    ).first()
    return {
        "expected_cents": max(received, this_month),
        "received_cents": received,
        "last_paycheck": (
            {"pay_date": last.pay_date.isoformat(), "net_cents": last.net_cents} if last else None
        ),
    }


def _budget(summary: MonthlySummary) -> dict:
    totals = {g.group: g for g in summary.groups}
    groups = []
    for group, name in _GROUPS:
        groups.append(
            {
                "group": group.value,
                "name": name,
                "target_cents": totals[group].budget_cents,
                "actual_cents": totals[group].actual_cents,
                "categories": [
                    {
                        "id": c.category_id,
                        "name": c.name,
                        "target_cents": c.budget_cents,
                        "actual_cents": c.actual_cents,
                    }
                    for c in summary.categories
                    if c.group == group
                ],
            }
        )
    return {
        "target_cents": sum(g["target_cents"] for g in groups),
        "actual_cents": sum(g["actual_cents"] for g in groups),
        "groups": groups,
        # Money that couldn't be placed in a budget category (no category, or a refund).
        "unassigned": {
            "in_cents": max(0, summary.unassigned_in_cents),
            "out_cents": max(0, summary.unassigned_out_cents),
            "count": summary.unassigned_count,
        },
    }


def _transactions(session: Session, today: dt.date) -> list[dict]:
    first = today - dt.timedelta(days=TRANSACTION_DAYS - 1)
    rows = session.execute(
        select(
            Transaction.id,
            Transaction.date,
            Transaction.description,
            Transaction.amount_cents,
            Transaction.category_id,
            Transaction.account_id,
        )
        .where(Transaction.date >= first, Transaction.date <= today)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(MAX_TRANSACTIONS)
    )
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "description": r.description.strip()[:DESCRIPTION_MAX],
            "amount_cents": r.amount_cents,
            "category_id": r.category_id,
            "account_id": r.account_id,
        }
        for r in rows
    ]


def _accounts(session: Session, today: dt.date) -> list[dict]:
    """Every account. Balances count only transactions up to today, matching ``balance_as_of``.

    A credit card or loan balance is negative when money is owed.
    """
    rows = session.execute(
        select(
            Transaction.account_id,
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.max(Transaction.date),
        )
        .where(Transaction.date <= today)
        .group_by(Transaction.account_id)
    ).all()
    totals = {account_id: (balance, latest) for account_id, balance, latest in rows}
    return [
        {
            "id": a.id,
            "name": a.name,
            "kind": a.kind.value,
            "balance_cents": totals.get(a.id, (0, today))[0],
            "balance_as_of": totals.get(a.id, (0, today))[1].isoformat(),
        }
        for a in account_service.list_accounts(session)
    ]
