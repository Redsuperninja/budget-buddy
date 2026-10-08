from typing import Annotated

from fastapi import APIRouter, Path

from app.deps import SessionDep
from app.schemas.retirement import RetirementOut
from app.services import retirement as service

router = APIRouter(prefix="/api/local/retirement", tags=["retirement"])


@router.get("/{tax_year}")
def contributions(
    tax_year: Annotated[int, Path(ge=2000, le=2100)], session: SessionDep
) -> RetirementOut:
    """This year's 401(k), IRA and HSA contributions against the limits. An estimate."""
    return service.contributions(session, tax_year)
