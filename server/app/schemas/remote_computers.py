import datetime as dt
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.common import Schema

ComputerName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    Field(description='A name to recognize this computer by, like "Kitchen laptop".'),
]


class JoinCode(Schema):
    """A one-time code another computer types to join. Secret: never log it."""

    code: str
    address: str  # what to open on the other computer, like http://192.168.1.20:8765/
    expires_at: int
    seconds_valid: int
    # False when Budget Buddy can't be reached from the home network yet, with why.
    can_connect: bool
    message: str | None


class JoinRequest(Schema):
    code: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    name: ComputerName


class Joined(Schema):
    name: str


class ComputerOut(Schema):
    id: int
    name: str
    paired_at: dt.datetime
    last_seen_at: dt.datetime | None
