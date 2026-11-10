"""Commit helper shared by services that guard a unique name."""

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def commit_or(session: Session, make_error: Callable[[], Exception]) -> None:
    """Commit; if a unique rule was broken (two requests at once), roll back and raise the error."""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise make_error() from None
