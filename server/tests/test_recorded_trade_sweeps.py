"""A trade you record yourself from a transaction (Transactions page, "stock trade") gets its
deposit sweep linked like a trade found in a bank file, so the sweep doesn't wait for a category.
Fake numbers only."""

import pytest

TXNS = "/api/local/transactions"
TRADES = "/api/local/stocks/bank-trades"
PAID = "FAKE BROKER ORDER 12345"  # no trade wording: the finder doesn't name it
SWEEP_IN = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"
SWEEP_OUT = "FAKE DEPOSIT SWEEP INTRA-DAY DEPOSIT"


@pytest.fixture
def brokerage(make_account) -> int:
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def waiting(client) -> list[str]:
    items = client.get(TXNS, params={"uncategorized": "true"}).json()["items"]
    return sorted(t["description"] for t in items)


def buy(client, transaction_id, symbol="FAKE") -> None:
    body = {"transaction_id": transaction_id, "symbol": symbol, "acquired_on": "2026-10-02",
            "shares": "5", "cost_basis_cents": 50_000}  # fmt: skip
    assert client.post("/api/local/stocks/lots", json=body).status_code == 201


def test_recording_a_buy_links_its_sweep(client, brokerage, add_txn):
    paid = add_txn(brokerage, -50_000, date="2026-10-02", description=PAID)
    add_txn(brokerage, 50_000, date="2026-10-02", description=SWEEP_IN)
    assert waiting(client) == sorted([PAID, SWEEP_IN])

    buy(client, paid["id"])
    assert waiting(client) == []
    [trade] = client.get(TRADES).json()["items"]
    assert (trade["recorded"], trade["symbol"]) == (True, "FAKE")
    assert trade["sweep_transaction_id"] is not None
    month = client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()
    assert month["unassigned_count"] == 0


def test_recording_a_sale_links_its_sweep(client, brokerage, add_txn):
    bought = add_txn(brokerage, -50_000, date="2026-10-01", description=PAID)
    buy(client, bought["id"])
    sold = add_txn(brokerage, 30_000, date="2026-10-06", description="FAKE BROKER ORDER 67890")
    add_txn(brokerage, -30_000, date="2026-10-07", description=SWEEP_OUT)
    body = {"transaction_id": sold["id"], "symbol": "FAKE", "sold_on": "2026-10-06",
            "shares": "2", "proceeds_cents": 30_000}  # fmt: skip
    assert client.post("/api/local/stocks/sales", json=body).status_code == 201
    assert waiting(client) == []


def test_a_sweep_that_comes_in_later_is_linked(client, brokerage, add_txn):
    paid = add_txn(brokerage, -50_000, date="2026-10-02", description=PAID)
    buy(client, paid["id"])
    assert client.get(TRADES).json()["items"] == []  # no sweep yet: nothing to list
    add_txn(brokerage, 50_000, date="2026-10-03", description=SWEEP_IN)
    assert waiting(client) == []
    assert len(client.get(TRADES).json()["items"]) == 1


def test_a_recorded_trade_cant_be_marked_not_a_trade(client, brokerage, add_txn):
    paid = add_txn(brokerage, -50_000, date="2026-10-02", description=PAID)
    add_txn(brokerage, 50_000, date="2026-10-02", description=SWEEP_IN)
    buy(client, paid["id"])
    [trade] = client.get(TRADES).json()["items"]
    refused = client.post(f"{TRADES}/{trade['id']}/dismiss")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "trade_recorded"


def test_deleting_the_purchase_puts_both_back(client, brokerage, add_txn):
    paid = add_txn(brokerage, -50_000, date="2026-10-02", description=PAID)
    add_txn(brokerage, 50_000, date="2026-10-02", description=SWEEP_IN)
    buy(client, paid["id"])
    [lot] = client.get("/api/local/stocks/lots").json()
    assert client.delete(f"/api/local/stocks/lots/{lot['id']}").status_code == 204
    assert waiting(client) == sorted([PAID, SWEEP_IN])  # not a trade after all: count both
    assert client.get(TRADES).json()["items"] == []


def test_a_found_trade_stays_found_after_deleting_its_purchase(client, brokerage, add_txn):
    paid = add_txn(brokerage, -50_000, date="2026-10-02", description="YOU BOUGHT FAKE FUND (FAKE)")
    add_txn(brokerage, 50_000, date="2026-10-02", description=SWEEP_IN)
    buy(client, paid["id"])
    [lot] = client.get("/api/local/stocks/lots").json()
    assert client.delete(f"/api/local/stocks/lots/{lot['id']}").status_code == 204
    [trade] = client.get(TRADES).json()["items"]  # waiting for its shares again
    assert (trade["recorded"], waiting(client)) == (False, [])
