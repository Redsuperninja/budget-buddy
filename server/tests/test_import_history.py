"""Import history: every file imported, and undoing one. Fake data only."""

import pytest
from csv_helpers import CHECKING_CSV, ok, send, txns

URL = "/api/local/imports"


@pytest.fixture
def checking(make_account):
    return make_account()["id"]


def history(client):
    return client.get(URL).json()


def test_a_bank_import_is_listed_and_can_be_undone(client, checking, add_txn):
    ok(send(client, checking, CHECKING_CSV, "commit", file_name="fake-statement.csv"))
    [entry] = history(client)
    assert (entry["kind"], entry["account_name"], entry["file_name"], entry["rows_added"]) == (
        "bank",
        "Test Checking",
        "fake-statement.csv",
        4,
    )
    typed = add_txn(checking, -100, description="Typed in")
    assert client.delete(f"{URL}/{entry['id']}").status_code == 204
    assert [t["id"] for t in txns(client, checking)] == [typed["id"]]  # only the typed-in one
    assert history(client) == []
    assert client.delete(f"{URL}/{entry['id']}").status_code == 404

    # Nothing new: nothing recorded.
    ok(send(client, checking, CHECKING_CSV, "commit"))
    ok(send(client, checking, CHECKING_CSV, "commit"))
    assert len(history(client)) == 1


def test_undo_frees_a_transfer_partner(client, checking, make_account, add_txn):
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    other = add_txn(savings, 50_000, date="2026-01-06", description="Transfer from checking")
    body = "Date,Description,Amount\r\n01/06/2026,Online transfer to savings,-500.00\r\n"
    assert ok(send(client, checking, body, "commit"))["transfers_matched"] == 1
    [entry] = history(client)
    assert client.delete(f"{URL}/{entry['id']}").status_code == 204
    partner = client.get(f"/api/local/transactions/{other['id']}").json()
    assert (partner["kind"], partner["transfer_pair_id"]) == ("normal", None)


def test_undo_a_stock_import_unless_a_sale_needs_it(client, make_account):
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    body = "Symbol,Date,Shares,Cost\r\nFAKE,2026-01-05,2,20.00\r\n"
    imported = client.post(
        "/api/local/stocks/import",
        content=body.encode(),
        params={"account_id": brokerage, "file_name": "fake-trades.csv"},
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    [entry] = history(client)
    assert (entry["kind"], entry["rows_added"]) == ("stocks", 1)

    sale = {"account_id": brokerage, "symbol": "FAKE", "sold_on": "2026-02-01", "shares": "1"}
    sold = client.post("/api/local/stocks/sales", json=sale | {"proceeds": "15"})
    assert sold.status_code == 201
    refused = client.delete(f"{URL}/{entry['id']}")
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "import_in_use")
    assert len(client.get("/api/local/stocks/lots").json()) == 1  # nothing removed

    assert client.delete(f"/api/local/stocks/sales/{sold.json()['id']}").status_code == 204
    assert client.delete(f"{URL}/{entry['id']}").status_code == 204
    assert client.get("/api/local/stocks/lots").json() == []


def test_a_newer_positions_file_replaces_the_older_entry(client, make_account):
    ira = make_account(name="Fake IRA", kind="retirement")["id"]

    def positions(name):
        response = client.post(
            "/api/local/stocks/positions/import",
            content=b"Symbol,Quantity\r\nFAKE,1\r\n",
            params={"account_id": ira, "as_of": "2026-10-01", "file_name": name},
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 200, response.text

    positions("old.csv")
    positions("new.csv")
    assert [(e["kind"], e["file_name"]) for e in history(client)] == [("positions", "new.csv")]
    assert client.delete(f"{URL}/{history(client)[0]['id']}").status_code == 204
    assert client.get("/api/local/stocks/positions").json()["accounts"] == []


def test_file_names_are_cleaned_and_stored_encrypted(client, checking):
    from sqlalchemy import text

    from app.db import SessionLocal

    ok(send(client, checking, CHECKING_CSV, "commit", file_name="Fake1234\u202e\u0007vsc.csv"))
    assert history(client)[0]["file_name"] == "Fake1234vsc.csv"
    with SessionLocal(bind=client.app.state.engine) as session:
        raw = session.execute(text("SELECT file_name FROM imports")).scalar()
    assert b"Fake1234" not in raw
