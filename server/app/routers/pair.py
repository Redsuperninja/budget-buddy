"""``POST /api/pair``: the phone's side of pairing (sync contract §3.6, §4.4).

Open to the home network. Everything in the body is encrypted with a key only this computer and
the scanning phone can compute, so nothing here is logged.
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.deps import SessionDep
from app.errors import ApiError
from app.services import pairing as service

router = APIRouter(prefix="/api", tags=["pairing"])

BODY_LIMIT_BYTES = 16 * 1024


async def _read_body(request: Request) -> bytes:
    """Read the body, stopping at the limit (don't trust Content-Length alone)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > BODY_LIMIT_BYTES:
        raise _too_large()
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > BODY_LIMIT_BYTES:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


def _too_large() -> ApiError:
    return ApiError(413, "too_large", "That was too much data to send at once. Try again.")


@router.post("/pair")
async def pair(request: Request, session: SessionDep) -> JSONResponse:
    state = request.app.state
    now = state.clock()
    peer = request.client.host if request.client else "unknown"
    if not state.pair_limiter.allow(peer, now):
        raise ApiError(
            429, "too_many_attempts", "Too many tries. Wait a minute, then scan the code again."
        )

    pairing = service.require_active_session(session, now)

    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        raise ApiError(400, "bad_request", service.SERVER_ERROR_MESSAGE)
    body = await _read_body(request)
    try:
        outer = json.loads(body)
    except (ValueError, RecursionError):  # not JSON, or nested so deep it can't be read
        raise ApiError(400, "bad_request", service.SERVER_ERROR_MESSAGE) from None

    result = service.pair(
        session,
        pairing,
        outer,
        now=now,
        server_id=state.server_id,
        server_name=state.settings.server_name,
    )
    return JSONResponse(
        status_code=result.status, content=result.envelope, headers={"Cache-Control": "no-store"}
    )
