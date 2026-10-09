import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import Offset, PathId, SessionDep
from app.schemas.paychecks import (
    DepositLink,
    PaycheckCreate,
    PaycheckOut,
    PaycheckPage,
    PaycheckSummary,
    PaycheckUpdate,
    PayDeposit,
)
from app.services import paychecks as service
from app.services.pay_deposits import waiting_deposits

router = APIRouter(prefix="/api/local/paychecks", tags=["paychecks"])

Year = Annotated[int, Query(ge=2000, le=2100)]


@router.get("")
def list_paychecks(
    session: SessionDep,
    year: Year | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> PaycheckPage:
    return service.list_paychecks(session, year, limit, offset)


@router.get("/summary")
def year_summary(session: SessionDep, year: Year | None = None) -> PaycheckSummary:
    """Year-to-date totals (this calendar year unless ``year`` is given)."""
    return service.year_summary(session, year or dt.date.today().year)


# Declared before "/{paycheck_id}" so the path isn't read as an ID.
@router.get("/deposits")
def pay_deposits(session: SessionDep, year: Year | None = None) -> list[PayDeposit]:
    """Pay deposits not linked to a paycheck yet (this calendar year unless ``year`` is given)."""
    return waiting_deposits(session, year or dt.date.today().year)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_paycheck(data: PaycheckCreate, session: SessionDep) -> PaycheckOut:
    return service.create_paycheck(session, data)


@router.get("/{paycheck_id}")
def get_paycheck(paycheck_id: PathId, session: SessionDep) -> PaycheckOut:
    return service.get_paycheck(session, paycheck_id)


@router.patch("/{paycheck_id}")
def update_paycheck(paycheck_id: PathId, data: PaycheckUpdate, session: SessionDep) -> PaycheckOut:
    return service.update_paycheck(session, paycheck_id, data)


@router.delete("/{paycheck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paycheck(paycheck_id: PathId, session: SessionDep) -> None:
    service.delete_paycheck(session, paycheck_id)


@router.post("/{paycheck_id}/deposit")
def link_deposit(paycheck_id: PathId, data: DepositLink, session: SessionDep) -> PaycheckOut:
    return service.link_deposit(session, paycheck_id, data.transaction_id)


@router.delete("/{paycheck_id}/deposit")
def unlink_deposit(paycheck_id: PathId, session: SessionDep) -> PaycheckOut:
    return service.unlink_deposit(session, paycheck_id)
