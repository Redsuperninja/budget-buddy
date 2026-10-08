"""Field types shared by the schemas. Money is always whole cents (``int``)."""

from typing import Annotated, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.money import MAX_ABS_CENTS, dollars_to_cents

# Strict: a JSON float like 12.5 (or the string "1250") is rejected instead of silently converted.
Cents = Annotated[int, Field(strict=True, gt=-MAX_ABS_CENTS, lt=MAX_ABS_CENTS)]
# SQLite stores integers in 64 bits; a bigger ID can't exist and would crash the query.
MAX_ID = 2**63 - 1
Id = Annotated[int, Field(ge=1, le=MAX_ID)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OptionalShortText = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)]
Notes = Annotated[str | None, Field(max_length=10_000)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class UpdateSchema(Schema):
    """PATCH body: only the fields sent are changed. Fields in ``not_null`` can't be cleared."""

    not_null: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_cleared_required_fields(self):
        for field in self.not_null:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be empty.")
        return self

    def changes(self) -> dict:
        return self.model_dump(exclude_unset=True)


def parse_dollars(text: str) -> int:
    """``dollars_to_cents`` with plain-English errors that don't echo the input back."""
    try:
        return dollars_to_cents(text)
    except ValueError as exc:
        reason = str(exc).split(": ", 1)[0]
        if reason.startswith("Not a dollar amount"):
            reason = "Enter a dollar amount like 12.34 or -5.00, without a $ sign or commas"
        raise ValueError(reason + ".") from None


def _check_dollars(text: str) -> str:
    parse_dollars(text)  # so a bad amount is reported against the "amount" field
    return text


# A dollar amount as text ("12.34", "-5"), for callers that don't want to do the cents math.
DollarText = Annotated[str, Field(strict=True, max_length=40), AfterValidator(_check_dollars)]


def pick_cents(cents: int | None, dollars: str | None, what: str = "amount") -> int | None:
    """Take the amount from ``<what>_cents`` or ``<what>`` (dollars text). Not both."""
    if cents is not None and dollars is not None:
        raise ValueError(f"Send either {what}_cents or {what}, not both.")
    return parse_dollars(dollars) if dollars is not None else cents


def resolve_amount(amount_cents: int | None, amount: str | None) -> int | None:
    """Pick the amount from ``amount_cents`` or ``amount`` (dollars). Not both, never zero."""
    cents = pick_cents(amount_cents, amount)
    if cents == 0:
        raise ValueError("The amount can't be zero.")
    return cents
