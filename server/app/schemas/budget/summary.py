import datetime as dt
from typing import Literal

from app.models import CategoryGroup
from app.schemas.common import Schema


class CategoryTotal(Schema):
    category_id: int
    name: str
    group: CategoryGroup
    # This month's budget. Applies to every month; for a percentage budget it's the share of this
    # month's budget income (see MonthlySummary.budget_income_cents).
    budget_cents: int
    # Set when the budget is a percentage of income, in basis points (1500 = 15%).
    budget_percent_bp: int | None
    # Needs, wants, savings: money spent (or put into savings) this month, refunds netted off.
    # Income: money received.
    actual_cents: int


class GroupTotal(Schema):
    group: CategoryGroup
    budget_cents: int
    actual_cents: int
    # Needs, wants, savings: actual as a share of this month's *actual* income (not the planned
    # income budgets may use), in basis points. None for the income group or with no income.
    percent_of_income_bp: int | None


class MonthlySummary(Schema):
    month: str  # "YYYY-MM"
    income_cents: int
    # Needs + wants, refunds netted off. Can be negative if refunds exceed spending.
    spending_cents: int
    # Savings group, same sign rule as spending, including saved_by_transfer_cents.
    saved_cents: int
    # Linked transfers into your own savings-type accounts minus transfers back out. Part of
    # saved_cents and the savings group's actual, but of no category.
    saved_by_transfer_cents: int
    # Needs + wants budgets (what you planned to spend). Budgets apply to every month, so
    # changing one also changes what past months show.
    spending_budget_cents: int
    # The income percentage budgets are shares of: the planned monthly income, or this month's
    # actual income (never below zero) when none is planned.
    budget_income_cents: int
    budget_income_source: Literal["planned", "actual"]
    groups: list[GroupTotal]
    categories: list[CategoryTotal]
    # Regular transactions and refunds with no usable category. Not in the totals above;
    # both amounts are positive. Shown so nothing silently goes missing.
    unassigned_in_cents: int
    unassigned_out_cents: int
    unassigned_count: int


class TrendMonth(Schema):
    month: str  # "YYYY-MM"
    income_cents: int
    spending_cents: int  # can be negative when refunds were bigger than spending
    saved_cents: int  # can be negative when more came out of savings than went in
    # What you have minus what you owe at the month's end: every account's balance (as on Home).
    net_worth_cents: int


class MonthlyTrend(Schema):
    months: list[TrendMonth]  # oldest first


class PaceDay(Schema):
    date: dt.date
    spent_cents: int  # needs + wants spent from the 1st through this day (the summary's rules)


class SpendingPace(Schema):
    month: str  # "YYYY-MM"
    days_in_month: int
    budget_cents: int  # needs + wants budgets for the month
    days: list[PaceDay]  # the 1st up to today (or the month's last day), oldest first
    complete: bool  # the month is over (its last day is before today)
