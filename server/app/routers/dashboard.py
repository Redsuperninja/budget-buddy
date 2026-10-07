"""The computer dashboard: a small web page served by the Home Base itself (roadmap #16).

Everything is local: no scripts, fonts or images come from the internet. These routes are not
phone routes, so ``LocalAccessMiddleware`` already answers this computer only. The page carries
the per-run CSRF token in a ``<meta>`` tag (inline script is barred by the CSP, so the page's
script reads it from there) and sends it back on every write.
"""

from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import PurePosixPath

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.errors import not_found

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
CONTENT_TYPES = {".js": "text/javascript", ".css": "text/css"}
TOKEN_PLACEHOLDER = "__CSRF_TOKEN__"


def _find_assets(folder: Traversable, prefix: str = "") -> dict[str, Traversable]:
    """Every .js and .css file in the dashboard folder, by URL path (such as "js/main.js")."""
    found: dict[str, Traversable] = {}
    for item in folder.iterdir():
        if item.is_dir():
            found |= _find_assets(item, f"{prefix}{item.name}/")
        elif any(item.name.endswith(ext) for ext in CONTENT_TYPES):
            found[prefix + item.name] = item
    return found


# Built once at startup. Only these exact paths are served, so there is no directory listing and
# nothing outside this folder can be asked for.
ASSETS = _find_assets(resources.files("app.dashboard"))


def _read(name: str) -> str:
    return (resources.files("app.dashboard") / name).read_text(encoding="utf-8")


@router.get("/")
def index(request: Request) -> Response:
    html = _read("index.html").replace(TOKEN_PLACEHOLDER, request.app.state.csrf_token)
    headers = {**SECURITY_HEADERS, "Cache-Control": "no-store"}
    return Response(html, media_type="text/html; charset=utf-8", headers=headers)


@router.get("/static/{name:path}")
def asset(name: str) -> Response:
    file = ASSETS.get(name)
    if file is None:
        raise not_found("page")
    media_type = CONTENT_TYPES[PurePosixPath(name).suffix]
    headers = {**SECURITY_HEADERS, "Cache-Control": "no-cache"}
    return Response(file.read_text(encoding="utf-8"), media_type=media_type, headers=headers)


@router.get("/api/local/csrf-token")
def csrf_token(request: Request) -> JSONResponse:
    """For the helper scripts, which have no page to read the token from. Loopback + Host
    checked like every dashboard route, and no CORS headers, so other websites can't read it."""
    return JSONResponse(
        {"token": request.app.state.csrf_token}, headers={"Cache-Control": "no-store"}
    )
