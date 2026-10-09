"""Live stock prices from Finnhub, only when you turn it on (ADR-0010).

The only time Budget Buddy talks to the internet. What's sent: the symbols you hold (like VTI), one
request each, to Finnhub's quote API over HTTPS, with your key in a header (never in the address,
so it can't end up in a log). Nothing else: no amounts, accounts or other data.

- Prices refresh when the Investments page asks (on opening it, and on Refresh), never on a
  timer. A symbol fetched in the last ``FRESH_SECONDS`` isn't asked for again.
- Finnhub's free plan allows 60 requests a minute; a refresh stops early on a limit, a key problem
  or no connection, and says so in plain English. Prices fetched so far are kept.
- A price is Finnhub's latest trade price (``c``), rounded half up to a cent, dated by its time.
"""

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PriceFeed, StockLot, StockPrice, StockSale
from app.schemas.price_feed import PriceFeedIn, PriceFeedOut, RefreshResult

QUOTE_URL = "https://finnhub.io/api/v1/quote"
TIMEOUT_SECONDS = 5
FRESH_SECONDS = 60
MAX_REPLY_BYTES = 4096
FEED = "feed"

OFF = "Live prices are off. Turn them on and add your Finnhub key on the Investments page."
NO_KEY = "Add your free Finnhub key on the Investments page to get live prices."
BAD_KEY = "Finnhub didn't accept your key. Check it on finnhub.io and paste it again."
LIMIT = "Finnhub's free limit was reached. Try again in a minute."
OFFLINE = "Couldn't reach Finnhub. Check your internet connection and try again."


class FeedStop(Exception):
    """Stop this refresh; the message is for people."""


def _feed(session: Session) -> PriceFeed:
    return session.get(PriceFeed, 1) or PriceFeed(id=1, enabled=False)


def settings(session: Session) -> PriceFeedOut:
    feed = _feed(session)
    return PriceFeedOut(enabled=feed.enabled, has_key=bool(feed.api_key))


def save_settings(session: Session, data: PriceFeedIn) -> PriceFeedOut:
    feed = _feed(session)
    feed.enabled = data.enabled
    if data.api_key is not None:
        feed.api_key = data.api_key or None  # an empty key removes it
    session.add(feed)
    session.commit()
    return settings(session)


def held_symbols(session: Session) -> list[str]:
    """Symbols with shares still held, in any account."""
    sold = (
        select(StockSale.lot_id, func.sum(StockSale.shares_micro).label("sold"))
        .group_by(StockSale.lot_id)
        .subquery()
    )
    rows = session.execute(
        select(StockLot.symbol)
        .outerjoin(sold, sold.c.lot_id == StockLot.id)
        .where(StockLot.shares_micro > func.coalesce(sold.c.sold, 0))
        .distinct()
        .order_by(StockLot.symbol)
    )
    return list(rows.scalars())


def _get_json(url: str, key: str) -> dict:
    """One HTTPS GET to Finnhub. The key goes in a header, not the address."""
    request = urllib.request.Request(url, headers={"X-Finnhub-Token": key})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:  # noqa: S310
            return json.loads(reply.read(MAX_REPLY_BYTES))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise FeedStop(BAD_KEY) from None
        if exc.code == 429:
            raise FeedStop(LIMIT) from None
        raise FeedStop(OFFLINE) from None
    except (OSError, ValueError):
        raise FeedStop(OFFLINE) from None


def quote(symbol: str, key: str) -> tuple[int, dt.date] | None:
    """The latest price in cents and its date, or None if Finnhub doesn't know the symbol."""
    data = _get_json(f"{QUOTE_URL}?{urllib.parse.urlencode({'symbol': symbol})}", key)
    try:
        price = Decimal(str(data.get("c") or 0))
        when = int(data.get("t") or 0)
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return None
    if price <= 0 or when <= 0:
        return None
    cents = int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return cents, dt.datetime.fromtimestamp(when, dt.UTC).date()


def refresh(session: Session, now: dt.datetime | None = None) -> RefreshResult:
    """Fetch the latest price of each symbol you hold that wasn't fetched in the last minute."""
    now = now or dt.datetime.now(dt.UTC).replace(tzinfo=None)
    feed = _feed(session)
    if not feed.enabled:
        return RefreshResult(updated=[], not_found=[], message=OFF)
    if not feed.api_key:
        return RefreshResult(updated=[], not_found=[], message=NO_KEY)
    updated, not_found, message = [], [], None
    for symbol in held_symbols(session):
        row = session.get(StockPrice, symbol)
        fresh = dt.timedelta(seconds=FRESH_SECONDS)
        if row and row.source == FEED and row.fetched_at and now - row.fetched_at < fresh:
            continue
        try:
            found = quote(symbol, feed.api_key)
        except FeedStop as stop:
            message = str(stop)
            break
        if found is None:
            not_found.append(symbol)
            continue
        row = row or StockPrice(symbol=symbol)
        row.price_cents, row.as_of = found
        row.source, row.fetched_at = FEED, now
        session.add(row)
        updated.append(symbol)
    session.commit()
    return RefreshResult(updated=updated, not_found=not_found, message=message)
