"""Which requests another computer on the home network may make (ADR-0009).

``LocalAccessMiddleware`` asks ``RemoteAccess.refusal`` about every request that isn't from this
computer and isn't a phone route. Without a valid ``bb_computer`` cookie (used from the address
that joined) a computer only gets the page, its files and the join route. With one it gets the
dashboard routes on an **allow-list**, so a new route stays this-computer-only until someone
decides otherwise; letting more devices in never is. Writes are then checked like the local page's
(``Origin`` and CSRF token), with the home-network address as the only allowed origin.

Every request gets ``scope["state"]["dashboard_token_ok"]``: only this computer and joined
computers get a page carrying the CSRF token.
"""

from collections.abc import Callable

import anyio
from starlette.requests import cookie_parser
from starlette.types import Scope

from app.services.remote_computers import COOKIE_NAME

JOIN_PATH = "/api/remote/join"
TOKEN_OK = "dashboard_token_ok"
_PAGE_PATHS = ("/",)
_PAGE_PREFIXES = ("/static/",)
# The dashboard areas a joined computer may use. Not here, so this computer only: pairing phones,
# devices, other computers, the scripts' CSRF token, and anything added later.
JOINED_AREAS = frozenset(
    {
        "accounts",
        "budget",
        "categories",
        "category-rules",
        "deductions",
        "dividends",
        "donations",
        "paychecks",
        "receipts",
        "retirement",
        "stocks",
        "summary",
        "tax-summary",
        "transactions",
    }
)

NOT_JOINED_MESSAGE = (
    "This computer isn't connected to Budget Buddy yet. Open the Budget Buddy page and enter the "
    "code shown on the Budget Buddy computer."
)
LOCAL_ONLY_MESSAGE = "This can only be done on the computer where Budget Buddy is running."


def joined_may_use(path: str) -> bool:
    """True for ``/api/local/<area>`` and below, for an area on the allow-list."""
    parts = path.split("/")
    return len(parts) >= 4 and parts[1:3] == ["api", "local"] and parts[3] in JOINED_AREAS


def cookie_token(scope: Scope) -> str | None:
    """Our cookie, read leniently: a bad cookie from another app on this address is skipped."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"cookie":
            token = cookie_parser(value.decode("latin-1")).get(COOKIE_NAME)
            if token:
                return token
    return None


class RemoteAccess:
    def __init__(self, signed_in: Callable[[str | None, str | None], bool]) -> None:
        # Checks a cookie token and the address using it against the joined computers (database).
        self.signed_in = signed_in

    async def refusal(
        self, scope: Scope, host: str, lan_host: str | None
    ) -> tuple[str, str] | None:
        """None if a home-network computer may make this request, else (code, message)."""
        if lan_host is None or host != lan_host:
            return "not_this_computer", NOT_JOINED_MESSAGE
        path, method = scope["path"], scope.get("method", "GET")
        client = scope.get("client")
        # Off the event loop: the check reads (and now and then writes) the database.
        joined = await anyio.to_thread.run_sync(
            self.signed_in, cookie_token(scope), client[0] if client else None
        )
        scope.setdefault("state", {})[TOKEN_OK] = joined
        if method in ("GET", "HEAD") and (path in _PAGE_PATHS or path.startswith(_PAGE_PREFIXES)):
            return None
        if path == JOIN_PATH:
            return None
        if not joined:
            return "not_this_computer", NOT_JOINED_MESSAGE
        if not joined_may_use(path):
            return "not_this_computer", LOCAL_ONLY_MESSAGE
        return None
