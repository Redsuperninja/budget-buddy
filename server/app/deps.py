"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.common import MAX_ID

# Who may call which route (this computer only, except the phone's routes) is enforced for
# every route by ``app.network.LocalAccessMiddleware``, not per router.
SessionDep = Annotated[Session, Depends(get_session)]

# IDs and offsets in the URL are bounded so a huge number gets a 422, not a database crash.
PathId = Annotated[int, Path(ge=1, le=MAX_ID)]
QueryId = Annotated[int | None, Query(ge=1, le=MAX_ID)]
Offset = Annotated[int, Query(ge=0, le=MAX_ID)]
