"""Encrypted sync for a paired phone (sync contract §3.7 to §3.9, §4.4, §6).

``open_and_run`` is the one path every ``/api/sync/*`` request takes after the token has been
checked and the body read: envelope checks, replay protection, then the endpoint's work. The
endpoint functions below only see already-decrypted, already-replay-checked data.

Nothing here logs receipt details, amounts, keys, nonces, or photo bytes. Errors that go back to
the phone use fixed text.
"""

import datetime as dt
import json
import re

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError
from app.models import Device, SeenNonce
from app.services import devices as device_service
from app.services import envelope, snapshot
from app.services.envelope import EncryptedError, bad_data
from app.services.sync_context import Endpoint, SyncContext

WATERMARK_LAG_SECONDS = 600  # twice the clock window (§4.4)

_RFC3339_Z = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def open_and_run(
    ctx: SyncContext, body: bytes, *, path: str, endpoint: Endpoint
) -> tuple[int, dict]:
    """Steps 3 to 8 of §4.4 for a paired phone. Returns ``(status, response envelope)``.

    Problems before the box opens raise ``ApiError`` (plaintext). From the replay check on,
    every answer, including errors, is encrypted with the device's sync key.
    """
    session, device, now = ctx.session, ctx.device, ctx.now
    try:
        outer_json = json.loads(body)
    except (ValueError, RecursionError):  # not JSON, or nested so deep it can't be read
        raise envelope.bad_request() from None
    outer = envelope.parse_outer(outer_json)
    envelope.check_clock(outer.ts, now, device.nonce_watermark)
    if device.sync_key is None:  # defensive: only a removed phone has no key
        raise envelope.decrypt_failed()
    try:
        key = b64u_decode(device.sync_key, 32)
    except ValueError:
        raise envelope.decrypt_failed() from None
    inner = envelope.open_request(key, outer, path=path)

    request_nonce = b64u_encode(outer.nonce)
    try:
        envelope.check_contract(inner)
        _remember_nonce(session, device, outer.nonce, outer.ts)
        data = endpoint(ctx, inner.get("data"))
        device_service.ensure_active(session, device.id)  # removed while the endpoint ran?
        return 200, envelope.seal(key, request_nonce, now, 200, data=data)
    except ApiError:  # the phone was removed while the request was in flight: plaintext 401
        session.rollback()
        raise
    except EncryptedError as err:
        session.rollback()
        return err.status, envelope.seal_error(key, request_nonce, now, err)
    except Exception:  # never show the phone anything about what broke
        session.rollback()
        err = EncryptedError(500, "server_error", envelope.SERVER_ERROR_MESSAGE)
        return err.status, envelope.seal_error(key, request_nonce, now, err)


def _remember_nonce(session: Session, device: Device, nonce: bytes, ts: int) -> None:
    """Step 7 of §4.4: insert first; a duplicate means this exact request was already used.

    In the same transaction the device is checked again: a phone removed while its body was still
    arriving must not finish with its old key (nothing is saved, plaintext ``device_revoked``).
    Then the device's watermark moves up (only ever, in SQL, by an accepted request's own
    timestamp) and nonces older than the stored value are pruned.
    """
    try:
        session.add(SeenNonce(device_id=device.id, nonce=nonce, ts=ts))
        session.flush()
    except IntegrityError:
        session.rollback()
        raise EncryptedError(409, "replay", envelope.REPLAY_MESSAGE) from None
    moved = session.execute(
        update(Device)
        .where(*device_service.active_clauses(device.id))
        .values(nonce_watermark=func.max(Device.nonce_watermark, ts - WATERMARK_LAG_SECONDS))
    )
    if moved.rowcount != 1:
        session.rollback()
        raise device_service.revoked_error()
    watermark = session.scalar(select(Device.nonce_watermark).where(Device.id == device.id))
    session.execute(
        delete(SeenNonce).where(SeenNonce.device_id == device.id, SeenNonce.ts < watermark)
    )
    session.commit()


# --- POST /api/sync/snapshot ---------------------------------------------------------------


def snapshot_endpoint(ctx: SyncContext, data: object) -> dict:
    if not isinstance(data, dict):
        raise bad_data()
    return snapshot.build_snapshot(ctx.session, now=ctx.now, server_id=ctx.server_id)


# --- POST /api/sync/ack --------------------------------------------------------------------


def ack_endpoint(ctx: SyncContext, data: object) -> dict:
    """The phone finished a sync: remember when (the dashboard's "Last synced")."""
    if not isinstance(data, dict):
        raise bad_data()
    generated, uploaded, version = (
        data.get("snapshot_generated_at"),
        data.get("receipts_uploaded"),
        data.get("app_version"),
    )
    if (
        not isinstance(generated, str)
        or not _RFC3339_Z.fullmatch(generated)
        or not envelope.is_int(uploaded)
        or not 0 <= uploaded <= 1_000_000
        or not isinstance(version, str)
        or len(version) > 32
        or not version.isprintable()
    ):
        raise bad_data()
    moment = dt.datetime.fromtimestamp(ctx.now, dt.UTC)
    ctx.device.last_sync_at = moment.replace(tzinfo=None)  # stored as naive UTC
    ctx.device.app_version = version
    ctx.session.commit()
    return {"last_sync_at": snapshot.utc_timestamp(ctx.now)}
