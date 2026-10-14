"""Pairing sessions: the Home Base identity, the QR code's session and who is paired (§2.1).

Nothing here logs or returns the code or keys except the payload that has to carry them.
Times are Unix seconds passed in by the caller (so tests can control the clock).
"""

import os
from pathlib import Path

from nacl.public import PrivateKey
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.crypto._fs import write_private_bytes
from app.crypto.b64url import b64u_decode, b64u_encode
from app.crypto.hashing import hash_secret
from app.models import Device, PairingNonce, PairingSession
from app.services.devices.envelope import CONTRACT

APP_ID = "budget-buddy"
CODE_TTL_SECONDS = 600
SERVER_ID_FILENAME = "server-id"


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


def hash_code(code: str) -> str:
    return hash_secret(code)


def end_session(session: Session, session_id: int, now: int, *, cancel: bool) -> None:
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
        end_session(session, session_id, now, cancel=False)
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
        end_session(session, session_id, now, cancel=True)

    code = b64u_encode(os.urandom(16))
    secret = PrivateKey.generate()
    exp = now + CODE_TTL_SECONDS
    pair_pub = b64u_encode(bytes(secret.public_key))
    session.add(
        PairingSession(
            code_hash=hash_code(code),
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


def lan_wanted(session: Session, now: int) -> bool:
    """Should the home-network listener be open? Yes during a pairing, or with a paired phone."""
    return active_session(session, now) is not None or device_count(session) > 0


def device_count(session: Session) -> int:
    return (
        session.scalar(select(func.count()).select_from(Device).where(Device.revoked.is_(False)))
        or 0
    )
