"""Serves the computer dashboard (roadmap #16) from the ``dashboard/`` folder (ADR-0005).

Everything is local: no scripts, fonts or images come from the internet. These routes are not
phone routes, so ``LocalAccessMiddleware`` already answers this computer only. The page carries
the per-run CSRF token in a ``<meta>`` tag (inline script is barred by the CSP, so the page's
script reads it from there) and sends it back on every write.
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.dashboard_files import CONTENT_TYPES
from app.errors import not_found
from app.remote_access import TOKEN_OK

router = APIRouter(tags=["dashboard"], include_in_schema=False)

# Scripts and styles may only come from this same address; no inline script; no framing.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
}
TOKEN_PLACEHOLDER = "__CSRF_TOKEN__"
HTML = "text/html; charset=utf-8"
NO_DASHBOARD_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Budget Buddy</title></head>'
    "<body><h1>Budget Buddy is running</h1><p>The dashboard files weren't found, so there is "
    "no web page to show. Your phone can still connect.</p></body></html>"
)


@router.get("/")
def index(request: Request) -> Response:
    dashboard = request.app.state.dashboard
    html = dashboard.read_index() if dashboard else None
    headers = {**SECURITY_HEADERS, "Cache-Control": "no-store"}
    if html is None:  # API-only: no dashboard folder (ADR-0005)
        return Response(NO_DASHBOARD_PAGE, 404, media_type=HTML, headers=headers)
    # Only when the access rules said so (this computer, or a joined one): another computer that
    # hasn't joined gets the page without a token, so it can only join.
    token_ok = getattr(request.state, TOKEN_OK, False)
    html = html.replace(TOKEN_PLACEHOLDER, request.app.state.csrf_token if token_ok else "")
    return Response(html, media_type=HTML, headers=headers)


@router.get("/static/{name:path}")
def asset(name: str, request: Request) -> Response:
    dashboard = request.app.state.dashboard
    found = dashboard.read_asset_tagged(name) if dashboard else None
    if found is None:
        raise not_found("page")
    text, etag = found
    media_type = CONTENT_TYPES[PurePosixPath(name).suffix]
    # no-cache = the browser keeps a copy but asks every time; an unchanged file answers 304.
    headers = {**SECURITY_HEADERS, "Cache-Control": "no-cache", "ETag": etag}
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(text, media_type=media_type, headers=headers)


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    sent = [part.strip().removeprefix("W/") for part in header.split(",")]
    return "*" in sent or etag in sent


@router.get("/api/local/csrf-token")
def csrf_token(request: Request) -> JSONResponse:
    """For the helper scripts, which have no page to read the token from. Loopback + Host
    checked like every dashboard route, and no CORS headers, so other websites can't read it."""
    return JSONResponse(
        {"token": request.app.state.csrf_token}, headers={"Cache-Control": "no-store"}
    )
