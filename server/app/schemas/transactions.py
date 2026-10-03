import datetime as dt
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.models import TransactionKind, TransactionSource
from app.schemas.common import (
    Cents,
    DollarText,
    Id,
    Notes,
    Schema,
    UpdateSchema,
    resolve_amount,
)

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
# "transfer" is set only by linking two transactions (POST .../transfer), never directly.
EditableKind = Literal[TransactionKind.NORMAL, TransactionKind.REFUND, TransactionKind.ADJUSTMENT]


class TransactionCreate(Schema):
    """Negative amount = money out, positive = money in. Send ``amount_cents`` or ``amount``."""

    account_id: Id
    date: dt.date
    amount_cents: Cents | None = None
    amount: DollarText | None = None
    description: Description
    category_id: Id | None = None
    kind: EditableKind = TransactionKind.NORMAL
    notes: Notes = None

    @model_validator(mode="after")
    def _amount(self):
        self.amount_cents = resolve_amount(self.amount_cents, self.amount)
        if self.amount_cents is None:
            raise ValueError("An amount is required: send amount_cents or amount.")
        self.amount = None
        return self


class TransactionUpdate(UpdateSchema):
    not_null = ("account_id", "date", "amount_cents", "description", "kind")

    account_id: Id | None = None
    date: dt.date | None = None
    amount_cents: Cents | None = None
    amount: DollarText | None = None
    description: Description | None = None
    category_id: Id | None = None
    kind: EditableKind | None = None
    notes: Notes = None

    @model_validator(mode="after")
    def _amount(self):
        if self.amount is not None:
            self.amount_cents = resolve_amount(self.amount_cents, self.amount)
            self.amount = None
            self.model_fields_set.discard("amount")
            self.model_fields_set.add("amount_cents")
        elif self.amount_cents is not None:
            resolve_amount(self.amount_cents, None)  # rejects zero
        return self


class TransferLink(Schema):
    other_id: Id = Field(description="The matching transaction on your other account.")


class TransactionOut(Schema):
    id: int
    account_id: Id
    date: dt.date
    amount_cents: int
    description: str
    category_id: int | None
    source: TransactionSource
    kind: TransactionKind
    transfer_pair_id: int | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class TransactionPage(Schema):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int
