"""Live prices from Finnhub (ADR-0010). Finnhub is faked: tests never touch the internet."""

import datetime as dt
import io
import json
import types
import urllib.error

import pytest

from app.services import price_feed

FEED = "/api/local/price-feed"
REFRESH = "/api/local/stocks/prices/refresh"
HOLDINGS = "/api/local/stocks/holdings"
KEY = "fakekey123"
WHEN = int(dt.datetime(2026, 10, 9, 20, 0, tzinfo=dt.UTC).timestamp())


@pytest.fixture(autouse=True)
def no_internet(monkeypatch):
    """Every test: the real opener is never used, so nothing reaches Finnhub."""

    def refuse(request, timeout):
        raise AssertionError(f"a test tried to reach {request.full_url}")

    monkeypatch.setattr(price_feed, "_OPENER", types.SimpleNamespace(open=refuse))


@pytest.fixture
def finnhub(monkeypatch):
    """Answers like Finnhub's quote API; records what was asked."""
    calls = []
    quotes = {"FAKE": {"c": 123.456, "t": WHEN}, "IRAF": {"c": 50, "t": WHEN}}

    def get_json(url, key):
        calls.append((url, key))
        symbol = url.split("symbol=")[1]
        return quotes.get(symbol, {"c": 0, "t": 0})

    monkeypatch.setattr(price_feed, "_get_json", get_json)
    return calls


def buy(client, symbol, shares="2", account_id=None):
    body = {"symbol": symbol, "acquired_on": "2025-01-02", "shares": shares, "cost_basis": "100.00"}
    assert (
        client.post("/api/local/stocks/lots", json=body | {"account_id": account_id}).status_code
        == 201
    )


def turn_on(client, key=KEY):
    return client.put(FEED, json={"enabled": True, "api_key": key})


def test_off_until_turned_on(client, finnhub):
    buy(client, "FAKE")
    assert client.get(FEED).json() == {"enabled": False, "has_key": False}
    result = client.post(REFRESH).json()
    assert result["updated"] == [] and "off" in result["message"]
    assert finnhub == []  # nothing was sent


def test_turned_on_without_a_key(client, finnhub):
    buy(client, "FAKE")
    client.put(FEED, json={"enabled": True})
    assert "key" in client.post(REFRESH).json()["message"]
    assert finnhub == []


def test_refresh_fetches_held_symbols_only(client, finnhub, make_account):
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    buy(client, "FAKE")
    buy(client, "IRAF", account_id=ira)
    buy(client, "GONE", shares="1")
    client.post("/api/local/stocks/sales", json={"symbol": "GONE", "sold_on": "2026-01-02",
                                                  "shares": "1", "proceeds": "1.00"})  # fmt: skip
    assert turn_on(client).json() == {"enabled": True, "has_key": True}
    result = client.post(REFRESH).json()
    assert result == {
        "enabled": True,
        "updated": ["FAKE", "IRAF"],
        "not_found": [],
        "message": None,
    }
    assert {url.split("symbol=")[1] for url, _ in finnhub} == {"FAKE", "IRAF"}  # not GONE
    assert all(key == KEY and KEY not in url for url, key in finnhub)  # key in the header only
    holding = client.get(HOLDINGS).json()["accounts"][0]["holdings"][0]
    assert (holding["price_cents"], holding["price_source"], holding["price_as_of"]) == (
        12_346,  # 123.456 rounded half up
        "feed",
        "2026-10-09",
    )


def test_a_recent_price_isnt_fetched_again(client, finnhub):
    buy(client, "FAKE")
    turn_on(client)
    client.post(REFRESH)
    again = client.post(REFRESH).json()
    assert again["updated"] == [] and len(finnhub) == 1


def test_unknown_symbol(client, finnhub):
    buy(client, "NOPE")
    turn_on(client)
    assert client.post(REFRESH).json()["not_found"] == ["NOPE"]


@pytest.mark.parametrize(
    ("code", "words"), [(401, "didn't accept your key"), (429, "limit"), (500, "Couldn't reach")]
)
def test_problems_stop_with_a_plain_message(client, monkeypatch, code, words):
    def fail(url, key):
        raise price_feed.FeedStop(
            {401: price_feed.BAD_KEY, 429: price_feed.LIMIT}.get(code, price_feed.OFFLINE)
        )

    monkeypatch.setattr(price_feed, "_get_json", fail)
    buy(client, "FAKE")
    turn_on(client)
    assert words in client.post(REFRESH).json()["message"]


def test_a_symbol_the_plan_doesnt_cover_is_skipped(client, monkeypatch):
    """Finnhub answers 403 for a symbol behind a paid plan: that one has no price, the rest do."""
    asked = []

    def open_url(request, timeout):
        symbol = request.full_url.split("symbol=")[1]
        asked.append(symbol)
        if symbol == "FUNDX":
            raise urllib.error.HTTPError(request.full_url, 403, "no access", {}, None)
        return io.BytesIO(json.dumps({"c": 10, "t": WHEN}).encode())

    monkeypatch.setattr(price_feed, "_OPENER", types.SimpleNamespace(open=open_url))
    buy(client, "FUNDX")
    buy(client, "FAKE")
    turn_on(client)
    result = client.post(REFRESH).json()
    assert (result["updated"], result["not_found"]) == (["FAKE"], ["FUNDX"])
    assert result["message"] is None  # not "didn't accept your key"
    assert asked == ["FAKE", "FUNDX"]


@pytest.mark.parametrize(
    ("error", "words"),
    [
        (urllib.error.HTTPError("u", 401, "no", {}, None), "didn't accept"),
        (urllib.error.HTTPError("u", 429, "slow", {}, None), "limit"),
        (urllib.error.HTTPError("u", 503, "down", {}, None), "Couldn't reach"),
        (urllib.error.URLError("offline"), "Couldn't reach"),
    ],
)
def test_http_errors_become_plain_messages(monkeypatch, error, words):
    def raise_it(request, timeout):
        assert request.get_header("X-finnhub-token") == KEY
        assert request.full_url.startswith("https://finnhub.io/")
        raise error

    monkeypatch.setattr(price_feed, "_OPENER", types.SimpleNamespace(open=raise_it))
    with pytest.raises(price_feed.FeedStop, match=words):
        price_feed.quote("FAKE", KEY)


def test_a_typed_price_is_marked_as_yours(client):
    buy(client, "FAKE")
    client.post(
        "/api/local/stocks/prices", json={"symbol": "FAKE", "price": "10.00", "as_of": "2026-10-09"}
    )
    holding = client.get(HOLDINGS).json()["accounts"][0]["holdings"][0]
    assert (holding["price_source"], holding["price_fetched_at"]) == ("you", None)


def test_the_key_is_never_sent_back_and_can_be_removed(client):
    turn_on(client)
    assert KEY not in client.get(FEED).text
    assert client.put(FEED, json={"enabled": True, "api_key": ""}).json()["has_key"] is False
    assert client.put(FEED, json={"enabled": True, "api_key": "bad key!"}).status_code == 422


def test_bad_replies_are_ignored(monkeypatch):
    replies = [
        {"c": "x", "t": WHEN}, {"c": -1, "t": WHEN}, [], {"c": 5}, {"c": float("nan"), "t": WHEN},
        {"c": float("inf"), "t": WHEN}, {"c": 1e300, "t": WHEN}, {"c": 1e20, "t": WHEN},
        {"c": 5, "t": 1e20}, {"c": 5, "t": WHEN + 10**9}, {"c": 0.001, "t": WHEN},
    ]  # fmt: skip
    for reply in replies:
        monkeypatch.setattr(price_feed, "_get_json", lambda url, key, r=reply: r)
        assert price_feed.quote("FAKE", KEY) is None


def test_a_redirect_is_never_followed(monkeypatch):
    """urllib copies headers to a redirect's target; the key must never go anywhere but Finnhub."""
    import io
    import urllib.request

    sent = []

    class Redirecting(urllib.request.BaseHandler):
        handler_order = 100  # before the real HTTPS handler: nothing goes on the network

        def https_open(self, request):
            sent.append(request.full_url)
            response = urllib.response.addinfourl(
                io.BytesIO(b""), {"Location": "http://evil.example/"}, request.full_url, 302
            )
            response.msg = "Found"
            return response

    opener = urllib.request.build_opener(price_feed._NoRedirect(), Redirecting())
    monkeypatch.setattr(price_feed, "_OPENER", opener)
    with pytest.raises(price_feed.FeedStop, match="Couldn't reach"):
        price_feed.quote("FAKE", KEY)
    assert sent == ["https://finnhub.io/api/v1/quote?symbol=FAKE"]


def test_a_huge_or_odd_reply_is_rejected_when_parsed():
    with pytest.raises(ValueError):
        price_feed.json.loads(b'{"c": NaN}', parse_constant=price_feed._reject_constant)


def test_one_refresh_at_a_time(client, finnhub):
    buy(client, "FAKE")
    turn_on(client)
    price_feed._RUNNING.acquire()
    try:
        assert "already" in client.post(REFRESH).json()["message"]
    finally:
        price_feed._RUNNING.release()


def test_settings_are_this_computer_only(make_client):
    lan = make_client("192.168.1.50", base_url="http://192.168.1.20:8765")
    assert lan.get(FEED).status_code == 403
