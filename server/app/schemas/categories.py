import datetime as dt

from pydantic import field_validator, model_validator

from app.models import CategoryGroup
from app.money import MAX_ABS_CENTS
from app.schemas.common import Name, Schema, UpdateSchema


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


class CategoryCreate(Schema):
    name: Name
    group: CategoryGroup
    # Applies to every month: changing it also changes what past months show.
    budget_cents: int = 0

    @field_validator("group", mode="before")
    @classmethod
    def _not_transfer(cls, value):
        if value == CategoryGroup.TRANSFER.value:
            raise ValueError(
                "Transfer is a built-in category. Pick needs, wants, savings, or income."
            )
        return value

    _budget = field_validator("budget_cents", mode="before")(_check_budget)


class CategoryUpdate(UpdateSchema):
    """Rename or change the monthly budget. The group can't change: that would quietly turn
    past spending into income (or the reverse)."""

    not_null = ("name", "budget_cents")

    name: Name | None = None
    budget_cents: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _no_group(cls, data):
        if isinstance(data, dict) and "group" in data:
            raise ValueError("A category's group can't be changed. Make a new category instead.")
        return data

    _budget = field_validator("budget_cents", mode="before")(_check_budget)


class CategoryOut(Schema):
    id: int
    name: str
    group: CategoryGroup
    budget_cents: int
    created_at: dt.datetime
    updated_at: dt.datetime
