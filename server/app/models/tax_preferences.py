"""Tax preferences (roadmap 25j): the filing status that narrows the yearly tax summary."""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.tax_data import FILING_STATUSES

_ALLOWED = ", ".join(f"'{s}'" for s in FILING_STATUSES)


class TaxPreferences(TimestampMixin, Base):
    """One row (id 1), made when first saved. ``filing_status`` null means "Not set: show all".
    Plain text, not encrypted: one of four fixed words (see migration 0030)."""

    __tablename__ = "tax_preferences"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint(f"filing_status IN ({_ALLOWED})", name="known_filing_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_status: Mapped[str | None] = mapped_column(String(32))
