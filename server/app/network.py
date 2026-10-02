"""Only answer requests coming from this computer or the home network (see ADR-0002)."""

import ipaddress

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


async def private_network_only(request: Request, call_next) -> Response:
    """HTTP middleware: reject anyone outside the home network with 403."""
    client_host = request.client.host if request.client else None
    if not is_private_address(client_host):
        return JSONResponse(
            status_code=403,
            content={"detail": "Budget Buddy only answers devices on your home network."},
        )
    return await call_next(request)
