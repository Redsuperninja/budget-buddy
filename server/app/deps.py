"""Shared FastAPI dependencies and request helpers."""

import re
from typing import Annotated

from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import ApiError
from app.schemas.common import MAX_ID

# Who may call which route (this computer only, except the phone's routes) is enforced for
# every route by ``app.network.LocalAccessMiddleware``, not per router.
SessionDep = Annotated[Session, Depends(get_session)]

# IDs and offsets in the URL are bounded so a huge number gets a 422, not a database crash.
PathId = Annotated[int, Path(ge=1, le=MAX_ID)]
QueryId = Annotated[int | None, Query(ge=1, le=MAX_ID)]
Offset = Annotated[int, Query(ge=0, le=MAX_ID)]

# Years 1900 through 9998 (9999-12 would need a month after the last one Python can hold).
MONTH_PATTERN = re.compile(
    r"(19[0-9]{2}|[2-8][0-9]{3}|9[0-8][0-9]{2}|99[0-8][0-9]|999[0-8])-(0[1-9]|1[0-2])"
)


def parse_month(text: str) -> tuple[int, int]:
    """``"2026-01"`` -> ``(2026, 1)``, or a plain-English 422."""
    match = MONTH_PATTERN.fullmatch(text)
    if not match:
        raise ApiError(422, "validation_error", "Enter the month as year-month, like 2026-01.")
    return int(match[1]), int(match[2])
