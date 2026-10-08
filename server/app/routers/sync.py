"""``POST /api/sync/*``: what a paired phone calls over the home Wi-Fi (sync contract §3.7 to §3.9).

Open to the home network. The phone's token is checked before the body is read; the body is
encrypted with the phone's sync key, so nothing in it is ever logged here.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.bodylimit import RECEIPTS_LIMIT_BYTES, SMALL_SYNC_LIMIT_BYTES, read_limited
from app.deps import SessionDep
from app.errors import ApiError
from app.services import devices as device_service
from app.services import envelope, sync_receipts
from app.services import sync as service
from app.services.sync_context import Endpoint, SyncContext

router = APIRouter(prefix="/api/sync", tags=["sync"])

_BEARER = "bearer "


def _bearer_token(request: Request) -> str:
    values = request.headers.getlist("authorization")
    token = ""
    if len(values) == 1 and values[0].lower().startswith(_BEARER):
        token = values[0][len(_BEARER) :].strip()
    if not token:
        raise ApiError(
            401,
            "not_paired",
            "This phone isn't connected to your computer anymore. Please pair again.",
        )
    return token


async def _run(
    request: Request, session: SessionDep, path: str, limit: int, endpoint: Endpoint
) -> JSONResponse:
    state = request.app.state
    # Who is asking comes first, before a single byte of the body is read (§4.4 step 2).
    device = device_service.authenticate_token(session, _bearer_token(request))
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise envelope.bad_request()
    body = await read_limited(request, limit)
    ctx = SyncContext(
        session=session,
        device=device,
        store=state.receipt_store,
        now=state.clock(),
        server_id=state.server_id,
    )
    try:
        status, reply = service.open_and_run(ctx, body, path=path, endpoint=endpoint)
    except ApiError:
        raise
    except Exception:  # fixed text only: never exception details
        session.rollback()
        raise ApiError(500, "server_error", envelope.SERVER_ERROR_MESSAGE) from None
    return JSONResponse(status_code=status, content=reply, headers={"Cache-Control": "no-store"})


@router.post("/receipts")
async def receipts(request: Request, session: SessionDep) -> JSONResponse:
    return await _run(
        request,
        session,
        "/api/sync/receipts",
        RECEIPTS_LIMIT_BYTES,
        sync_receipts.receipts_endpoint,
    )


@router.post("/snapshot")
async def snapshot(request: Request, session: SessionDep) -> JSONResponse:
    return await _run(
        request, session, "/api/sync/snapshot", SMALL_SYNC_LIMIT_BYTES, service.snapshot_endpoint
    )


@router.post("/ack")
async def ack(request: Request, session: SessionDep) -> JSONResponse:
    return await _run(
        request, session, "/api/sync/ack", SMALL_SYNC_LIMIT_BYTES, service.ack_endpoint
    )
