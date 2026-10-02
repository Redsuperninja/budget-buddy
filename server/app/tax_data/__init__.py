"""US federal tax-year reference data (limits, thresholds, brackets), one JSON file per year.

Every tax-year-specific number the app uses lives in ``<year>.json`` next to this file, with a
source for each section. Logic should call :func:`load_tax_year` instead of hard-coding numbers.

Conventions:
- Money is integer cents (fields ending in ``_cents``).
- Rates are exact decimals (e.g. ``0.22``), parsed as :class:`~decimal.Decimal`, never floats.
- ``null`` means "does not apply this year" or "could not be verified";
  the section ``note`` says which.

These figures support estimates only. They are not tax advice.
"""

import json
from datetime import date
from decimal import Decimal
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

__all__ = [
    "FILING_STATUSES",
    "TaxYearData",
    "UnsupportedTaxYearError",
    "load_tax_year",
    "supported_tax_years",
]

FILING_STATUSES = (
    "single",
    "married_filing_jointly",
    "married_filing_separately",
    "head_of_household",
)

Cents = Annotated[StrictInt, Field(ge=0)]
Rate = Annotated[Decimal, Field(ge=0, le=1)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(_Model):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")


class _Section(_Model):
    """A group of figures and the sources that back them."""

    source_ids: list[str] = Field(min_length=1)
    note: str | None = None


class ByFilingStatus(_Model):
    single: Cents
    married_filing_jointly: Cents
    married_filing_separately: Cents
    head_of_household: Cents

    def for_status(self, filing_status: str) -> int:
        if filing_status not in FILING_STATUSES:
            raise ValueError(f"Unknown filing status: {filing_status!r}")
        return getattr(self, filing_status)


class Bracket(_Model):
    rate: Rate
    up_to_cents: Cents | None  # None = no upper limit (top bracket)


def _check_brackets(name: str, brackets: list[Bracket]) -> None:
    if not brackets:
        raise ValueError(f"{name}: no brackets")
    if brackets[-1].up_to_cents is not None:
        raise ValueError(f"{name}: the top bracket must have up_to_cents = null")
    limits = [b.up_to_cents for b in brackets[:-1]]
    if any(limit is None for limit in limits):
        raise ValueError(f"{name}: only the top bracket may have up_to_cents = null")
    if any(a >= b for a, b in zip(limits, limits[1:], strict=False)):
        raise ValueError(f"{name}: bracket limits must be strictly ascending")
    rates = [b.rate for b in brackets]
    if any(a >= b for a, b in zip(rates, rates[1:], strict=False)):
        raise ValueError(f"{name}: bracket rates must be strictly ascending")


class BracketTable(_Section):
    by_filing_status: dict[str, list[Bracket]]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if set(self.by_filing_status) != set(FILING_STATUSES):
            raise ValueError(
                f"brackets must cover exactly these filing statuses: {FILING_STATUSES}"
            )
        for status, brackets in self.by_filing_status.items():
            _check_brackets(status, brackets)
        return self


class AgeOrBlindAddition(_Model):
    married: Cents
    unmarried: Cents


class StandardDeduction(_Section):
    basic_cents: ByFilingStatus
    additional_age_65_or_blind_cents: AgeOrBlindAddition


class SeniorDeduction(_Section):
    per_person_cents: Cents
    magi_phaseout_start_joint_cents: Cents
    magi_phaseout_start_other_cents: Cents
    phaseout_rate: Rate | None


class NetInvestmentIncomeTax(_Section):
    rate: Rate
    magi_threshold_cents: ByFilingStatus


class CapitalLossDeductionLimit(_Section):
    limit_cents: Cents
    married_filing_separately_limit_cents: Cents


class CharitableAgiLimits(_Model):
    cash_to_50_percent_orgs: Rate
    cash_to_other_orgs: Rate
    capital_gain_property_to_50_percent_orgs: Rate
    capital_gain_property_to_other_orgs: Rate


class Charitable(_Section):
    agi_limits: CharitableAgiLimits
    written_acknowledgment_threshold_cents: Cents
    form_8283_noncash_threshold_cents: Cents
    qualified_appraisal_threshold_cents: Cents
    non_itemizer_deduction_cents: ByFilingStatus | None
    itemized_agi_floor_rate: Rate | None


class Hsa(_Section):
    self_only_cents: Cents
    family_cents: Cents
    catch_up_55_plus_cents: Cents


class Retirement(_Section):
    elective_deferral_401k_cents: Cents
    catch_up_50_plus_cents: Cents
    catch_up_age_60_to_63_cents: Cents
    ira_cents: Cents
    ira_catch_up_50_plus_cents: Cents


class SaltCap(_Section):
    cap_cents: Cents
    married_filing_separately_cap_cents: Cents
    magi_phaseout_start_cents: Cents
    married_filing_separately_magi_phaseout_start_cents: Cents
    phaseout_rate: Rate
    floor_cents: Cents
    married_filing_separately_floor_cents: Cents


class StudentLoanInterest(_Section):
    max_deduction_cents: Cents
    magi_phaseout_start_joint_cents: Cents
    magi_phaseout_end_joint_cents: Cents
    magi_phaseout_start_other_cents: Cents
    magi_phaseout_end_other_cents: Cents


class MedicalExpense(_Section):
    agi_floor_rate: Rate


class Fica(_Section):
    social_security_rate: Rate
    social_security_wage_base_cents: Cents
    medicare_rate: Rate
    additional_medicare_rate: Rate
    additional_medicare_threshold_cents: ByFilingStatus


class TaxYearData(_Model):
    """All reference figures for one US federal tax year."""

    schema_version: StrictInt = Field(ge=1, le=1)
    tax_year: StrictInt = Field(ge=2000, le=2100)
    last_reviewed: date
    sources: list[Source] = Field(min_length=1)

    standard_deduction: StandardDeduction
    senior_deduction: SeniorDeduction
    ordinary_brackets: BracketTable
    capital_gains_brackets: BracketTable
    net_investment_income_tax: NetInvestmentIncomeTax
    capital_loss_deduction_limit: CapitalLossDeductionLimit
    charitable: Charitable
    hsa: Hsa
    retirement: Retirement
    salt_cap: SaltCap
    student_loan_interest: StudentLoanInterest
    medical_expense: MedicalExpense
    fica: Fica

    def sections(self) -> dict[str, _Section]:
        return {name: value for name, value in self if isinstance(value, _Section)}

    @model_validator(mode="after")
    def _validate_sources(self) -> Self:
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        known = set(ids)
        for name, section in self.sections().items():
            missing = set(section.source_ids) - known
            if missing:
                raise ValueError(f"{name} references unknown source ids: {sorted(missing)}")
        return self


class UnsupportedTaxYearError(ValueError):
    """Raised when there is no reference data file for the requested tax year."""

    def __init__(self, year: int, supported: tuple[int, ...]) -> None:
        years = ", ".join(str(y) for y in supported) or "none"
        super().__init__(f"No tax data for {year}. Supported tax years: {years}.")
        self.year = year
        self.supported = supported


def _data_files() -> dict[int, Traversable]:
    files = {}
    for entry in resources.files(__name__).iterdir():
        stem, _, ext = entry.name.partition(".")
        if ext == "json" and stem.isdigit():
            files[int(stem)] = entry
    return files


def supported_tax_years() -> tuple[int, ...]:
    """Tax years that have a reference data file, oldest first."""
    return tuple(sorted(_data_files()))


@cache
def load_tax_year(year: int) -> TaxYearData:
    """Load and validate the reference data for ``year``.

    Raises :class:`UnsupportedTaxYearError` if there is no file for that year.
    """
    files = _data_files()
    if year not in files:
        raise UnsupportedTaxYearError(year, supported_tax_years())
    raw = json.loads(files[year].read_text(encoding="utf-8"), parse_float=Decimal)
    data = TaxYearData.model_validate(raw)
    if data.tax_year != year:
        raise ValueError(f"{year}.json says tax_year {data.tax_year}")
    return data
