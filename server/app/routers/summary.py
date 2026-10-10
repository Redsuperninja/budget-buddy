import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep, parse_month
from app.errors import ApiError
from app.schemas.summary import MonthlySummary, MonthlyTrend, SpendingPace
from app.services import summary as service
from app.services.spending_pace import spending_pace
from app.services.trend import monthly_trend

router = APIRouter(prefix="/api/local/summary", tags=["summary"])


@router.get("/monthly")
def monthly_summary(
    session: SessionDep, month: str = "", through: dt.date | None = None
) -> MonthlySummary:
    """The month's totals; with ``through`` (a day in that month), only up to and including it."""
    year, number = parse_month(month)
    if through is not None and (through.year, through.month) != (year, number):
        raise ApiError(422, "validation_error", "Pick a day in the same month.")
    return service.monthly_summary(session, year, number, through=through)


@router.get("/trend")
def trend(
    session: SessionDep,
    end: str = "",
    months: Annotated[int, Query(ge=1, le=24)] = 12,
) -> MonthlyTrend:
    """Money in, spending and saving for ``months`` months up to and including ``end``."""
    return monthly_trend(session, *parse_month(end), months)


@router.get("/pace")
def pace(session: SessionDep, month: str = "") -> SpendingPace:
    """Spending from the 1st through each day of ``month`` (up to today), and its budget."""
    return spending_pace(session, *parse_month(month))
