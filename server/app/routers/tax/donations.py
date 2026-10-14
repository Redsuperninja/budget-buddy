from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.deps import Offset, PathId, SessionDep
from app.models import DonationKind
from app.schemas.tax.donations import (
    DonationCreate,
    DonationOut,
    DonationPage,
    DonationSummary,
    DonationUpdate,
)
from app.services.tax import donations as service

router = APIRouter(prefix="/api/local/donations", tags=["donations"])

TaxYear = Annotated[int, Path(ge=2000, le=2100)]


@router.get("")
def list_donations(
    session: SessionDep,
    tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    kind: DonationKind | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> DonationPage:
    return service.list_donations(session, service.DonationFilters(tax_year, kind, limit, offset))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_donation(data: DonationCreate, session: SessionDep) -> DonationOut:
    return service.create_donation(session, data)


# Declared before "/{donation_id}" so "summary" isn't read as an ID.
@router.get("/summary/{tax_year}")
def donation_summary(tax_year: TaxYear, session: SessionDep) -> DonationSummary:
    """Totals for one tax year and the paperwork each gift needs. An estimate, not tax advice."""
    return service.summary(session, tax_year)


@router.get("/{donation_id}")
def get_donation(donation_id: PathId, session: SessionDep) -> DonationOut:
    return service.donation_out(session, donation_id)


@router.patch("/{donation_id}")
def update_donation(donation_id: PathId, data: DonationUpdate, session: SessionDep) -> DonationOut:
    return service.update_donation(session, donation_id, data)


@router.delete("/{donation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_donation(donation_id: PathId, session: SessionDep) -> None:
    service.delete_donation(session, donation_id)
