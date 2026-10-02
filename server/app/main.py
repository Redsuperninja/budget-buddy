from fastapi import FastAPI

from app import __version__
from app.config import Settings
from app.network import private_network_only
from app.routers import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app. Creates the data folder if it doesn't exist yet."""
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Budget Buddy Home Base", version=__version__)
    app.state.settings = settings
    app.middleware("http")(private_network_only)
    app.include_router(health.router)
    return app
