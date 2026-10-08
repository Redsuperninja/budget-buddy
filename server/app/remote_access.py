"""Which requests another computer on the home network may make (ADR-0009).

``LocalAccessMiddleware`` asks ``RemoteAccess.refusal`` about every request that isn't from this
computer and isn't a phone route. Without a valid ``bb_computer`` cookie a computer only gets the
page, its files and the join route; with one it gets the dashboard API too, except the routes that
let more devices in. Writes are then checked like the local page's (``Origin`` and CSRF token), with
the home-network address as the only allowed origin.
"""

from collections.abc import Callable
from http.cookies import CookieError, SimpleCookie

from starlette.types import Scope

from app.services.remote_computers import COOKIE_NAME

JOIN_PATH = "/api/remote/join"
_PAGE_PATHS = ("/",)
_PAGE_PREFIXES = ("/static/",)
# Letting more devices in, or the helper scripts' token: only on the Budget Buddy computer itself.
LOCAL_ONLY_PREFIXES = (
    "/api/local/pairing",
    "/api/local/devices",
    "/api/local/remote-computers",
    "/api/local/csrf-token",
)

NOT_JOINED_MESSAGE = (
    "This computer isn't connected to Budget Buddy yet. Open the Budget Buddy page and enter the "
    "code shown on the Budget Buddy computer."
)
LOCAL_ONLY_MESSAGE = "This can only be done on the computer where Budget Buddy is running."


def cookie_token(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"cookie":
            try:
                jar = SimpleCookie(value.decode("latin-1"))
            except CookieError:
                return None
            morsel = jar.get(COOKIE_NAME)
            return morsel.value if morsel else None
    return None


class RemoteAccess:
    def __init__(self, signed_in: Callable[[str | None], bool]) -> None:
        # Checks a cookie token against the joined computers (the database).
        self.signed_in = signed_in

    def refusal(self, scope: Scope, host: str, lan_host: str | None) -> tuple[str, str] | None:
        """None if a home-network computer may make this request, else (code, message).

        Also records in ``scope["state"]`` whether it has joined, so the page knows whether to
        carry the CSRF token.
        """
        if lan_host is None or host != lan_host:
            return "not_this_computer", NOT_JOINED_MESSAGE
        path, method = scope["path"], scope.get("method", "GET")
        joined = self.signed_in(cookie_token(scope))
        scope.setdefault("state", {})["remote_signed_in"] = joined
        if method in ("GET", "HEAD") and (path in _PAGE_PATHS or path.startswith(_PAGE_PREFIXES)):
            return None
        if path == JOIN_PATH:
            return None
        if not joined:
            return "not_this_computer", NOT_JOINED_MESSAGE
        if path.startswith(LOCAL_ONLY_PREFIXES):
            return "not_this_computer", LOCAL_ONLY_MESSAGE
        return None
