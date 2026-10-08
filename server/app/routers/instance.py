"""This computer only: the desktop app's check that this Home Base is really Budget Buddy
(``app.instance_proof``). Not on the joined computers' allow-list."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.instance_proof import NONCE, proof

router = APIRouter(tags=["instance"], include_in_schema=False)


@router.get("/api/local/instance/proof")
def instance_proof(
    request: Request, nonce: Annotated[str, Query(pattern=NONCE.pattern)]
) -> JSONResponse:
    return JSONResponse(
        {"proof": proof(request.app.state.instance_key, nonce)},
        headers={"Cache-Control": "no-store"},
    )
