from app.models import CategoryGroup
from app.schemas.common import Schema


class CategoryTotal(Schema):
    category_id: int
    name: str
    group: CategoryGroup
    # Applies to every month, not just this one.
    # Applies to every month, not just this one.
    budget_cents: int
    # Needs, wants, savings: money spent (or put into savings) this month, refunds netted off.
    # Income: money received.
    actual_cents: int


class GroupTotal(Schema):
    group: CategoryGroup
    budget_cents: int
    actual_cents: int


class MonthlySummary(Schema):
    month: str  # "YYYY-MM"
    income_cents: int
    # Needs + wants, refunds netted off. Can be negative if refunds exceed spending.
    spending_cents: int
    # Savings group, same sign rule as spending. Money moved to your own savings account
    # isn't counted here yet.
    saved_cents: int
    # Needs + wants budgets (what you planned to spend). Budgets apply to every month, so
    # changing one also changes what past months show. Budgets apply to every month, so
    # changing one also changes what past months show.
    spending_budget_cents: int
    groups: list[GroupTotal]
    categories: list[CategoryTotal]
    # Regular transactions and refunds with no usable category. Not in the totals above;
    # both amounts are positive. Shown so nothing silently goes missing.
    unassigned_in_cents: int
    unassigned_out_cents: int
    unassigned_count: int
