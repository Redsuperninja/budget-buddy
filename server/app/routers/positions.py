"""Positions from a broker's file (a snapshot per account). The import's body is the CSV file.

1. ``POST /api/local/stocks/positions/import/preview``: the columns found and the positions.
2. ``POST /api/local/stocks/positions/import``: replace the account's snapshot with them.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import PathId, SessionDep
from app.routers.imports.csv_import import CsvBody
from app.schemas.positions import PositionsChoices, PositionsOut, PositionsPreview, PositionsResult
from app.services import positions as service

router = APIRouter(prefix="/api/local/stocks/positions", tags=["stocks"])


@router.get("")
def list_positions(session: SessionDep) -> PositionsOut:
    """Each account's latest positions, next to what your recorded trades add up to."""
    return service.list_positions(session)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_positions(account_id: PathId, session: SessionDep) -> None:
    """Forget an account's positions snapshot."""
    service.clear(session, account_id)


@router.post("/import/preview")
def preview_import(
    data: CsvBody, choices: Annotated[PositionsChoices, Query()], session: SessionDep
) -> PositionsPreview:
    return service.preview(session, data, choices)


@router.post("/import")
def import_positions(
    data: CsvBody, choices: Annotated[PositionsChoices, Query()], session: SessionDep
) -> PositionsResult:
    return service.commit(session, data, choices)
