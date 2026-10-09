"""Building a ready-to-run Home Base: the app, its listeners, and the uvicorn server.

Shared by ``python -m app`` (a console window) and the desktop app (a background thread), so both
start the Home Base the same way.
"""

import uvicorn

from app import instance_proof
from app.config import Settings
from app.logs import log_config
from app.main import create_app


class HomeBaseServer(uvicorn.Server):
    """uvicorn's server, plus the running file the desktop app checks (``app/instance_proof.py``).

    It's written only once the port is really ours: uvicorn runs the app's start-up before it
    binds, so a second copy started by mistake (which can't bind) must not replace or remove the
    running copy's file.
    """

    def __init__(self, config: uvicorn.Config, settings: Settings, key: str) -> None:
        super().__init__(config)
        self._settings, self._key, self._wrote = settings, key, False

    async def startup(self, sockets=None) -> None:
        await super().startup(sockets)
        if self.started:  # bound and serving (a failed bind exits before this)
            instance_proof.write(self._settings.data_dir, self._settings.port, self._key)
            self._wrote = True

    async def shutdown(self, sockets=None) -> None:
        if self._wrote:
            instance_proof.remove(self._settings.data_dir, self._key)
        await super().shutdown(sockets)


def build_server(settings: Settings) -> uvicorn.Server:
    app = create_app(settings)
    # The main server answers this computer only (unless BUDGET_BUDDY_HOST says otherwise). The
    # home-network listener is opened separately, on this computer's own address, while pairing
    # or once a phone is paired (app/listeners.py).
    app.state.listener.attach()
    app.state.listener.sync_from_database()
    # proxy_headers=False: never trust X-Forwarded-For, so the private-network check
    # always sees the real client address. log_config: access logs leave out query strings.
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        proxy_headers=False,
        log_config=log_config(),
    )
    return HomeBaseServer(config, settings, app.state.instance_key)


def local_url(settings: Settings) -> str:
    return f"http://127.0.0.1:{settings.port}"
