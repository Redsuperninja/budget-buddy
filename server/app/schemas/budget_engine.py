"""The suggested budget (roadmap #10): what to plan for each category, from recent months."""

from typing import Literal

from app.models import CategoryGroup
from app.schemas.common import Schema


class SuggestedCategory(Schema):
    category_id: int
    name: str
    group: CategoryGroup
    average_cents: int  # actual per month over the months with data
    current_budget_cents: int  # the budget as set now, for the month planned for
    suggested_cents: int
    suggested_percent_bp: int | None  # share of income_cents; None with no income


class SuggestedGroup(Schema):
    group: CategoryGroup
    guide_percent_bp: int  # the 50/30/20 guide for this group
    average_cents: int
    suggested_cents: int
    suggested_percent_bp: int | None


class BudgetSuggestion(Schema):
    month: str  # the month planned for, "YYYY-MM"
    looked_at: list[str]  # the full months before it that the averages come from
    months_with_data: int
    income_cents: int  # the income the plan shares out
    income_source: Literal["planned", "average"]
    average_income_cents: int
    # The part of the savings amount to move into your savings accounts: it belongs to no
    # category, so it isn't saved as a budget. Included in the savings group's suggestion.
    savings_by_transfer_cents: int
    groups: list[SuggestedGroup]
    categories: list[SuggestedCategory]
    notes: list[str]  # plain-English remarks, for example "only 1 month of history"


class ApplyChoice(Schema):
    month: str
    # "amounts": dollar budgets; "percentages": shares of income.
    use: Literal["amounts", "percentages"] = "amounts"


class ApplyResult(Schema):
    updated: int
    # Set when applying as percentages saved the average income as the planned income.
    planned_income_cents: int | None = None
