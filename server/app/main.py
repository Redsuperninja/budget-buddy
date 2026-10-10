import os
import secrets
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app import __version__, instance_proof
from app.config import Settings
from app.crypto import EncryptedFileStore, FieldCipher, load_keys
from app.dashboard_files import default_dashboard_dir, load_dashboard
from app.data_folder import warn_if_risky_data_dir
from app.db import create_db_engine, run_migrations
from app.errors import install_error_handlers
from app.lan import LanAddress, detect_lan_ip, host_header
from app.listeners import LanListener
from app.network import LocalAccessMiddleware, PrivateNetworkOnlyMiddleware
from app.ratelimit import RateLimiter
from app.remote_access import RemoteAccess
from app.routers import (
    accounts,
    activity_import,
    budget_plan,
    categories,
    category_rules,
    csv_import,
    dashboard,
    deductions,
    dividends,
    donations,
    health,
    imports,
    instance,
    pair,
    pairing,
    paychecks,
    positions,
    price_feed,
    receipts,
    remote_computers,
    retirement,
    stock_import,
    stocks,
    summary,
    sync,
    tax_summary,
    transactions,
)
from app.services.pairing_sessions import load_server_id, purge_ended_sessions
from app.services.receipts import remove_orphan_files
from app.services.remote_computers import JoinCodes, authenticate


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
    warn_if_risky_data_dir(settings.data_dir)
    keys = load_keys(settings)
    engine = create_db_engine(settings.data_dir, field_cipher=FieldCipher(keys.db_fields))
    run_migrations(engine)
    receipt_store = EncryptedFileStore.for_receipts(settings.data_dir, keys.files)
    remove_orphan_files(engine, receipt_store)  # leftovers from a crash; see services/receipts

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        with Session(engine) as session:
            purge_ended_sessions(session, app.state.clock())  # erase keys of old QR codes
        yield
        app.state.listener.close()
        engine.dispose()

    # The API explorer pages list every endpoint, so they're only on in dev mode.
    docs = {} if settings.dev_mode else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Budget Buddy Home Base", version=__version__, lifespan=lifespan, **docs)
    app.state.settings = settings
    app.state.engine = engine
    app.state.clock = lambda: int(time.time())  # Unix seconds; tests replace it
    app.state.server_id = load_server_id(settings.data_dir)
    app.state.lan = LanAddress(settings.lan_ip or detect_lan_ip(), pinned=bool(settings.lan_ip))
    app.state.pair_limiter = RateLimiter(limit=10, window_seconds=60)  # per address, §2.3
    app.state.dashboard = load_dashboard(settings.dashboard_dir or default_dashboard_dir())
    app.state.csrf_token = secrets.token_urlsafe(32)  # per run; the dashboard sends it on writes
    app.state.instance_key = instance_proof.new_key()  # see app/instance_proof.py
    app.state.listener = LanListener(app, settings)  # opened by ``python -m app`` only
    app.state.keys = keys  # derived keys only (fields, files, backup); never the master key
    app.state.receipt_store = receipt_store
    app.state.join_codes = JoinCodes()  # other computers' one-time codes, memory only (ADR-0009)
    app.state.join_limiter = RateLimiter(limit=10, window_seconds=60)  # per address

    def signed_in(token: str | None, address: str | None) -> bool:
        with Session(engine) as session:
            return authenticate(session, token, address)

    # Middleware added last runs first: the home-network check, then the Host rules.
    app.add_middleware(
        LocalAccessMiddleware,
        port=settings.port,
        lan_host=lambda: host_header(app.state.lan.ip, settings.port) if app.state.lan.ip else None,
        csrf_token=lambda: app.state.csrf_token,
        remote=RemoteAccess(signed_in),
    )
    app.add_middleware(PrivateNetworkOnlyMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(pair.router)
    app.include_router(sync.router)
    app.include_router(pairing.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(categories.router)
    app.include_router(budget_plan.router)
    app.include_router(category_rules.router)
    app.include_router(summary.router)
    app.include_router(csv_import.router)
    app.include_router(activity_import.router)
    app.include_router(imports.router)
    app.include_router(paychecks.router)
    app.include_router(receipts.router)
    app.include_router(donations.router)
    app.include_router(dividends.router)
    app.include_router(deductions.router)
    app.include_router(tax_summary.router)
    app.include_router(stock_import.router)
    app.include_router(positions.router)
    app.include_router(stocks.router)
    app.include_router(retirement.router)
    app.include_router(price_feed.router)
    app.include_router(remote_computers.router)
    app.include_router(instance.router)
    app.include_router(dashboard.router)
    return app
