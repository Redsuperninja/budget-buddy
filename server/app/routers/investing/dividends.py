from typing import Annotated

from fastapi import APIRouter, Path, status

from app.deps import PathId, SessionDep
from app.schemas.investing.dividends import DividendsFound, DividendsOut
from app.services.investing import dividends as service
from app.services.investing.combined_sweeps import link_combined
from app.services.investing.dividend_matching import find_dividends

router = APIRouter(prefix="/api/local/dividends", tags=["dividends"])

TaxYear = Annotated[int, Path(ge=2000, le=2100)]


@router.post("/find")
def find(session: SessionDep) -> DividendsFound:
    """Look through every transaction for dividends and their deposit sweeps."""
    found = find_dividends(session)
    combined = link_combined(session)  # one sweep for several dividends (or trades)
    session.commit()
    return DividendsFound(found=found.dividends, sweeps_linked=found.sweeps + combined)


@router.get("/{tax_year}")
def list_dividends(tax_year: TaxYear, session: SessionDep) -> DividendsOut:
    """Dividends paid in one tax year, with the total and the taxed part. An estimate."""
    return service.list_dividends(session, tax_year)


@router.post("/{dividend_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(dividend_id: PathId, session: SessionDep) -> None:
    """Not a dividend: leave it out from now on."""
    service.dismiss(session, dividend_id)
