"""Brokerage activity import into one account. The request body is the CSV file itself.

1. ``POST .../activity-import/preview``: the columns found, and what would be added.
2. ``POST .../activity-import``: add it, sorted (trades, dividends, transfers). Same file.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import PathId, SessionDep
from app.routers.imports.csv_import import CsvBody
from app.schemas.imports.activity_import import ActivityChoices, ActivityPreview, ActivityResult
from app.services.imports import activity_import as service

router = APIRouter(prefix="/api/local/accounts/{account_id}/activity-import", tags=["csv import"])


@router.post("/preview")
def preview_import(account_id: PathId, data: CsvBody, session: SessionDep) -> ActivityPreview:
    return service.preview(session, account_id, data)


@router.post("")
def import_activity(
    account_id: PathId,
    data: CsvBody,
    choices: Annotated[ActivityChoices, Query()],
    session: SessionDep,
) -> ActivityResult:
    return service.commit(session, account_id, data, choices)
