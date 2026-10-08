"""Other computers on the home network (ADR-0009): one-time join codes, cookie tokens, removing.

A join code lives only in memory (as a SHA-256) for 10 minutes, works once, and five wrong tries
end it. A joined computer holds a random token in a cookie; only its SHA-256 is stored.
"""

import datetime as dt
import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import RemoteComputer

CODE_TTL_SECONDS = 600
MAX_WRONG_TRIES = 5
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I look-alikes
CODE_LENGTH = 8
COOKIE_NAME = "bb_computer"
COOKIE_MAX_AGE = 400 * 24 * 3600  # about a year; browsers cap cookies at 400 days
LAST_SEEN_EVERY = dt.timedelta(minutes=5)

NO_CODE = (
    "That code has run out or was already used. On the Budget Buddy computer, open Devices, then "
    "Other computers, and click Allow another computer for a new one."
)
WRONG_CODE = "That code isn't right. Check it on the Budget Buddy computer and try again."


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def normalize_code(text: str) -> str:
    """What people type: any case, with spaces or a dash ("abcd-efgh")."""
    return "".join(ch for ch in text.upper() if ch.isalnum())


@dataclass
class _Invite:
    code_hash: str
    expires_at: int
    wrong_tries: int = 0


class JoinCodes:
    """The one live join code, if any. Kept in memory: restarting Budget Buddy cancels it."""

    def __init__(self) -> None:
        self._invite: _Invite | None = None
        self._lock = threading.Lock()

    def new(self, now: int) -> tuple[str, int]:
        """Make a new code (cancelling any old one). Returns it and when it runs out."""
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        with self._lock:
            self._invite = _Invite(_hash(code), now + CODE_TTL_SECONDS)
        return code, now + CODE_TTL_SECONDS

    def live(self, now: int) -> bool:
        with self._lock:
            return self._invite is not None and now < self._invite.expires_at

    def use(self, typed: str, now: int) -> None:
        """Spend the code, or raise. Five wrong tries end it."""
        with self._lock:
            invite = self._invite
            if invite is None or now >= invite.expires_at:
                self._invite = None
                raise ApiError(409, "no_join_code", NO_CODE)
            if not hmac.compare_digest(_hash(normalize_code(typed)), invite.code_hash):
                invite.wrong_tries += 1
                if invite.wrong_tries >= MAX_WRONG_TRIES:
                    self._invite = None
                raise ApiError(403, "wrong_code", WRONG_CODE)
            self._invite = None


def join(session: Session, codes: JoinCodes, typed: str, name: str, now: int) -> str:
    """Spend the code and remember this computer. Returns its new token (for the cookie only)."""
    codes.use(typed, now)
    token = secrets.token_urlsafe(32)
    session.add(RemoteComputer(name=name, token_hash=_hash(token)))
    session.commit()
    return token


def authenticate(session: Session, token: str | None) -> bool:
    """True if ``token`` belongs to a computer still allowed in (and notes it was seen)."""
    if not token or len(token) > 100:
        return False
    computer = session.scalar(
        select(RemoteComputer).where(RemoteComputer.token_hash == _hash(token))
    )
    if computer is None:
        return False
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    if computer.last_seen_at is None or now - computer.last_seen_at > LAST_SEEN_EVERY:
        computer.last_seen_at = now
        session.commit()
    return True


def list_computers(session: Session) -> list[RemoteComputer]:
    """Joined computers that haven't been removed, newest first."""
    query = select(RemoteComputer).where(RemoteComputer.token_hash.is_not(None))
    return list(session.scalars(query.order_by(RemoteComputer.id.desc())))


def remove(session: Session, computer_id: int) -> None:
    computer = session.get(RemoteComputer, computer_id)
    if computer is None or computer.token_hash is None:
        raise not_found("computer")
    computer.token_hash = None
    computer.revoked_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    session.commit()


def network_wanted(session: Session, codes: JoinCodes, now: int) -> bool:
    """Should the home-network listener stay open for other computers?"""
    joined = session.scalar(
        select(func.count())
        .select_from(RemoteComputer)
        .where(RemoteComputer.token_hash.is_not(None))
    )
    return codes.live(now) or bool(joined)
