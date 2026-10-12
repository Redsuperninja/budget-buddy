"""Stock CSV import (purchases and sales). The request body is the CSV file itself.

1. ``POST /api/local/stocks/import/preview``: which columns were found and what would be added.
2. ``POST /api/local/stocks/import``: add it. Same file, same choices.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep
from app.routers.imports.csv_import import CsvBody
from app.schemas.imports.stock_import import (
    StockCommitChoices,
    StockImportChoices,
    StockImportPreview,
    StockImportResult,
)
from app.services.imports import stock_import as service

router = APIRouter(prefix="/api/local/stocks/import", tags=["stocks"])


@router.post("/preview")
def preview_import(
    data: CsvBody, choices: Annotated[StockImportChoices, Query()], session: SessionDep
) -> StockImportPreview:
    return service.preview(session, data, choices)


@router.post("")
def import_stocks(
    data: CsvBody, choices: Annotated[StockCommitChoices, Query()], session: SessionDep
) -> StockImportResult:
    return service.commit(session, data, choices)
