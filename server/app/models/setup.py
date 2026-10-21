import datetime as dt

from sqlalchemy import CheckConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SetupProgress(Base):
    """First-start setup progress (ADR-0015): one row (id 1), made when first saved. Dates only,
    in UTC; never the recovery phrase, a key or file contents."""

    __tablename__ = "setup_progress"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    phrase_saved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    # Set by the server when it writes a backup file; the browser can't set it.
    last_backup_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
