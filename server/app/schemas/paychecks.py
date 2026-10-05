import datetime as dt
from typing import Annotated

from pydantic import Field, StringConstraints

from app.money import MAX_ABS_CENTS
from app.schemas.common import Id, Notes, Schema, UpdateSchema

# Every paycheck amount is whole cents and never negative.
PayCents = Annotated[int, Field(strict=True, ge=0, lt=MAX_ABS_CENTS)]
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


class PaycheckCreate(PaycheckFields):
    pay_date: dt.date
    employer: Employer
    account_id: Id | None = None
    notes: Notes = None


class PaycheckUpdate(UpdateSchema):
    not_null = (
        "pay_date",
        "employer",
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


class DepositLink(Schema):
    transaction_id: Id = Field(description="The deposit of this paycheck's net pay.")


class PaycheckOut(PaycheckFields):
    id: int
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
