"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import ApiError
from app.network import is_loopback_address

SessionDep = Annotated[Session, Depends(get_session)]


def loopback_only(request: Request) -> None:
    """Dashboard/admin routes answer this computer only (sync contract §3.1).

    Uses the socket peer address only. Proxy headers such as ``X-Forwarded-For`` are never trusted.
    """
    # TODO(#4): add the Host allowlist, Origin check and CSRF token before the dashboard ships
    # (roadmap #16). The loopback check alone does not stop DNS rebinding from a browser page.
    client = request.client
    if not is_loopback_address(client.host if client else None):
        raise ApiError(
            403,
            "not_this_computer",
            "This only works on the computer where Budget Buddy is running.",
        )


LOCAL_ONLY = [Depends(loopback_only)]
