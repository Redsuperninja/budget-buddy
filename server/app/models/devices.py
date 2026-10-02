import datetime as dt

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

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
