from fastapi import APIRouter

from app.deps import SessionDep, parse_month
from app.schemas.summary import MonthlySummary
from app.services import summary as service

router = APIRouter(prefix="/api/local/summary", tags=["summary"])


@router.get("/monthly")
def monthly_summary(session: SessionDep, month: str = "") -> MonthlySummary:
    return service.monthly_summary(session, *parse_month(month))
