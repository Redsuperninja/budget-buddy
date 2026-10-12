"""Retirement and HSA contributions against the year's limits (services/investing/retirement.py)."""

import datetime as dt

from app.schemas.common import Schema


class LimitOut(Schema):
    name: str
    contributed_cents: int
    limit_cents: int
    left_cents: int  # room left under the limit (0 when at or over)
    over_cents: int  # how much is over the limit (0 when under)
    catch_up_cents: list[int]  # extra allowed by age; not added (age isn't known)
    catch_up_ages: list[str]  # who may add each one, like "age 50 or older"

    note: str


class RetirementOut(Schema):
    tax_year: int
    is_estimate: bool
    note: str
    limits: list[LimitOut]
    tax_data_last_reviewed: dt.date
