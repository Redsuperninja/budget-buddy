"""Only answer requests coming from this computer or the home network (see ADR-0002)."""

import hmac
import ipaddress
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.remote_access import JOIN_PATH, TOKEN_OK

ALLOWED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "127.0.0.0/8",  # IPv4 loopback
        "10.0.0.0/8",  # RFC1918
        "172.16.0.0/12",  # RFC1918
        "192.168.0.0/16",  # RFC1918
        "169.254.0.0/16",  # IPv4 link-local
        "::1/128",  # IPv6 loopback
        "fc00::/7",  # IPv6 unique local (ULA)
        "fe80::/10",  # IPv6 link-local
    )
)

FORBIDDEN_DETAIL = "Budget Buddy only answers devices on your home network."

# WebSocket close code 1008 = "policy violation". Closing before accepting makes the server
# answer the WebSocket handshake with HTTP 403.
WS_POLICY_VIOLATION = 1008


def is_private_address(host: str | None) -> bool:
    """True if ``host`` is a loopback, private (RFC1918/ULA) or link-local IP address."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in net for net in ALLOWED_NETWORKS if net.version == ip.version)


def is_loopback_address(host: str | None) -> bool:
    """True only for this computer: ``127.0.0.0/8`` or ``::1`` (including IPv4-mapped forms)."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


# Added to every HTTP response, including refusals: stops browsers guessing file types and keeps
# other websites from embedding our responses.
ALWAYS_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"cross-origin-resource-policy", b"same-origin"),
)


# API replies hold financial data: no browser (or the desktop app's window) may keep a copy on disk.
API_HEADERS = ((b"cache-control", b"no-store"),)


def _with_always_headers(send: Send, path: str) -> Send:
    extra = ALWAYS_HEADERS + (API_HEADERS if path.startswith("/api/") else ())

    async def wrapped(message):
        if message["type"] == "http.response.start":
            headers = list(message.get("headers", []))
            present = {k.lower() for k, _ in headers}
            headers += [(k, v) for k, v in extra if k not in present]
            message = {**message, "headers": headers}
        await send(message)

    return wrapped


class PrivateNetworkOnlyMiddleware:
    """ASGI middleware: reject anyone outside the home network.

    HTTP requests get a 403 response; WebSocket connections are closed with code 1008
    before they are accepted. Other scope types (such as ``lifespan``) pass straight through.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            # Outermost middleware: covers every response.
            send = _with_always_headers(send, scope.get("path", ""))

        client = scope.get("client")
        if is_private_address(client[0] if client else None):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": WS_POLICY_VIOLATION})
            return

        response = JSONResponse(
            status_code=403,
            content={"error": {"code": "not_home_network", "message": FORBIDDEN_DETAIL}},
        )
        await response(scope, receive, send)


def allowed_hosts(port: int) -> frozenset[str]:
    """The ``Host`` header values we answer to (sync contract §3.1).

    Only this computer's own names. A DNS-rebinding page in the browser sends its own hostname
    here, so it gets refused. The computer's own home-network address is added separately
    (see ``LocalAccessMiddleware``'s ``lan_host``).
    """
    return frozenset({f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"})


def allowed_origins(port: int) -> frozenset[str]:
    """The ``Origin`` values a dashboard page on this computer sends (sync contract §3.1)."""
    return frozenset(f"http://{host}" for host in allowed_hosts(port))


# The only routes the phone needs over Wi-Fi (sync contract §3.1). Everything else is for this
# computer only.
LAN_ROUTES = ("/api/health", "/api/pair")
LAN_ROUTE_PREFIXES = ("/api/sync/",)

# Reading is safe to allow without an Origin; anything else changes data.
SAFE_METHODS = frozenset({"GET", "HEAD"})


def is_lan_route(path: str) -> bool:
    """True for the few routes a paired phone may call from the home network."""
    return path in LAN_ROUTES or path.startswith(LAN_ROUTE_PREFIXES)


def _header(scope: Scope, name: bytes) -> str | None:
    """The value of a request header, or None if it's missing or sent more than once."""
    values = [v for k, v in scope.get("headers", []) if k.lower() == name]
    if len(values) != 1:
        return None
    return values[0].decode("latin-1")


class LocalAccessMiddleware:
    """ASGI middleware for the sync contract §3.1 rules that apply on top of the network check.

    - Every request must name this computer in its ``Host`` header, else 403 ``bad_host``.
    - Deny by default: only the phone's routes (``is_lan_route``) answer the home network. Every
      other route answers this computer only (socket peer is loopback; proxy headers such as
      ``X-Forwarded-For`` are never trusted), else 403 ``not_this_computer``. New routes are
      protected without anyone having to remember a dependency.
    - Requests that change data on a dashboard route (anything but GET/HEAD) must come from a
      page on this computer: ``Origin`` must be present and match, and ``X-CSRF-Token`` must carry
      this run's token (compared in constant time), else 403 ``bad_origin``. This stops other
      websites from submitting forms or ``fetch`` calls to the Home Base (CSRF).
    """

    def __init__(
        self,
        app: ASGIApp,
        port: int,
        lan_host: Callable[[], str | None] | None = None,
        csrf_token: Callable[[], str] | None = None,
        remote=None,
    ) -> None:
        self.app = app
        self.hosts = allowed_hosts(port)
        self.origins = allowed_origins(port)
        # The computer's home-network ``ip:port``, which phones put in ``Host`` (§3.1). Asked on
        # each request because the address is detected or changed while the app runs.
        self.lan_host = lan_host or (lambda: None)
        # The per-run CSRF token the dashboard page sends back on every write. No token means
        # no dashboard write can ever pass.
        self.csrf_token = csrf_token or (lambda: "")
        # Other computers on the home network (``app.remote_access.RemoteAccess``, ADR-0009).
        # None: this computer only.
        self.remote = remote

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        host = _header(scope, b"host")
        if host is None or (host.lower() not in self.hosts and host.lower() != self.lan_host()):
            await _refuse(scope, receive, send, "bad_host", BAD_HOST_MESSAGE)
            return

        if is_lan_route(scope["path"]):
            await self.app(scope, receive, send)
            return

        origins = self.origins
        client = scope.get("client")
        if not is_loopback_address(client[0] if client else None):
            lan_host = self.lan_host()
            refusal = (
                await self.remote.refusal(scope, host.lower(), lan_host)
                if self.remote is not None
                else ("not_this_computer", NOT_THIS_COMPUTER_MESSAGE)
            )
            if refusal is not None:
                await _refuse(scope, receive, send, *refusal)
                return
            origins = frozenset({f"http://{lan_host}"})
        else:
            scope.setdefault("state", {})[TOKEN_OK] = True  # this computer

        if scope.get("method", "GET") not in SAFE_METHODS:
            origin = _header(scope, b"origin")
            if origin is None or origin.lower() not in origins:
                await _refuse(scope, receive, send, "bad_origin", BAD_ORIGIN_MESSAGE)
                return
            sent = _header(scope, b"x-csrf-token") or ""
            expected = self.csrf_token()
            # Joining is the one write with no token yet: the page only gets one after joining.
            joining = scope["path"] == JOIN_PATH
            if not joining and (
                not expected or not hmac.compare_digest(sent.encode(), expected.encode())
            ):
                await _refuse(scope, receive, send, "bad_origin", BAD_ORIGIN_MESSAGE)
                return

        await self.app(scope, receive, send)


BAD_HOST_MESSAGE = (
    "Budget Buddy only answers when it's opened as http://127.0.0.1 or http://localhost "
    "on this computer."
)


NOT_THIS_COMPUTER_MESSAGE = "This only works on the computer where Budget Buddy is running."
BAD_ORIGIN_MESSAGE = "Changes can only be made from the Budget Buddy page on this computer."


async def _refuse(scope: Scope, receive: Receive, send: Send, code: str, message: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": WS_POLICY_VIOLATION})
        return
    response = JSONResponse(status_code=403, content={"error": {"code": code, "message": message}})
    await response(scope, receive, send)
