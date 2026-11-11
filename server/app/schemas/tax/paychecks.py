import datetime as dt
from typing import Annotated

from pydantic import Field, StringConstraints

from app.models import PaycheckLineKind
from app.money import MAX_ABS_CENTS
from app.schemas.common import Id, Notes, Schema, UpdateSchema

# Every paycheck amount is whole cents and never negative.
PayCents = Annotated[int, Field(strict=True, ge=0, lt=MAX_ABS_CENTS)]
MAX_LINES = 20
Employer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PaycheckFields(Schema):
    """The amounts on a pay stub. Gross minus every other line must equal ``net_cents``."""

    gross_cents: PayCents
    # Taxes withheld
    federal_tax_cents: PayCents = 0
    state_tax_cents: PayCents = 0
    social_security_cents: PayCents = 0
    medicare_cents: PayCents = 0
    # Taken out before tax
    retirement_cents: PayCents = Field(0, description="Traditional 401(k)/403(b)/457")
    hsa_cents: PayCents = 0
    health_insurance_cents: PayCents = Field(
        0, description="Health/dental/vision premiums, FSA (Section 125)"
    )
    # Taken out after tax
    roth_retirement_cents: PayCents = Field(0, description="Roth 401(k)/403(b)")
    other_deductions_cents: PayCents = Field(
        0, description="Other after-tax deductions, e.g. union dues"
    )
    net_cents: PayCents


class PaycheckLineIn(Schema):
    """One extra stub line. Whether it was taken out before tax follows from its kind."""

    kind: PaycheckLineKind
    amount_cents: PayCents


class PaycheckLineOut(PaycheckLineIn):
    id: int
    pre_tax_federal: bool
    pre_tax_fica: bool


class PaycheckExtras(Schema):
    """Optional stub details that never change the adds-up rule."""

    period_start: dt.date | None = None
    period_end: dt.date | None = None
    # "Year to date" figures printed on the stub (must be at least this check's own amount).
    ytd_gross_cents: PayCents | None = None
    ytd_federal_tax_cents: PayCents | None = None
    ytd_social_security_cents: PayCents | None = None
    ytd_medicare_cents: PayCents | None = None


class PaycheckCreate(PaycheckFields, PaycheckExtras):
    lines: list[PaycheckLineIn] = Field(default_factory=list, max_length=MAX_LINES)
    pay_date: dt.date
    employer: Employer
    account_id: Id | None = None
    notes: Notes = None
    # The deposit of its net pay, linked straight away (same checks as linking it later).
    deposit_transaction_id: Id | None = None


class PaycheckUpdate(UpdateSchema, PaycheckExtras):
    not_null = (
        "pay_date",
        "employer",
        "lines",
        *(name for name in PaycheckFields.model_fields),
    )

    pay_date: dt.date | None = None
    employer: Employer | None = None
    account_id: Id | None = None
    notes: Notes = None
    gross_cents: PayCents | None = None
    federal_tax_cents: PayCents | None = None
    state_tax_cents: PayCents | None = None
    social_security_cents: PayCents | None = None
    medicare_cents: PayCents | None = None
    retirement_cents: PayCents | None = None
    hsa_cents: PayCents | None = None
    health_insurance_cents: PayCents | None = None
    roth_retirement_cents: PayCents | None = None
    other_deductions_cents: PayCents | None = None
    net_cents: PayCents | None = None
    # Sending lines replaces all of them; leave it out to keep the current ones.
    lines: list[PaycheckLineIn] | None = Field(None, max_length=MAX_LINES)


class DepositLink(Schema):
    transaction_id: Id = Field(description="The deposit of this paycheck's net pay.")


class PaycheckOut(PaycheckFields, PaycheckExtras):
    id: int
    lines: list[PaycheckLineOut]
    pay_date: dt.date
    employer: str
    account_id: int | None
    deposit_transaction_id: int | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class PaycheckPage(Schema):
    items: list[PaycheckOut]
    total: int
    limit: int
    offset: int


class PayDeposit(Schema):
    """Money in that looks like pay and isn't linked to a paycheck yet: a paycheck to fill in."""

    transaction_id: int
    date: dt.date
    description: str
    amount_cents: int  # the take-home (net) pay
    account_id: int
    employer: str  # a guess from the description, to start the form with


class SocialSecurityCheck(Schema):
    wage_base_cents: int
    rate: str  # exact decimal as text, e.g. "0.062"
    max_tax_cents: int
    withheld_cents: int
    over_max_cents: int
    message: str


class PaycheckSummary(Schema):
    """Year-to-date totals. Estimates for your own records, not tax advice."""

    year: int
    paycheck_count: int
    totals: dict[str, int]  # field name -> cents, for every amount on the pay stub
    taxes_withheld_cents: int
    pre_tax_deductions_cents: int
    after_tax_deductions_cents: int
    social_security_by_employer: dict[str, int]
    social_security_check: SocialSecurityCheck | None
    message: str | None = None
    # Extra-line totals already inside gross (qualified_tips, qualified_overtime): never add them
    # to gross or take-home.
    line_totals: dict[str, int] = {}
