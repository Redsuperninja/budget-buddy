"""Other deductions (roadmap #13): medical bills, mortgage interest, IRA contributions and so on."""

import datetime as dt
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.models import DeductionKind
from app.schemas.common import Cents, DollarText, Id, Schema, UpdateSchema, pick_cents

TaxYear = Annotated[int, Field(strict=True, ge=2000, le=2100)]
Description = Annotated[
    str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


def _not_negative(cents: int | None) -> int | None:
    if cents is not None and cents < 0:
        raise ValueError("A deduction amount can't be negative.")
    return cents


def _date_in_year(date: dt.date | None, tax_year: int | None) -> None:
    if date is not None and tax_year is not None and date.year != tax_year:
        raise ValueError("The date has to be in the tax year you picked.")


class DeductionCreate(Schema):
    """Send ``amount_cents`` or ``amount`` (dollars as text), not both."""

    tax_year: TaxYear
    kind: DeductionKind
    description: Description = None
    date: dt.date | None = None
    amount_cents: Cents | None = None
    amount: DollarText | None = None
    receipt_id: Id | None = None

    @model_validator(mode="after")
    def _check(self):
        cents = _not_negative(pick_cents(self.amount_cents, self.amount))
        if cents is None:
            raise ValueError("An amount is required: send amount_cents or amount.")
        self.amount_cents, self.amount = cents, None
        _date_in_year(self.date, self.tax_year)
        return self


class DeductionUpdate(UpdateSchema):
    not_null = ("tax_year", "kind", "amount_cents")

    tax_year: TaxYear | None = None
    kind: DeductionKind | None = None
    description: Description = None
    date: dt.date | None = None
    amount_cents: Cents | None = None
    amount: DollarText | None = None
    receipt_id: Id | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.amount is not None:
            self.amount_cents = pick_cents(self.amount_cents, self.amount)
            self.amount = None
            self.model_fields_set.discard("amount")
            self.model_fields_set.add("amount_cents")
        _not_negative(self.amount_cents)
        return self


class DeductionOut(Schema):
    id: int
    tax_year: int
    kind: DeductionKind
    description: str | None
    date: dt.date | None
    amount_cents: int
    receipt_id: int | None
    created_at: dt.datetime
    updated_at: dt.datetime
