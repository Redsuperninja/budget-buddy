"""Budget settings, and the income that percentage budgets are shares of.

A category with ``budget_percent_bp`` has a budget of that share of the month's *budget income*:
the planned monthly income when one is saved, otherwise that month's actual income (never below
zero). Planned income keeps the budgets steady through the month; without it, a percentage budget
grows as the month's pay comes in.
"""

from typing import Literal

from sqlalchemy.orm import Session

from app.models import BudgetPlan, Category, CategoryGroup
from app.percent import share_of
from app.schemas.budget_plan import BudgetPlanIn, BudgetPlanOut

PLAN_ID = 1
IncomeSource = Literal["planned", "actual"]


def get_plan(session: Session) -> BudgetPlanOut:
    plan = session.get(BudgetPlan, PLAN_ID)
    return BudgetPlanOut(planned_income_cents=plan.planned_income_cents if plan else None)


def save_plan(session: Session, data: BudgetPlanIn) -> BudgetPlanOut:
    plan = session.get(BudgetPlan, PLAN_ID) or BudgetPlan(id=PLAN_ID)
    plan.planned_income_cents = data.planned_income_cents
    session.add(plan)
    session.commit()
    return get_plan(session)


def budget_income(session: Session, actual_income_cents: int) -> tuple[int, IncomeSource]:
    """The income percentage budgets are shares of, and where it came from."""
    planned = get_plan(session).planned_income_cents
    if planned is not None:
        return planned, "planned"
    return max(0, actual_income_cents), "actual"


def budget_for(category: Category, income_cents: int) -> int:
    """A category's budget in cents for a month with this budget income. Income categories have
    none (one saved by an older version is ignored): income is what budgets are measured against."""
    if category.group == CategoryGroup.INCOME:
        return 0
    if category.budget_percent_bp is None:
        return category.budget_cents
    return share_of(income_cents, category.budget_percent_bp)
