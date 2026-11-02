"""Tax preferences (roadmap 25j): the filing status that narrows the yearly tax summary."""

from typing import Literal

from app.schemas.common import Schema
from app.tax_data import FILING_STATUSES

# One of the statuses the tax-year data files cover (app/tax_data), or None for "Not set: show all".
FilingStatus = Literal[FILING_STATUSES]  # type: ignore[valid-type]


class TaxPreferences(Schema):
    """Both what GET returns and what PUT takes: send ``null`` to go back to showing all."""

    filing_status: FilingStatus | None = None
