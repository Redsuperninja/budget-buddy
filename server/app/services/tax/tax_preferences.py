"""Tax preferences (roadmap 25j): the filing status that narrows the yearly tax summary.

One row, made when first saved; no row means "Not set: show all", so nothing changes for people
who never choose. This only picks which numbers are shown, never how any are worked out.
"""

from sqlalchemy.orm import Session

from app.models import TaxPreferences as Row
from app.schemas.tax.tax_preferences import TaxPreferences

ROW_ID = 1


def filing_status(session: Session) -> str | None:
    row = session.get(Row, ROW_ID)
    return row.filing_status if row else None


def get_preferences(session: Session) -> TaxPreferences:
    return TaxPreferences(filing_status=filing_status(session))


def save_preferences(session: Session, data: TaxPreferences) -> TaxPreferences:
    row = session.get(Row, ROW_ID) or Row(id=ROW_ID)
    row.filing_status = data.filing_status
    session.add(row)
    session.commit()
    return get_preferences(session)
