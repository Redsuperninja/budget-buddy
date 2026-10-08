"""Auto-categorization rules: "a description containing this text goes in this category"."""

import datetime as dt
from typing import Annotated

from pydantic import StringConstraints

from app.schemas.common import Id, Schema, UpdateSchema

Pattern = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


class RuleCreate(Schema):
    pattern: Pattern
    category_id: Id


class RuleUpdate(UpdateSchema):
    not_null = ("pattern", "category_id")

    pattern: Pattern | None = None
    category_id: Id | None = None


class RuleOut(Schema):
    id: int
    pattern: str
    category_id: int
    created_at: dt.datetime
    updated_at: dt.datetime


class ApplyResult(Schema):
    # How many transactions that had no category now have one.
    categorized: int
