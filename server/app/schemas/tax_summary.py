"""The yearly tax summary (roadmap #13): one page of totals to take to tax time."""

import datetime as dt
from typing import Literal

from app.models import DeductionKind
from app.schemas.common import Schema


class Line(Schema):
    label: str
    amount_cents: int


class DeductionTotal(Schema):
    kind: DeductionKind
    label: str
    count: int
    amount_cents: int
    where: Literal["itemized", "adjustment", "credit", "other"]
    where_text: str  # plain English: where it usually goes on a return


class TaxSummary(Schema):
    tax_year: int
    generated_on: dt.date
    disclaimer: str
    paycheck_count: int
    pay: list[Line]  # year totals from your pay stubs
    donation_count: int
    donations: list[Line]  # cash, goods, total
    stock_sale_count: int
    stocks: list[Line]  # short-term, long-term, total gain (negative = loss)
    possible_wash_sale_count: int
    deductions: list[DeductionTotal]
    # Basic standard deduction by filing status from that year's tax data, for comparison;
    # None when the year has no data file.
    standard_deduction_cents: dict[str, int] | None
