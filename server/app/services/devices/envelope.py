"""The encrypted request and response envelope shared by pairing and sync (sync contract §4).

Opening and sealing live here once, so ``/api/pair`` and ``/api/sync/*`` can't drift apart. Nothing
in this module logs, and error messages are fixed text: no keys, nonces, or message contents.
"""

import json
import os
from dataclasses import dataclass

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError

CONTRACT = 1
CLOCK_WINDOW_SECONDS = 300

SERVER_ERROR_MESSAGE = "Something went wrong. Try again in a minute."
UPDATE_MESSAGE = (
    "Budget Buddy needs an update on your phone or computer so they can talk to each other."
)
REPLAY_MESSAGE = "Sync got interrupted. Please try again."
CLOCK_MESSAGE = (
    "The clock on your phone or your computer is wrong. Turn on automatic date and time on "
    "both, then try again."
)
DECRYPT_FAILED_MESSAGE = (
    "This phone's connection to your computer needs to be set up again. Please pair again."
)


class EncryptedError(Exception):
    """An error to send back inside the encrypted envelope (the box already opened)."""

    def __init__(self, status: int, code: str, message: str, **extra) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


def bad_request() -> ApiError:
    return ApiError(400, "bad_request", SERVER_ERROR_MESSAGE)


def bad_data() -> EncryptedError:
    """The decrypted request's ``data`` is wrong; answered inside the encrypted envelope."""
    return EncryptedError(400, "bad_request", SERVER_ERROR_MESSAGE)


def decrypt_failed() -> ApiError:
    return ApiError(401, "decrypt_failed", DECRYPT_FAILED_MESSAGE)


def update_needed() -> ApiError:
    return ApiError(426, "update_needed", UPDATE_MESSAGE, supported=[CONTRACT])


@dataclass(frozen=True)
class Outer:
    """The plaintext part of a request envelope, after strict decoding."""

    nonce: bytes
    box: bytes
    ts: int
    phone_pub: bytes | None = None


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_outer(outer: object, *, with_phone_pub: bool = False) -> Outer:
    """Step 3 of §4.4: the envelope's own fields. Raises plaintext ``ApiError``."""
    if not isinstance(outer, dict):
        raise bad_request()
    version = outer.get("v")
    if not is_int(version):
        raise bad_request()  # no usable version at all: not one of our envelopes
    if version != CONTRACT:
        raise update_needed()
    try:
        nonce = b64u_decode(outer.get("nonce"), 24)
        box = b64u_decode(outer.get("box"))
        phone_pub = b64u_decode(outer.get("phone_pub"), 32) if with_phone_pub else None
    except ValueError:
        raise bad_request() from None
    ts = outer.get("ts")
    if len(box) < 16 or not is_int(ts):
        raise bad_request()
    return Outer(nonce=nonce, box=box, ts=ts, phone_pub=phone_pub)


def check_clock(ts: int, now: int, watermark: int = 0) -> None:
    """Step 4 of §4.4: within five minutes of now, and not older than the replay watermark."""
    if abs(now - ts) > CLOCK_WINDOW_SECONDS or ts < watermark:
        raise ApiError(400, "clock_skew", CLOCK_MESSAGE, server_time=now)


def open_request(key: bytes, outer: Outer, *, path: str, method: str = "POST") -> dict:
    """Steps 5 and 6 of §4.4: open the box and check the inner request is meant for this call.

    Any failure is plaintext 401 ``decrypt_failed`` (there is no trusted sender to answer yet).
    """
    try:
        inner = json.loads(SecretBox(key).decrypt(outer.box, outer.nonce))
    except (CryptoError, ValueError, RecursionError):
        raise decrypt_failed() from None
    if (
        not isinstance(inner, dict)
        or inner.get("type") != "req"
        or inner.get("ts") != outer.ts
        or inner.get("method") != method
        or inner.get("path") != path
    ):
        raise decrypt_failed()
    return inner


def check_contract(inner: dict) -> None:
    """Encrypted 426 when the phone speaks a contract version we don't."""
    if inner.get("contract") != CONTRACT or not is_int(inner.get("contract")):
        raise EncryptedError(426, "update_needed", UPDATE_MESSAGE, supported=[CONTRACT])


def seal(key: bytes, request_nonce: str, now: int, status: int, **body) -> dict:
    """A response envelope (§4.3) with a fresh random nonce, answering ``request_nonce``."""
    inner = {"type": "res", "ts": now, "re": request_nonce, "status": status, **body}
    plaintext = json.dumps(inner, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    nonce = os.urandom(24)
    box = SecretBox(key).encrypt(plaintext, nonce).ciphertext
    return {"v": CONTRACT, "nonce": b64u_encode(nonce), "ts": now, "box": b64u_encode(box)}


def seal_error(key: bytes, request_nonce: str, now: int, err: EncryptedError) -> dict:
    error = {"code": err.code, "message": err.message, **err.extra}
    return seal(key, request_nonce, now, err.status, error=error)
