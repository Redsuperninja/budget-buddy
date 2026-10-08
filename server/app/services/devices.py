"""Paired phones: look up by token, list, and remove (sync contract §3.10)."""

import datetime as dt
import hmac

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode
from app.crypto.hashing import hash_secret
from app.errors import ApiError, not_found
from app.models import Device, SeenNonce


def hash_token(token: str) -> str:
    """``sha256`` of the token's ASCII text, lowercase hex. Only this is ever stored."""
    return hash_secret(token)


def authenticate_token(session: Session, token: object) -> Device:
    """The device a bearer token belongs to, or an error the phone understands.

    Used by the sync routes (roadmap #15). A removed phone is refused immediately because the
    check reads the database every time.
    """
    try:
        b64u_decode(token, 32)
    except ValueError:
        raise ApiError(400, "bad_request", "Something went wrong. Try again in a minute.") from None
    wanted = hash_token(str(token))
    device = session.scalar(select(Device).where(Device.token_hash == wanted))
    if device is None or not hmac.compare_digest(device.token_hash, wanted):
        raise ApiError(
            401,
            "not_paired",
            "This phone isn't connected to your computer anymore. Please pair again.",
        )
    if device.revoked:
        raise revoked_error()
    return device


def active_clauses(device_id: int) -> tuple:
    """SQL conditions for "this phone is still paired and still has its sync key"."""
    return (Device.id == device_id, Device.revoked_at.is_(None), Device.sync_key.is_not(None))


def ensure_active(session: Session, device_id: int) -> None:
    """Raise the plaintext ``device_revoked`` error if the phone was removed a moment ago."""
    if session.scalar(select(Device.id).where(*active_clauses(device_id))) is None:
        raise revoked_error()


def revoked_error() -> ApiError:
    return ApiError(
        401,
        "device_revoked",
        "This phone was removed from Budget Buddy on your computer. Pair again to keep syncing.",
    )


def list_devices(session: Session) -> list[Device]:
    return list(session.scalars(select(Device).order_by(Device.paired_at.desc(), Device.id.desc())))


def revoke_device(session: Session, device_id: int) -> Device:
    """Remove a phone: mark it revoked and delete its sync key. The row stays for history.

    Its remembered request nonces are deleted too (§3.10). Safe to repeat.
    """
    device = session.get(Device, device_id)
    if device is None:
        raise not_found("phone")
    if not device.revoked:
        device.revoked = True
        device.revoked_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    device.sync_key = None
    session.execute(delete(SeenNonce).where(SeenNonce.device_id == device_id))
    session.commit()
    return device
