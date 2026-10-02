"""Only answer requests coming from this computer or the home network (see ADR-0002)."""

import ipaddress

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

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

        client = scope.get("client")
        if is_private_address(client[0] if client else None):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": WS_POLICY_VIOLATION})
            return

        response = JSONResponse(status_code=403, content={"detail": FORBIDDEN_DETAIL})
        await response(scope, receive, send)
