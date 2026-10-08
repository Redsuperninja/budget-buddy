"""Other computers on the home network (ADR-0009).

``/api/local/remote-computers/...`` makes join codes and lists or removes computers: this computer
only (``app.remote_access`` keeps joined computers out of them). ``/api/remote/join`` is where
another computer spends a code and gets its cookie. Codes and tokens are never logged.
"""

from fastapi import APIRouter, Request, Response, status

from app.deps import PathId, SessionDep
from app.errors import ApiError
from app.lan import host_header
from app.schemas.remote_computers import ComputerOut, JoinCode, Joined, JoinRequest
from app.services import remote_computers as service

router = APIRouter(tags=["remote computers"])

NO_NETWORK_MESSAGE = (
    "Budget Buddy can't find your home network. Connect this computer to your home Wi-Fi or "
    "network, then try again."
)
TOO_MANY_MESSAGE = "Too many tries. Wait a minute, then try again."


@router.post("/api/local/remote-computers/join-code")
def new_join_code(request: Request, response: Response) -> JoinCode:
    """A code that lets one more computer join, once, for 10 minutes."""
    state = request.app.state
    ip = state.lan.refresh()
    if ip is None:
        raise ApiError(409, "no_home_network", NO_NETWORK_MESSAGE)
    code, expires_at = state.join_codes.new(state.clock())
    response.headers["Cache-Control"] = "no-store"
    state.listener.sync(True, ip)
    return JoinCode(
        code=f"{code[:4]}-{code[4:]}",
        address=f"http://{host_header(ip, state.settings.port)}/",
        expires_at=expires_at,
        seconds_valid=service.CODE_TTL_SECONDS,
        can_connect=state.listener.reachable(),
        message=state.listener.unreachable_reason(),
    )


@router.get("/api/local/remote-computers")
def list_computers(request: Request, session: SessionDep) -> list[ComputerOut]:
    request.app.state.listener.sync_from_database()  # closes the listener once nothing needs it
    return service.list_computers(session)


@router.post(
    "/api/local/remote-computers/{computer_id}/remove", status_code=status.HTTP_204_NO_CONTENT
)
def remove_computer(request: Request, computer_id: PathId, session: SessionDep) -> None:
    """It stops working at once."""
    service.remove(session, computer_id)
    request.app.state.listener.sync_from_database()


@router.post("/api/remote/join")
def join(data: JoinRequest, request: Request, response: Response, session: SessionDep) -> Joined:
    state = request.app.state
    client = request.client.host if request.client else "unknown"
    if not state.join_limiter.allow(client, state.clock()):
        raise ApiError(429, "too_many_tries", TOO_MANY_MESSAGE)
    token = service.join(session, state.join_codes, data.code, data.name, state.clock())
    response.set_cookie(
        service.COOKIE_NAME,
        token,
        max_age=service.COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return Joined(name=data.name)
