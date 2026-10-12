"""Bank CSV import for one account (roadmap #6). The request body is the CSV file itself.

1. ``POST .../csv-import/preview``: what the columns look like and what would be imported.
2. ``POST .../csv-import``: import it. Same file, same choices.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.deps import PathId, SessionDep
from app.errors import ApiError
from app.schemas.imports.csv_import import (
    CommitChoices,
    ImportPreview,
    ImportResult,
    MappingChoices,
)
from app.services.imports import csv_import as service

router = APIRouter(prefix="/api/local/accounts/{account_id}/csv-import", tags=["csv import"])

# Browsers label .csv files differently (Windows often says it's an Excel file).
CSV_TYPES = frozenset(
    "text/csv text/plain application/csv text/comma-separated-values application/vnd.ms-excel "
    "application/octet-stream".split()
)
_MB = 1024 * 1024


def _too_big() -> ApiError:
    return ApiError(
        413,
        "file_too_large",
        f"This file is bigger than {service.MAX_UPLOAD_BYTES // _MB} MB. Please export a shorter "
        "date range and import it in parts.",
    )


async def csv_upload(request: Request) -> bytes:
    """The request body, refused if it isn't labelled as a CSV or is over the size limit."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in CSV_TYPES:
        raise ApiError(415, "not_a_csv", "Please choose a CSV file (its name usually ends .csv).")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > service.MAX_UPLOAD_BYTES:
        raise _too_big()
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > service.MAX_UPLOAD_BYTES:
            raise _too_big()
    return bytes(body)


CsvBody = Annotated[bytes, Depends(csv_upload)]


@router.post("/preview")
def preview_import(
    account_id: PathId,
    data: CsvBody,
    choices: Annotated[MappingChoices, Query()],
    session: SessionDep,
) -> ImportPreview:
    return service.preview(session, account_id, data, choices)


@router.post("")
def import_csv(
    account_id: PathId,
    data: CsvBody,
    choices: Annotated[CommitChoices, Query()],
    session: SessionDep,
) -> ImportResult:
    return service.commit(session, account_id, data, choices)


@router.delete("/mapping", status_code=status.HTTP_204_NO_CONTENT)
def forget_mapping(account_id: PathId, session: SessionDep) -> None:
    service.forget_mapping(session, account_id)
