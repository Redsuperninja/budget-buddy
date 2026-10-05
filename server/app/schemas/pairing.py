import datetime as dt

from pydantic import BaseModel

from app.schemas.common import Schema


class PairingPayload(BaseModel):
    """The QR code's contents (sync contract §2.1). ``code`` is secret: never log it."""

    v: int
    app: str
    host: str
    port: int
    code: str
    pair_pub: str
    server_id: str
    name: str
    exp: int


class PairingStarted(BaseModel):
    payload: PairingPayload
    # The same payload as one line of text, for "Show code as text" (paste into the phone).
    payload_text: str
    expires_at: int
    seconds_valid: int
    # False when Budget Buddy is only listening on this computer, so a phone can't reach it yet.
    phone_can_connect: bool
    message: str | None = None


class DeviceOut(Schema):
    id: int
    name: str
    platform: str | None
    app_version: str | None
    paired_at: dt.datetime
    last_sync_at: dt.datetime | None
    revoked: bool
    revoked_at: dt.datetime | None
