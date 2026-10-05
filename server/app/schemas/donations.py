import datetime as dt
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from app.models import DonationKind
from app.schemas.common import (
    Cents,
    DollarText,
    Id,
    Notes,
    Schema,
    UpdateSchema,
    resolve_amount,
)

Organization = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    Field(description="The charity's name."),
]

_AMOUNT_HELP = (
    "For cash, what you gave. For goods, what the items were worth when you gave them (fair "
    "market value). If you got something back, like a dinner, enter only the part above its value."
)


_DATE_HELP = (
    "Use the date you paid: the day you mailed a check or the day the card was charged, even if "
    "the card is paid off later."
)
# A phone a time zone ahead of the Home Base may already be on tomorrow's date.
_FUTURE_GRACE = dt.timedelta(days=1)


def _today() -> dt.date:
    """The Home Base's local date. A function so tests can freeze the clock."""
    return dt.date.today()


def _not_future(date: dt.date | None) -> dt.date | None:
    if date is not None and date > _today() + _FUTURE_GRACE:
        raise ValueError(
            "Enter a gift on the day you actually gave it. A pledge counts once you pay it."
        )
    return date


GiftDate = Annotated[dt.date, Field(description=_DATE_HELP), AfterValidator(_not_future)]


def _positive(cents: int) -> int:
    if cents <= 0:
        raise ValueError(
            "A donation amount must be more than zero. If a gift was refunded or returned, "
            "edit or delete it instead."
        )
    return cents


class DonationCreate(Schema):
    """Send ``amount_cents`` or ``amount`` (dollars as text), not both."""

    date: GiftDate
    organization: Organization
    kind: DonationKind
    amount_cents: Cents | None = Field(default=None, description=_AMOUNT_HELP)
    amount: DollarText | None = None
    receipt_id: Id | None = None
    notes: Notes = None

    @model_validator(mode="after")
    def _amount(self):
        cents = resolve_amount(self.amount_cents, self.amount)
        if cents is None:
            raise ValueError("An amount is required: send amount_cents or amount.")
        self.amount_cents = _positive(cents)
        self.amount = None
        return self


class DonationUpdate(UpdateSchema):
    not_null = ("date", "organization", "kind", "amount_cents")

    date: GiftDate | None = None
    organization: Organization | None = None
    kind: DonationKind | None = None
    amount_cents: Cents | None = Field(default=None, description=_AMOUNT_HELP)
    amount: DollarText | None = None
    receipt_id: Id | None = None
    notes: Notes = None

    @model_validator(mode="after")
    def _amount(self):
        if self.amount is not None:
            self.amount_cents = _positive(resolve_amount(self.amount_cents, self.amount))
            self.amount = None
            self.model_fields_set.discard("amount")
            self.model_fields_set.add("amount_cents")
        elif self.amount_cents is not None:
            _positive(self.amount_cents)
        return self


class DonationOut(Schema):
    id: int
    date: dt.date
    tax_year: int
    organization: str
    kind: DonationKind
    amount_cents: int
    receipt_id: int | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class DonationPage(Schema):
    items: list[DonationOut]
    total: int
    limit: int
    offset: int


class ProofItem(Schema):
    """One piece of paperwork to keep or file. ``code`` is stable; ``message`` is for people."""

    code: str
    message: str


class DonationProof(Schema):
    donation_id: int
    date: dt.date
    organization: str
    kind: DonationKind
    amount_cents: int
    has_receipt: bool
    proof_needed: list[ProofItem]


class ProofThresholds(Schema):
    """The paperwork thresholds used, straight from that year's tax data file."""

    written_acknowledgment_cents: int
    form_8283_noncash_cents: int
    qualified_appraisal_cents: int


class DonationSummary(Schema):
    tax_year: int
    is_estimate: bool
    disclaimer: str
    donation_count: int
    cash_total_cents: int
    goods_total_cents: int
    total_cents: int
    # Paperwork that depends on the whole year (e.g. Form 8283), not on one gift.
    year_proof_needed: list[ProofItem]
    donations: list[DonationProof]
    thresholds: ProofThresholds
    tax_data_last_reviewed: dt.date
