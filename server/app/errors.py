"""One error shape for the whole API: ``{"error": {"code": ..., "message": ...}}``.

``code`` is stable and machine-readable; ``message`` is plain English. This matches the sync
contract's error style. Messages never include amounts, descriptions, SQL, or exception text.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(thing: str) -> ApiError:
    return ApiError(404, "not_found", f"That {thing} doesn't exist. It may have been deleted.")


def error_response(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message, **extra}}
    )


def _field_name(loc: tuple) -> str | None:
    # ("body", "amount") -> "amount"; ("query", "limit") -> "limit"; ("body",) -> None
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or None


def _plain(msg: str) -> str:
    # Our own validators raise ValueError("..."), which Pydantic prefixes with "Value error, ".
    return msg.removeprefix("Value error, ")


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": _field_name(e["loc"]), "message": _plain(e["msg"])} for e in exc.errors()]
    first = fields[0] if fields else {"field": None, "message": "Something in the request is off."}
    message = first["message"]
    if first["field"]:
        message = f"Please check {first['field']}: {message}"
    return error_response(422, "validation_error", message, fields=fields)


async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message)


async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(404, "not_found", "That page doesn't exist.")
    if exc.status_code == 405:
        return error_response(405, "method_not_allowed", "That action isn't supported here.")
    return error_response(exc.status_code, "http_error", str(exc.detail))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
