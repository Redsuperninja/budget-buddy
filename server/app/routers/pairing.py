"""This-computer-only routes for pairing phones (the dashboard's "Pair a phone" and device list).

Every route here is loopback-only by default (``LocalAccessMiddleware``). Responses carrying the
pairing code are ``no-store`` and the code never goes in a URL or a log.
"""

import json

from fastapi import APIRouter, Request, Response

from app.deps import PathId, SessionDep
from app.errors import ApiError
from app.schemas.pairing import DeviceOut, PairingStarted
from app.services import devices as device_service
from app.services import pairing as service

# Note: the per-session CSRF token of contract §3.1 comes with the dashboard (#16); until then the
# Origin check in LocalAccessMiddleware is what protects these routes.
router = APIRouter(prefix="/api/local", tags=["pairing"])

NO_NETWORK_MESSAGE = (
    "Budget Buddy can't find your home network. Connect this computer to your home Wi-Fi, "
    "then try again."
)


@router.post("/pairing")
def start_pairing(request: Request, response: Response, session: SessionDep) -> PairingStarted:
    """Start pairing: a new QR code (and the same thing as text) that works once for 10 minutes."""
    state = request.app.state
    host = state.lan.refresh()
    if host is None:
        raise ApiError(409, "no_home_network", NO_NETWORK_MESSAGE)
    settings = state.settings
    payload = service.start_session(
        session,
        now=state.clock(),
        host=host,
        port=settings.port,
        server_id=state.server_id,
        server_name=settings.server_name,
    )
    response.headers["Cache-Control"] = "no-store"
    listener = state.listener
    listener.sync(True, host)  # a live pairing: open the home-network listener
    reachable = listener.reachable()
    return PairingStarted(
        payload=payload,
        payload_text=json.dumps(payload, separators=(",", ":")),
        expires_at=payload["exp"],
        seconds_valid=service.CODE_TTL_SECONDS,
        phone_can_connect=reachable,
        message=listener.unreachable_reason(),
    )


@router.get("/devices")
def list_devices(request: Request, session: SessionDep) -> list[DeviceOut]:
    """Paired phones, newest first, including removed ones (so "New phone paired" can be shown)."""
    service.purge_ended_sessions(session, request.app.state.clock())
    request.app.state.listener.sync_from_database()  # closes the listener once nothing needs it
    return device_service.list_devices(session)


@router.post("/devices/{device_id}/revoke")
def revoke_device(request: Request, device_id: PathId, session: SessionDep) -> DeviceOut:
    """Remove a phone. It stops working immediately."""
    device = device_service.revoke_device(session, device_id)
    request.app.state.listener.sync_from_database()
    return device
