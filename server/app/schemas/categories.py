import datetime as dt

from pydantic import field_validator, model_validator

from app.models import CategoryGroup
from app.money import MAX_ABS_CENTS
from app.percent import WHOLE_BP
from app.schemas.common import Name, Schema, UpdateSchema

BOTH_BUDGETS = "Set the budget as an amount or as a percentage of income, not both."
INCOME_PERCENT = "An income category's budget can't be a percentage of income. Enter an amount."


def _check_budget(value):
    """Plain-English budget checks (a monthly target in whole cents, never negative)."""
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Enter the budget in whole cents, like 25000 for $250.00.")
    if value < 0:
        raise ValueError("The budget can't be negative.")
    if value >= MAX_ABS_CENTS:
        raise ValueError("That budget is too large.")
    return value


def _check_percent(value):
    """A share of income in basis points: 1 (0.01%) to 10000 (100%)."""
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= WHOLE_BP:
        raise ValueError(
            "Enter the percentage in hundredths of a percent, from 1 to 10000 (1500 is 15%)."
        )
    return value


class CategoryCreate(Schema):
    name: Name
    group: CategoryGroup
    # Applies to every month: changing it also changes what past months show.
    budget_cents: int = 0
    # Or: a share of monthly income in basis points (1500 = 15%). Not for income categories.
    budget_percent_bp: int | None = None

    @field_validator("group", mode="before")
    @classmethod
    def _not_transfer(cls, value):
        if value == CategoryGroup.TRANSFER.value:
            raise ValueError(
                "Transfer is a built-in category. Pick needs, wants, savings, or income."
            )
        return value

    _budget = field_validator("budget_cents", mode="before")(_check_budget)
    _percent = field_validator("budget_percent_bp", mode="before")(_check_percent)

    @model_validator(mode="after")
    def _one_kind_of_budget(self):
        if self.budget_percent_bp is not None:
            if self.budget_cents:
                raise ValueError(BOTH_BUDGETS)
            if self.group == CategoryGroup.INCOME:
                raise ValueError(INCOME_PERCENT)
        return self


class CategoryUpdate(UpdateSchema):
    """Rename or change the monthly budget. The group can't change: that would quietly turn
    past spending into income (or the reverse). Sending ``budget_cents`` switches the category
    to an amount budget; sending ``budget_percent_bp`` switches it to a percentage."""

    not_null = ("name", "budget_cents")

    name: Name | None = None
    budget_cents: int | None = None
    budget_percent_bp: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_group(cls, data):
        if isinstance(data, dict) and "group" in data:
            raise ValueError("A category's group can't be changed. Make a new category instead.")
        return data

    _budget = field_validator("budget_cents", mode="before")(_check_budget)
    _percent = field_validator("budget_percent_bp", mode="before")(_check_percent)

    @model_validator(mode="after")
    def _one_kind_of_budget(self):
        if "budget_cents" in self.model_fields_set and self.budget_percent_bp is not None:
            raise ValueError(BOTH_BUDGETS)
        return self


class CategoryOut(Schema):
    id: int
    name: str
    group: CategoryGroup
    budget_cents: int
    budget_percent_bp: int | None
    created_at: dt.datetime
    updated_at: dt.datetime
