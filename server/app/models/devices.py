import datetime as dt

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin


class Device(TimestampMixin, Base):
    """A paired phone. Only a hash of its token is kept (roadmap #14)."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    paired_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    last_sync_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(default=False, server_default="0")
    platform: Mapped[str | None] = mapped_column(String(16))
    app_version: Mapped[str | None] = mapped_column(String(32))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    # base64url of the device's 32-byte sync key, encrypted at rest. Deleted when revoked.
    sync_key: Mapped[str | None] = mapped_column(EncryptedString("devices.sync_key"))
    # Requests older than this (Unix seconds) are refused, so old nonces can be pruned safely
    # (sync contract §4.4). Moves only with timestamps from accepted, authenticated requests.
    nonce_watermark: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class RemoteComputer(TimestampMixin, Base):
    """Another computer allowed to use the dashboard over the home network (ADR-0009). Only a hash
    of its cookie token is kept; removing it clears the hash, so the token stops working at once."""

    __tablename__ = "remote_computers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    # The home-network address it joined from; its cookie works only from there (ADR-0009).
    joined_from: Mapped[str] = mapped_column(String(45))
    paired_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class PairingSession(Base):
    """One QR code's pairing attempt (sync contract §2.3). Times are Unix seconds.

    Only ``sha256(code)`` is stored, never the code. ``pair_sk`` (base64url, encrypted at rest)
    is erased as soon as the session ends: used, expired, or cancelled.
    """

    __tablename__ = "pairing_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    pair_pub: Mapped[str] = mapped_column(String(43))
    pair_sk: Mapped[str | None] = mapped_column(EncryptedString("pairing_sessions.pair_sk"))
    created_at: Mapped[int] = mapped_column(Integer)
    exp: Mapped[int] = mapped_column(Integer)
    used_at: Mapped[int | None] = mapped_column(Integer)
    cancelled_at: Mapped[int | None] = mapped_column(Integer)
    wrong_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class PairingNonce(Base):
    """Nonces already seen in a pairing session, so a captured request can't be replayed."""

    __tablename__ = "pairing_nonces"
    __table_args__ = (UniqueConstraint("session_id", "nonce"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("pairing_sessions.id", ondelete="CASCADE"))
    nonce: Mapped[bytes] = mapped_column(LargeBinary(24))


class SeenNonce(Base):
    """A request nonce a paired phone has used, so a captured request can't be replayed (§4.4).

    ``nonce`` is the decoded 24 bytes, not the base64 text. Rows older than the device's
    ``nonce_watermark`` are pruned; rows go with the device when it is removed (§3.10).
    """

    __tablename__ = "seen_nonces"
    __table_args__ = (
        UniqueConstraint("device_id", "nonce"),
        Index("ix_seen_nonces_ts", "device_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    nonce: Mapped[bytes] = mapped_column(LargeBinary(24))
    ts: Mapped[int] = mapped_column(Integer)
