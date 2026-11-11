"""Bank and card OFX/QFX import for one account (roadmap 26-2, ADR-0016). The body is the file.

1. ``POST .../ofx-import/preview``: which account in the file is used and what would be imported.
2. ``POST .../ofx-import``: import it. Same file, same choices.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.deps import PathId, SessionDep
from app.errors import ApiError
from app.routers.imports.upload import read_upload
from app.schemas.imports.ofx_import import OfxChoices, OfxCommitChoices, OfxImportResult, OfxPreview
from app.services.imports import ofx_import as service
from app.services.imports import ofx_parsing

router = APIRouter(prefix="/api/local/accounts/{account_id}/ofx-import", tags=["ofx import"])

# Browsers and Windows label .ofx and .qfx files in different ways.
OFX_TYPES = frozenset(
    "application/x-ofx application/ofx application/vnd.intu.qfx application/x-qfx text/ofx "
    "text/x-ofx text/plain application/octet-stream".split()
)


def _too_big() -> ApiError:
    return ApiError(
        413,
        "file_too_large",
        "This file is bigger than 5 MB. Please download a shorter date range from your bank.",
    )


async def ofx_upload(request: Request) -> bytes:
    """The request body, refused if it isn't labelled as a bank file or is over the size limit."""
    return await read_upload(
        request,
        OFX_TYPES,
        ofx_parsing.MAX_BYTES,
        ApiError(415, "not_an_ofx", "Please choose a bank download (its name ends .ofx or .qfx)."),
        _too_big(),
    )


OfxBody = Annotated[bytes, Depends(ofx_upload)]


@router.post("/preview")
def preview_import(
    account_id: PathId,
    data: OfxBody,
    choices: Annotated[OfxChoices, Query()],
    session: SessionDep,
) -> OfxPreview:
    return service.preview(session, account_id, data, choices)


@router.post("")
def import_ofx(
    account_id: PathId,
    data: OfxBody,
    choices: Annotated[OfxCommitChoices, Query()],
    session: SessionDep,
) -> OfxImportResult:
    return service.commit(session, account_id, data, choices)
