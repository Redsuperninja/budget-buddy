import os
import sys
from pathlib import Path

from fastapi import FastAPI

from app import __version__
from app.config import Settings
from app.network import PrivateNetworkOnlyMiddleware
from app.routers import health


def ensure_data_dir(path: Path) -> None:
    """Create the data folder so only the current user can open it (macOS/Linux).

    On Windows, POSIX permission bits don't apply; the default location is inside the
    user's own profile, so we just create the folder.
    """
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if sys.platform != "win32":
        # mkdir's mode is reduced by the umask and ignored if the folder already exists.
        os.chmod(path, 0o700)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app. Creates the data folder if it doesn't exist yet."""
    settings = settings or Settings()
    ensure_data_dir(settings.data_dir)

    # The API explorer pages list every endpoint, so they're only on in dev mode.
    docs = {} if settings.dev_mode else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Budget Buddy Home Base", version=__version__, **docs)
    app.state.settings = settings
    app.add_middleware(PrivateNetworkOnlyMiddleware)
    app.include_router(health.router)
    return app
