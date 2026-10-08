"""The home-network listener (sync contract §3.1).

The main server stays on this computer only (``127.0.0.1``). While a pairing is in progress, or
once at least one phone is paired, a second listener is opened on this computer's own home-network
address (never ``0.0.0.0``). When neither is true it is closed again.

``BUDGET_BUDDY_HOST`` set explicitly wins: an explicit loopback address means "never open the
network" and any other explicit address means the main server already listens there.
"""

import logging
import threading
from collections.abc import Callable

import uvicorn
from sqlalchemy.orm import Session

from app.config import Settings
from app.network import is_loopback_address


def _is_loopback_setting(host: str) -> bool:
    """Loopback by address (127.0.0.1, ::1) or by the name ``localhost`` in any case."""
    return host.strip().lower().rstrip(".") == "localhost" or is_loopback_address(host)


logger = logging.getLogger(__name__)

START_TIMEOUT_SECONDS = 5.0

NEVER_MESSAGE = (
    "Budget Buddy was set to answer only on this computer, so phones can't connect. Remove the "
    "BUDGET_BUDDY_HOST setting and restart Budget Buddy to pair a phone."
)
NOT_RUNNING_MESSAGE = (
    "Budget Buddy isn't set up to talk to phones in this mode. Start it with `python -m app` and "
    "try again."
)
FAILED_MESSAGE = (
    "Budget Buddy couldn't open its home-network connection. Check that this computer is on your "
    "home Wi-Fi and that nothing else is using port {port}, then try again."
)


def _uvicorn_server(app, host: str, port: int):
    from app.logs import log_config

    # proxy_headers=False: never trust X-Forwarded-For (see __main__).
    # lifespan="off": this is a second listener on the same app. The app's own startup and
    # shutdown (database, listener.close()) belong to the main server only.
    config = uvicorn.Config(
        app, host=host, port=port, proxy_headers=False, log_config=log_config(), lifespan="off"
    )
    return uvicorn.Server(config)


class LanListener:
    """Opens and closes the second, home-network listener. Needs ``attach()`` to do anything,
    which only ``python -m app`` calls, so tests and other launchers never open sockets."""

    def __init__(self, app, settings: Settings, make_server: Callable | None = None) -> None:
        self._app = app
        self._settings = settings
        self._make_server = make_server or _uvicorn_server
        self._attached = False
        self._lock = threading.Lock()
        self._server = None
        self._thread: threading.Thread | None = None
        self.bound_ip: str | None = None
        self.failed = False

    def attach(self) -> None:
        self._attached = True

    # -- what the settings say ------------------------------------------------------------

    @property
    def _explicit_host(self) -> bool:
        return "host" in self._settings.model_fields_set

    @property
    def never(self) -> bool:
        return self._explicit_host and _is_loopback_setting(self._settings.host)

    @property
    def main_is_on_network(self) -> bool:
        return self._explicit_host and not _is_loopback_setting(self._settings.host)

    # -- state ---------------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self.bound_ip is not None

    def reachable(self) -> bool:
        """True if a phone on the home network can connect right now."""
        return self.main_is_on_network or self.running

    def unreachable_reason(self) -> str | None:
        if self.reachable():
            return None
        if self.never:
            return NEVER_MESSAGE
        if self.failed:
            return FAILED_MESSAGE.format(port=self._settings.port)
        return NOT_RUNNING_MESSAGE

    # -- open / close --------------------------------------------------------------------

    def sync(self, wanted: bool, ip: str | None) -> None:
        """Open the listener on ``ip`` if ``wanted``, otherwise close it."""
        with self._lock:
            if self.main_is_on_network:
                return
            if not wanted or ip is None or not self._attached or self.never:
                self._stop()
                return
            if self.running and self.bound_ip == ip:
                return
            self._stop()
            self._start(ip)

    def sync_from_database(self) -> None:
        """Re-check whether the listener is wanted: a live pairing or join code, a paired phone,
        or a joined computer."""
        from app.services.pairing_sessions import lan_wanted
        from app.services.remote_computers import network_wanted

        state = self._app.state
        now = state.clock()
        with Session(state.engine) as session:
            wanted = lan_wanted(session, now) or network_wanted(session, state.join_codes, now)
        self.sync(wanted, state.lan.refresh() if wanted else state.lan.ip)

    def _start(self, ip: str) -> None:
        self.failed = False
        try:
            server = self._make_server(self._app, ip, self._settings.port)
        except Exception:
            logger.warning("Budget Buddy couldn't open its home-network connection.")
            self.failed = True
            return
        thread = threading.Thread(target=server.run, name="lan-listener", daemon=True)
        thread.start()
        waited = 0.0
        while not getattr(server, "started", False) and thread.is_alive():
            if waited >= START_TIMEOUT_SECONDS:
                break
            thread.join(0.05)
            waited += 0.05
        if not getattr(server, "started", False):
            server.should_exit = True
            self.failed = True
            logger.warning("Budget Buddy couldn't open its home-network connection.")
            return
        self._server, self._thread, self.bound_ip = server, thread, ip

    def _stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = self._thread = self.bound_ip = None
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)

    def close(self) -> None:
        with self._lock:
            self._stop()
