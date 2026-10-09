"""Live-price settings (ADR-0010): this computer only, like every setting that opens a connection
or lets something in (not on the joined computers' allow-list, ADR-0009). Refreshing prices is in
``routers/stocks.py`` and works from joined computers too."""

from fastapi import APIRouter

from app.deps import SessionDep
from app.schemas.price_feed import PriceFeedIn, PriceFeedOut
from app.services import price_feed

router = APIRouter(prefix="/api/local/price-feed", tags=["price feed"])


@router.get("")
def settings(session: SessionDep) -> PriceFeedOut:
    return price_feed.settings(session)


@router.put("")
def save(data: PriceFeedIn, session: SessionDep) -> PriceFeedOut:
    """Turn live prices on or off, and save or remove the Finnhub key (never sent back)."""
    return price_feed.save_settings(session, data)
