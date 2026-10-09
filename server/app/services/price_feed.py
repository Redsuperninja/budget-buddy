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
import ssl
import threading
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
MAX_SYMBOLS = 50  # per refresh, under Finnhub's free 60 a minute
MAX_PRICE = Decimal("1000000000")  # a billion dollars a share: anything above is a bad reply
FEED = "feed"
_RUNNING = threading.Lock()

OFF = "Live prices are off. Turn them on and add your Finnhub key on the Investments page."
NO_KEY = "Add your free Finnhub key on the Investments page to get live prices."
BAD_KEY = "Finnhub didn't accept your key. Check it on finnhub.io and paste it again."
LIMIT = "Finnhub's free limit was reached. Try again in a minute."
OFFLINE = "Couldn't reach Finnhub. Check your internet connection and try again."
BUSY = "Prices are already being refreshed. Try again in a moment."


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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect: urllib would copy the key header to wherever it points."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # the 3xx then raises HTTPError, shown as "couldn't reach"


# Certificates always checked (an explicit default context), no redirects. The system proxy, if
# any, is used: HTTPS goes through it as a tunnel (docs/dev/architecture/security.md).
_OPENER = urllib.request.build_opener(
    _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
)


def _reject_constant(name: str):
    raise ValueError(f"not a number: {name}")  # NaN, Infinity


def _get_json(url: str, key: str) -> dict:
    """One HTTPS GET to Finnhub. The key goes in a header, not the address."""
    request = urllib.request.Request(url, headers={"X-Finnhub-Token": key})
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as reply:
            return json.loads(reply.read(MAX_REPLY_BYTES), parse_constant=_reject_constant)
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
    latest = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    try:
        price = Decimal(str(data.get("c") or 0))
        when = int(data.get("t") or 0)
        if (
            not price.is_finite()
            or not 0 < price <= MAX_PRICE
            or not 0 < when <= latest.timestamp()
        ):
            return None
        cents = int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        day = dt.datetime.fromtimestamp(when, dt.UTC).date()
    except (InvalidOperation, TypeError, ValueError, AttributeError, OverflowError, OSError):
        return None  # anything odd: no price, rather than a broken page
    return (cents, day) if cents > 0 else None


def _due(session: Session, now: dt.datetime) -> list[str]:
    """Held symbols without a feed price from the last minute, at most ``MAX_SYMBOLS``."""
    fresh = now - dt.timedelta(seconds=FRESH_SECONDS)
    recent = {
        p.symbol
        for p in session.scalars(select(StockPrice).where(StockPrice.source == FEED))
        if p.fetched_at and p.fetched_at > fresh
    }
    return [s for s in held_symbols(session) if s not in recent][:MAX_SYMBOLS]


def refresh(session: Session, now: dt.datetime | None = None) -> RefreshResult:
    """Fetch the latest price of each symbol you hold that wasn't fetched in the last minute.

    All the asking happens first, with nothing written; then the prices are saved in one short
    transaction, so the database is never locked while waiting on the internet. One refresh at a
    time: a second one meanwhile just says so.
    """
    now = now or dt.datetime.now(dt.UTC).replace(tzinfo=None)
    feed = _feed(session)
    if not feed.enabled:
        return RefreshResult(enabled=False, updated=[], not_found=[], message=OFF)
    if not feed.api_key:
        return RefreshResult(enabled=True, updated=[], not_found=[], message=NO_KEY)
    key, due = feed.api_key, _due(session, now)
    session.rollback()  # end the read before going to the internet
    if not _RUNNING.acquire(blocking=False):
        return RefreshResult(enabled=True, updated=[], not_found=[], message=BUSY)
    try:
        found, not_found, message = {}, [], None
        for symbol in due:
            try:
                price = quote(symbol, key)
            except FeedStop as stop:
                message = str(stop)
                break
            if price is None:
                not_found.append(symbol)
            else:
                found[symbol] = price
        for symbol, (cents, day) in found.items():
            row = session.get(StockPrice, symbol) or StockPrice(symbol=symbol)
            row.price_cents, row.as_of, row.source, row.fetched_at = cents, day, FEED, now
            session.add(row)
        session.commit()
    finally:
        _RUNNING.release()
    return RefreshResult(enabled=True, updated=list(found), not_found=not_found, message=message)
