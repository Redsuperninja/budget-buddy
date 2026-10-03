import datetime as dt
from typing import Annotated

from pydantic import Field

from app.models import AccountKind
from app.schemas.common import Name, Notes, OptionalShortText, Schema, UpdateSchema

# Plain strings here; encryption at rest (roadmap #4) happens below the API.
Last4 = Annotated[str | None, Field(pattern=r"^[0-9]{4}$")]


class AccountCreate(Schema):
    name: Name
    kind: AccountKind
    institution: OptionalShortText = None
    last4: Last4 = None
    notes: Notes = None


class AccountUpdate(UpdateSchema):
    not_null = ("name", "kind")

    name: Name | None = None
    kind: AccountKind | None = None
    institution: OptionalShortText = None
    last4: Last4 = None
    notes: Notes = None


class AccountOut(Schema):
    id: int
    name: str
    kind: AccountKind
    institution: str | None
    last4: str | None
    notes: str | None
    # Sum of all the account's transactions. There's no opening-balance field: record a
    # starting balance as an "adjustment" transaction. Adjustments (including opening balances)
    # change balances but are never counted as income or spending.
    # For credit_card and loan accounts a negative balance means money owed. Charges are
    # negative, and payments and refunds are positive.
    balance_cents: int
    transaction_count: int
    created_at: dt.datetime
    updated_at: dt.datetime
