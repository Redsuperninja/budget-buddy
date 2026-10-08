"""Pairing a phone (sync contract v1, §2 and §3.6).

Nothing here logs or returns the code, keys, or tokens except in the one response that has to
carry them. Times are Unix seconds passed in by the caller (so tests can control the clock).
"""

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path

from nacl.public import Box, PrivateKey, PublicKey
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto._fs import write_private_bytes
from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError
from app.models import Device, PairingNonce, PairingSession
from app.services import envelope
from app.services.devices import hash_token
from app.services.envelope import (
    CONTRACT,
    REPLAY_MESSAGE,
    SERVER_ERROR_MESSAGE,
    EncryptedError,
)

APP_ID = "budget-buddy"
CODE_TTL_SECONDS = 600
MAX_WRONG_CODES = 5
PAIR_PATH = "/api/pair"
SERVER_ID_FILENAME = "server-id"

EXPIRED_MESSAGE = (
    "That pairing code has expired. Click Pair a phone on your computer to get a new one."
)


# --- Home Base identity -------------------------------------------------------------------


def load_server_id(data_dir: Path) -> str:
    """The Home Base's random 16-byte ID (base64url). Made on first use, kept in the data folder."""
    path = data_dir / SERVER_ID_FILENAME
    try:
        return b64u_encode(b64u_decode(path.read_text(encoding="ascii").strip(), 16))
    except (OSError, ValueError):
        server_id = b64u_encode(os.urandom(16))
        write_private_bytes(path, server_id.encode("ascii"))
        return server_id


# --- Sessions (the QR code) ---------------------------------------------------------------


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


def _end_session(session: Session, session_id: int, now: int, *, cancel: bool) -> None:
    """Erase the session's private key and nonces. Caller commits."""
    values = {"pair_sk": None}
    if cancel:
        values["cancelled_at"] = now
    session.execute(
        update(PairingSession)
        .where(PairingSession.id == session_id)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    session.execute(delete(PairingNonce).where(PairingNonce.session_id == session_id))


def purge_ended_sessions(session: Session, now: int) -> None:
    """Erase private keys of sessions that have ended (expired, used, or cancelled)."""
    ended = session.scalars(
        select(PairingSession.id).where(
            PairingSession.pair_sk.is_not(None),
            (PairingSession.exp <= now)
            | PairingSession.used_at.is_not(None)
            | PairingSession.cancelled_at.is_not(None),
        )
    ).all()
    for session_id in ended:
        _end_session(session, session_id, now, cancel=False)
    session.commit()


def start_session(
    session: Session, *, now: int, host: str, port: int, server_id: str, server_name: str
) -> dict:
    """Begin pairing: cancel any unused QR and return the payload for the new one (§2.1)."""
    unused = session.scalars(
        select(PairingSession.id).where(
            PairingSession.used_at.is_(None), PairingSession.cancelled_at.is_(None)
        )
    ).all()
    for session_id in unused:
        _end_session(session, session_id, now, cancel=True)

    code = b64u_encode(os.urandom(16))
    secret = PrivateKey.generate()
    exp = now + CODE_TTL_SECONDS
    pair_pub = b64u_encode(bytes(secret.public_key))
    session.add(
        PairingSession(
            code_hash=_hash_code(code),
            pair_pub=pair_pub,
            pair_sk=b64u_encode(bytes(secret)),
            created_at=now,
            exp=exp,
        )
    )
    session.commit()
    purge_ended_sessions(session, now)
    return {
        "v": CONTRACT,
        "app": APP_ID,
        "host": host,
        "port": port,
        "code": code,
        "pair_pub": pair_pub,
        "server_id": server_id,
        "name": server_name[:50],
        "exp": exp,
    }


def active_session(session: Session, now: int) -> PairingSession | None:
    return session.scalar(
        select(PairingSession)
        .where(
            PairingSession.used_at.is_(None),
            PairingSession.cancelled_at.is_(None),
            PairingSession.exp > now,
        )
        .order_by(PairingSession.id.desc())
        .limit(1)
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

    if not hmac.compare_digest(_hash_code(code), pairing.code_hash):
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
    _end_session(session, session_id, now, cancel=False)  # erases pair_sk with the claim
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
        _end_session(session, session_id, now, cancel=True)
    session.commit()


def lan_wanted(session: Session, now: int) -> bool:
    """Should the home-network listener be open? Yes during a pairing, or with a paired phone."""
    return active_session(session, now) is not None or device_count(session) > 0


def device_count(session: Session) -> int:
    return (
        session.scalar(select(func.count()).select_from(Device).where(Device.revoked.is_(False)))
        or 0
    )
