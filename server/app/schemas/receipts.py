import datetime as dt
from typing import Annotated

from pydantic import Field, StringConstraints

from app.money import MAX_ABS_CENTS
from app.schemas.common import Id, Notes, Schema, UpdateSchema

Merchant = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# What the receipt says you paid, in whole cents. Never negative.
TotalCents = Annotated[int, Field(strict=True, ge=0, lt=MAX_ABS_CENTS)]


class ReceiptCreate(Schema):
    date: dt.date
    merchant: Merchant
    total_cents: TotalCents
    category_id: Id | None = None
    transaction_id: Id | None = Field(default=None, description="The matching bank transaction.")
    tax_deductible: bool = False
    notes: Notes = None


class ReceiptUpdate(UpdateSchema):
    not_null = ("date", "merchant", "total_cents", "tax_deductible")

    date: dt.date | None = None
    merchant: Merchant | None = None
    total_cents: TotalCents | None = None
    category_id: Id | None = None
    transaction_id: Id | None = None
    tax_deductible: bool | None = None
    notes: Notes = None


class ReceiptOut(Schema):
    id: int
    date: dt.date
    merchant: str
    total_cents: int
    category_id: int | None
    transaction_id: int | None
    tax_deductible: bool
    notes: str | None
    has_image: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class ReceiptPage(Schema):
    items: list[ReceiptOut]
    total: int
    limit: int
    offset: int
