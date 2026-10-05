import re

from fastapi import APIRouter

from app.deps import SessionDep
from app.errors import ApiError
from app.schemas.summary import MonthlySummary
from app.services import summary as service

router = APIRouter(prefix="/api/local/summary", tags=["summary"])

# Years 1900 through 9998 (9999-12 would need a month after the last one Python can hold).
MONTH_PATTERN = re.compile(
    r"(19[0-9]{2}|[2-8][0-9]{3}|9[0-8][0-9]{2}|99[0-8][0-9]|999[0-8])-(0[1-9]|1[0-2])"
)


@router.get("/monthly")
def monthly_summary(session: SessionDep, month: str = "") -> MonthlySummary:
    match = MONTH_PATTERN.fullmatch(month)
    if not match:
        raise ApiError(422, "validation_error", "Enter the month as year-month, like 2026-01.")
    return service.monthly_summary(session, int(match[1]), int(match[2]))
