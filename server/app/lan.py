"""This computer's home-network address, for the pairing QR and the ``Host`` allowlist."""

import ipaddress
import socket

from app.network import is_loopback_address, is_private_address

# A documentation address (RFC 5737). Connecting a UDP socket to it sends nothing; it only makes
# the operating system pick the network card it would use, which tells us our own address.
_PROBE_ADDRESS = ("192.0.2.1", 9)


def detect_lan_ip() -> str | None:
    """The computer's home-network IPv4 address, or None if it isn't on a home network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(_PROBE_ADDRESS)
            found = probe.getsockname()[0]
    except OSError:
        return None
    if is_private_address(found) and not is_loopback_address(found):
        return found
    return None


def host_header(ip: str, port: int) -> str:
    """The ``Host`` header value a phone sends for this address (IPv6 goes in brackets)."""
    if ipaddress.ip_address(ip).version == 6:
        return f"[{ip}]:{port}"
    return f"{ip}:{port}"


class LanAddress:
    """The address phones use to reach this computer. Shared by the QR and the Host check."""

    def __init__(self, ip: str | None, *, pinned: bool) -> None:
        self.ip = ip
        self._pinned = pinned  # set by the user (BUDGET_BUDDY_LAN_IP), so never re-detected

    def refresh(self) -> str | None:
        if not self._pinned:
            self.ip = detect_lan_ip() or self.ip
        return self.ip
