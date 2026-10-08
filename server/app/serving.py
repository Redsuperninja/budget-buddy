"""Building a ready-to-run Home Base: the app, its listeners, and the uvicorn server.

Shared by ``python -m app`` (a console window) and the desktop app (a background thread), so both
start the Home Base the same way.
"""

import uvicorn

from app.config import Settings
from app.logs import log_config
from app.main import create_app


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
    return uvicorn.Server(config)


def local_url(settings: Settings) -> str:
    return f"http://127.0.0.1:{settings.port}"
