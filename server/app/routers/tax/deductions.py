from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import PathId, SessionDep
from app.schemas.tax.deductions import DeductionCreate, DeductionOut, DeductionUpdate
from app.services.tax import deductions as service

router = APIRouter(prefix="/api/local/deductions", tags=["deductions"])


@router.get("")
def list_deductions(
    session: SessionDep, tax_year: Annotated[int, Query(ge=2000, le=2100)]
) -> list[DeductionOut]:
    return service.list_deductions(session, tax_year)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_deduction(data: DeductionCreate, session: SessionDep) -> DeductionOut:
    return service.create_deduction(session, data)


@router.get("/{deduction_id}")
def get_deduction(deduction_id: PathId, session: SessionDep) -> DeductionOut:
    return service.get_deduction(session, deduction_id)


@router.patch("/{deduction_id}")
def update_deduction(
    deduction_id: PathId, data: DeductionUpdate, session: SessionDep
) -> DeductionOut:
    return service.update_deduction(session, deduction_id, data)


@router.delete("/{deduction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deduction(deduction_id: PathId, session: SessionDep) -> None:
    service.delete_deduction(session, deduction_id)
