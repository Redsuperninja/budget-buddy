import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app import __version__
from app.config import Settings
from app.crypto import FieldCipher, load_keys
from app.db import create_db_engine, run_migrations
from app.errors import install_error_handlers
from app.network import LocalAccessMiddleware, PrivateNetworkOnlyMiddleware
from app.routers import accounts, csv_import, health, transactions


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
    """Build the FastAPI app.

    Creates the data folder and database if needed and brings the database up to date, so
    nobody ever has to run migrations by hand. Loads the encryption key (creating it on first
    run) before touching the database.
    """
    settings = settings or Settings()
    ensure_data_dir(settings.data_dir)
    keys = load_keys(settings)
    engine = create_db_engine(settings.data_dir, field_cipher=FieldCipher(keys.db_fields))
    run_migrations(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    # The API explorer pages list every endpoint, so they're only on in dev mode.
    docs = {} if settings.dev_mode else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Budget Buddy Home Base", version=__version__, lifespan=lifespan, **docs)
    app.state.settings = settings
    app.state.engine = engine
    app.state.keys = keys  # derived keys only (fields, files, backup); never the master key
    # Middleware added last runs first: the home-network check, then the Host rules.
    app.add_middleware(LocalAccessMiddleware, port=settings.port)
    app.add_middleware(PrivateNetworkOnlyMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(csv_import.router)
    return app
