"""Budget settings: the planned monthly income that percentage budgets are shares of."""

from typing import Annotated

from pydantic import Field

from app.money import MAX_ABS_CENTS
from app.schemas.common import Schema

PlannedIncome = Annotated[int, Field(strict=True, ge=0, lt=MAX_ABS_CENTS)]


class BudgetPlanIn(Schema):
    # null: use each month's actual income instead.
    planned_income_cents: PlannedIncome | None


class BudgetPlanOut(Schema):
    planned_income_cents: int | None
