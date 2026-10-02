from fastapi import APIRouter

from app import __version__

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Simple "is Budget Buddy running?" check."""
    return {"status": "ok", "version": __version__}
