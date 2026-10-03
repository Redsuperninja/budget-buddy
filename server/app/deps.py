"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import get_session

# Who may call which route (this computer only, except the phone's routes) is enforced for
# every route by ``app.network.LocalAccessMiddleware``, not per router.
SessionDep = Annotated[Session, Depends(get_session)]
