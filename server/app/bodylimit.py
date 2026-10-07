"""Read a request body without ever holding more than the endpoint's limit (sync contract §3.2)."""

from fastapi import Request

from app.errors import ApiError

PAIR_LIMIT_BYTES = 16 * 1024
SMALL_SYNC_LIMIT_BYTES = 16 * 1024  # snapshot and ack
RECEIPTS_LIMIT_BYTES = 12 * 1024 * 1024


def too_large() -> ApiError:
    return ApiError(413, "too_large", "That was too much data to send at once. Try again.")


async def read_limited(request: Request, limit: int) -> bytes:
    """The body, stopping as soon as it goes over ``limit`` (don't trust Content-Length alone)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise too_large()
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_large()
        chunks.append(chunk)
    return b"".join(chunks)
