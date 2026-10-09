"""Live prices from Finnhub (services/price_feed.py, ADR-0010)."""

from typing import Annotated

from pydantic import StringConstraints

from app.schemas.common import Schema

ApiKey = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100, pattern=r"^[A-Za-z0-9_-]*$")
]


class PriceFeedIn(Schema):
    enabled: bool
    # A new key; "" removes the saved one; leave it out to keep it.
    api_key: ApiKey | None = None


class PriceFeedOut(Schema):
    enabled: bool
    has_key: bool  # the key itself is never sent back


class RefreshResult(Schema):
    updated: list[str]  # symbols with a new price
    not_found: list[str]  # symbols Finnhub didn't know (some mutual funds, for example)
    message: str | None  # why it stopped or didn't run, in plain English
