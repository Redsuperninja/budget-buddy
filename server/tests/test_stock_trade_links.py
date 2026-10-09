"""Stock purchases and sales classified from a transaction (Transactions page). Fake data only."""

import pytest

LOTS = "/api/local/stocks/lots"
SALES = "/api/local/stocks/sales"
TXN = "/api/local/transactions"


@pytest.fixture
def brokerage(make_account):
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def buy_from(client, transaction_id, shares="2", cost=None, **extra):
    body = {"symbol": "FAKE", "acquired_on": "2026-03-02", "shares": shares}
    body |= {"cost_basis_cents": cost or 20_000, "transaction_id": transaction_id, **extra}
    return client.post(LOTS, json=body)


def test_classify_a_purchase_and_a_sale(client, brokerage, add_txn):
    paid = add_txn(brokerage, -20_000, date="2026-03-02", description="YOU BOUGHT FAKE")
    lot = buy_from(client, paid["id"])
    assert lot.status_code == 201, lot.text
    assert (lot.json()["transaction_id"], lot.json()["account_id"]) == (paid["id"], brokerage)

    got = add_txn(brokerage, 15_000, date="2026-04-01", description="YOU SOLD FAKE")
    body = {"symbol": "FAKE", "sold_on": "2026-04-01", "shares": "1", "proceeds_cents": 15_000}
    sale = client.post(SALES, json=body | {"transaction_id": got["id"]})
    assert sale.status_code == 201, sale.text
    assert sale.json()["transaction_id"] == got["id"]

    # Neither is spending, income or waiting for a category: cash turned into shares and back.
    summary = client.get("/api/local/summary/monthly", params={"month": "2026-03"}).json()
    assert (summary["unassigned_out_cents"], summary["spending_cents"]) == (0, 0)
    waiting = client.get(TXN, params={"uncategorized": True}).json()["items"]
    assert waiting == []


def test_what_cant_be_a_trade(client, brokerage, make_account, add_txn):
    checking = make_account()["id"]
    in_checking = add_txn(checking, -20_000, description="Fake")
    money_in = add_txn(brokerage, 20_000, description="Fake")
    adjustment = add_txn(brokerage, 500, description="Fake", kind="adjustment")
    for transaction, phrase in [
        (in_checking, "brokerage, retirement or HSA"),
        (money_in, "has to be money out"),
        (adjustment, "regular transaction"),
    ]:
        refused = buy_from(client, transaction["id"])
        assert refused.status_code == 422
        assert phrase in refused.json()["error"]["message"]
    assert buy_from(client, 999_999).status_code == 404

    paid = add_txn(brokerage, -20_000, description="Fake")
    other = make_account(name="Other Brokerage", kind="brokerage")["id"]
    assert buy_from(client, paid["id"], account_id=other).status_code == 422
    assert buy_from(client, paid["id"]).status_code == 201
    again = buy_from(client, paid["id"])
    assert (again.status_code, again.json()["error"]["code"]) == (409, "already_a_trade")


def test_deleting_the_transaction_keeps_the_shares(client, brokerage, add_txn):
    paid = add_txn(brokerage, -20_000, description="Fake")
    lot = buy_from(client, paid["id"]).json()
    assert client.delete(f"{TXN}/{paid['id']}").status_code == 204
    assert client.get(f"{LOTS}/{lot['id']}").json()["transaction_id"] is None
