"""The ``POST /api/pair`` handshake (sync contract v1, §2 and §3.6, steps 3 to 8 of §4.4).

Nothing here logs or returns the code, keys, or tokens except in the one response that has to
carry them. Times are Unix seconds passed in by the caller (so tests can control the clock).
"""

import hmac
import os
from dataclasses import dataclass

from nacl.public import Box, PrivateKey, PublicKey
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError
from app.models import Device, PairingNonce, PairingSession
from app.services.devices import envelope
from app.services.devices.envelope import (
    REPLAY_MESSAGE,
    SERVER_ERROR_MESSAGE,
    EncryptedError,
)
from app.services.devices.pairing_sessions import (
    active_session,
    end_session,
    hash_code,
    purge_ended_sessions,
)
from app.services.devices.phones import hash_token

MAX_WRONG_CODES = 5
PAIR_PATH = "/api/pair"

EXPIRED_MESSAGE = (
    "That pairing code has expired. Click Pair a phone on your computer to get a new one."
)


# --- POST /api/pair -----------------------------------------------------------------------


@dataclass
class PairResult:
    status: int
    envelope: dict


def require_active_session(session: Session, now: int) -> PairingSession:
    """Step 2 of §4.4: there has to be a live QR code, else plaintext 410."""
    purge_ended_sessions(session, now)
    found = active_session(session, now)
    if found is None or found.pair_sk is None:
        raise ApiError(410, "pairing_expired", EXPIRED_MESSAGE)
    return found


def pair(
    session: Session,
    pairing: PairingSession,
    outer: object,
    *,
    now: int,
    server_id: str,
    server_name: str,
) -> PairResult:
    """Steps 3 to 8 of §4.4 for ``/api/pair``. Plaintext problems raise ``ApiError``."""
    parsed = envelope.parse_outer(outer, with_phone_pub=True)
    envelope.check_clock(parsed.ts, now)
    try:
        pair_sk = PrivateKey(b64u_decode(pairing.pair_sk, 32))
        shared = Box(pair_sk, PublicKey(parsed.phone_pub)).shared_key()
    except Exception:  # e.g. a weak public key: libsodium refuses to agree on a key
        raise envelope.bad_request() from None
    inner = envelope.open_request(shared, parsed, path=PAIR_PATH)

    nonce = parsed.nonce
    request_nonce = b64u_encode(nonce)
    try:
        return _pair_inside_box(
            session,
            pairing,
            inner,
            nonce,
            now=now,
            server_id=server_id,
            server_name=server_name,
            shared=shared,
            request_nonce=request_nonce,
        )
    except EncryptedError as err:
        return PairResult(err.status, envelope.seal_error(shared, request_nonce, now, err))


def _pair_inside_box(
    session: Session,
    pairing: PairingSession,
    inner: dict,
    nonce: bytes,
    *,
    now: int,
    server_id: str,
    server_name: str,
    shared: bytes,
    request_nonce: str,
) -> PairResult:
    envelope.check_contract(inner)

    # Replay check: insert first, and a duplicate means this exact request was seen before.
    session_id = pairing.id
    try:
        session.add(PairingNonce(session_id=session_id, nonce=nonce))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise EncryptedError(409, "replay", REPLAY_MESSAGE) from None

    data = inner.get("data")
    code, name, platform, app_version = _validate_data(data)

    if not hmac.compare_digest(hash_code(code), pairing.code_hash):
        _count_wrong_code(session, session_id, now)
        raise EncryptedError(410, "pairing_expired", EXPIRED_MESSAGE)

    token = b64u_encode(os.urandom(32))
    sync_key = b64u_encode(os.urandom(32))
    # One atomic claim: only one phone can ever win this QR code.
    claimed = session.execute(
        update(PairingSession)
        .where(
            PairingSession.id == session_id,
            PairingSession.used_at.is_(None),
            PairingSession.cancelled_at.is_(None),
            PairingSession.exp > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise EncryptedError(410, "pairing_expired", EXPIRED_MESSAGE)
    device = Device(
        name=name,
        token_hash=hash_token(token),
        platform=platform,
        app_version=app_version,
        sync_key=sync_key,
    )
    session.add(device)
    session.flush()
    end_session(session, session_id, now, cancel=False)  # erases pair_sk with the claim
    session.commit()
    return PairResult(
        200,
        envelope.seal(
            shared,
            request_nonce,
            now,
            200,
            data={
                "device_id": device.id,
                "token": token,
                "sync_key": sync_key,
                "server_id": server_id,
                "server_name": server_name,
            },
        ),
    )


def _validate_data(data: object) -> tuple[str, str, str, str]:
    def bad() -> EncryptedError:
        return EncryptedError(400, "bad_request", SERVER_ERROR_MESSAGE)

    if not isinstance(data, dict):
        raise bad()
    code, name = data.get("code"), data.get("device_name")
    platform, app_version = data.get("platform"), data.get("app_version")
    try:
        b64u_decode(code, 16)
    except ValueError:
        raise bad() from None
    if not isinstance(name, str) or not name.strip() or not name.isprintable():
        raise bad()
    name = name.strip()
    if len(name) > 50 or platform not in ("ios", "android"):
        raise bad()
    if not isinstance(app_version, str) or len(app_version) > 32 or not app_version.isprintable():
        raise bad()
    return code, name, platform, app_version


def _count_wrong_code(session: Session, session_id: int, now: int) -> None:
    """A right-looking but wrong code: five of these end the session (§2.3)."""
    session.execute(
        update(PairingSession)
        .where(PairingSession.id == session_id)
        .values(wrong_attempts=PairingSession.wrong_attempts + 1)
        .execution_options(synchronize_session=False)
    )
    attempts = session.scalar(
        select(PairingSession.wrong_attempts).where(PairingSession.id == session_id)
    )
    if attempts is not None and attempts >= MAX_WRONG_CODES:
        end_session(session, session_id, now, cancel=True)
    session.commit()
