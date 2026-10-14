import datetime as dt
from typing import Annotated

from pydantic import Field, model_validator

from app.models import AccountKind, RetirementType
from app.schemas.common import (
    Cents,
    DollarText,
    Name,
    Notes,
    OptionalShortText,
    Schema,
    UpdateSchema,
    pick_cents,
)

# Plain strings here; encryption at rest (roadmap #4) happens below the API.
Last4 = Annotated[str | None, Field(pattern=r"^[0-9]{4}$")]


RETIREMENT_ONLY = "Only a retirement account has a retirement type (like Roth IRA or 401(k))."


class AccountCreate(Schema):
    name: Name
    kind: AccountKind
    retirement_type: RetirementType | None = None  # retirement accounts only
    institution: OptionalShortText = None
    last4: Last4 = None
    notes: Notes = None

    @model_validator(mode="after")
    def _retirement_type(self):
        if self.retirement_type is not None and self.kind != AccountKind.RETIREMENT:
            raise ValueError(RETIREMENT_ONLY)
        return self


class AccountUpdate(UpdateSchema):
    not_null = ("name", "kind")

    name: Name | None = None
    kind: AccountKind | None = None
    retirement_type: RetirementType | None = None
    institution: OptionalShortText = None
    last4: Last4 = None
    notes: Notes = None


class AccountOut(Schema):
    id: int
    name: str
    kind: AccountKind
    retirement_type: RetirementType | None
    institution: str | None
    last4: str | None
    notes: str | None
    # Sum of all the account's transactions. There's no opening-balance field: record a
    # starting balance as an "adjustment" transaction. Adjustments (including opening balances)
    # change balances but are never counted as income or spending.
    # For credit_card and loan accounts a negative balance means money owed. Charges are
    # negative, and payments and refunds are positive.
    balance_cents: int
    # The same, counting only transactions dated today or earlier: what the bank shows now.
    current_balance_cents: int
    transaction_count: int
    created_at: dt.datetime
    updated_at: dt.datetime


class BalanceSet(Schema):
    """What the bank says the balance was at the end of ``date``. Send ``balance_cents`` or
    ``balance`` (dollar text), not both. For a credit card or loan, what you owe is negative."""

    date: dt.date
    balance_cents: Cents | None = None
    balance: DollarText | None = None

    @model_validator(mode="after")
    def _balance(self):
        cents = pick_cents(self.balance_cents, self.balance, "balance")
        if cents is None:
            raise ValueError("Enter the balance: send balance_cents or balance.")
        if self.date > dt.date.today() + dt.timedelta(days=1):
            raise ValueError(
                "Use today or an earlier day: Budget Buddy can't know a future balance."
            )
        self.balance_cents, self.balance = cents, None
        return self


class BalanceSetResult(Schema):
    date: dt.date
    balance_cents: int
    # The balance adjustment added on that day to make it match (0: it already did, none added).
    adjustment_cents: int
    transaction_id: int | None
    # The balance at the end of today after this, which a change to an older day also moves.
    balance_now_cents: int
