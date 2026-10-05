"""Paired phones: look up by token, list, and remove (sync contract §3.10)."""

import datetime as dt
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode
from app.errors import ApiError, not_found
from app.models import Device


def hash_token(token: str) -> str:
    """``sha256`` of the token's ASCII text, lowercase hex. Only this is ever stored."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def authenticate_token(session: Session, token: object) -> Device:
    """The device a bearer token belongs to, or an error the phone understands.

    Used by the sync routes (roadmap #15). A removed phone is refused immediately because the
    check reads the database every time.
    """
    try:
        b64u_decode(token, 32)
    except ValueError:
        raise ApiError(400, "bad_request", "Something went wrong. Try again in a minute.") from None
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(str(token))))
    if device is None:
        raise ApiError(
            401,
            "not_paired",
            "This phone isn't connected to your computer anymore. Please pair again.",
        )
    if device.revoked:
        raise ApiError(
            401,
            "device_revoked",
            "This phone was removed from Budget Buddy on your computer. "
            "Pair again to keep syncing.",
        )
    return device


def list_devices(session: Session) -> list[Device]:
    return list(session.scalars(select(Device).order_by(Device.paired_at.desc(), Device.id.desc())))


def revoke_device(session: Session, device_id: int) -> Device:
    """Remove a phone: mark it revoked and delete its sync key. The row stays for history.

    Safe to repeat. (Once the sync routes keep per-device nonces, those are deleted here too.)
    """
    device = session.get(Device, device_id)
    if device is None:
        raise not_found("phone")
    if not device.revoked:
        device.revoked = True
        device.revoked_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    device.sync_key = None
    session.commit()
    return device
