"""Tax preferences (roadmap 25j). This computer and joined computers, like the tax summary they
narrow (ADR-0009): a filing status opens no connection and lets nothing in. Phones never reach
``/api/local``."""

from fastapi import APIRouter

from app.deps import SessionDep
from app.schemas.tax.tax_preferences import TaxPreferences
from app.services.tax import tax_preferences as service

router = APIRouter(prefix="/api/local/tax-preferences", tags=["tax summary"])


@router.get("")
def get_tax_preferences(session: SessionDep) -> TaxPreferences:
    return service.get_preferences(session)


@router.put("")
def save_tax_preferences(data: TaxPreferences, session: SessionDep) -> TaxPreferences:
    """Choose the filing status the tax summary shows, or null to show all of them."""
    return service.save_preferences(session, data)
