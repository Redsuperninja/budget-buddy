"""One upload check for the file-as-request-body imports (CSV and OFX)."""

from collections.abc import Collection

from fastapi import Request

from app.errors import ApiError


async def read_upload(
    request: Request,
    allowed_types: Collection[str],
    limit: int,
    wrong_type: ApiError,
    too_big: ApiError,
) -> bytes:
    """The request body, refused if its label isn't allowed or it is over ``limit`` bytes.

    The size is checked early from Content-Length, then again as the body streams in, so a missing
    or false header can't get a large file through.
    """
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in allowed_types:
        raise wrong_type
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_big
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise too_big
    return bytes(body)
