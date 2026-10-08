from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep, parse_month
from app.schemas.summary import MonthlySummary, MonthlyTrend
from app.services import summary as service
from app.services.trend import monthly_trend

router = APIRouter(prefix="/api/local/summary", tags=["summary"])


@router.get("/monthly")
def monthly_summary(session: SessionDep, month: str = "") -> MonthlySummary:
    return service.monthly_summary(session, *parse_month(month))


@router.get("/trend")
def trend(
    session: SessionDep,
    end: str = "",
    months: Annotated[int, Query(ge=1, le=24)] = 12,
) -> MonthlyTrend:
    """Money in, spending and saving for ``months`` months up to and including ``end``."""
    return monthly_trend(session, *parse_month(end), months)
