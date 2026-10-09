"""Brokerage activity import: transactions, with buys and sells linked as stock trades and
dividends filed. Fake data shaped like a broker's history export."""

import pytest

SH = 1_000_000

ACTIVITY_CSV = (
    "Run Date,Action,Symbol,Description,Type,Quantity,Price ($),Commission ($),Fees ($),"
    "Amount ($),Settlement Date\r\n"
    "01/02/2026,Electronic Funds Transfer Received,,No Description,Cash,0,,,,1000.00,01/02/2026\r\n"
    "01/05/2026,YOU BOUGHT FAKE FUND (FAKE),FAKE,FAKE FUND,Cash,4,100,,,-400.00,01/06/2026\r\n"
    "03/31/2026,DIVIDEND RECEIVED FAKE FUND (FAKE),FAKE,FAKE FUND,Cash,0,,,,3.10,03/31/2026\r\n"
    "06/01/2026,YOU SOLD FAKE FUND (FAKE),FAKE,FAKE FUND,Cash,-1,150,,,149.95,06/02/2026\r\n"
    "06/02/2026,SELL SHORT OTHR (Margin),OTHR,OTHER CO,Margin,-1,10,,,10.00,06/03/2026\r\n"
    "06/03/2026,JOURNALED SHARES IN,OTHR,OTHER CO,Cash,5,,,,0.00,06/03/2026\r\n"
)


@pytest.fixture
def brokerage(make_account):
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def send(client, account_id, action="preview", body=ACTIVITY_CSV, **params):
    url = f"/api/local/accounts/{account_id}/activity-import"
    return client.post(
        f"{url}/preview" if action == "preview" else url,
        content=body.encode(),
        params=params,
        headers={"Content-Type": "text/csv"},
    )


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_shows_transactions_and_trades(client, brokerage):
    p = ok(send(client, brokerage))
    # "Price", "Commission" and "Settlement Date" are never used.
    assert p["columns"] | {"date_format": None} == {
        "date": 0,
        "action": 1,
        "amount": 9,
        "symbol": 2,
        "shares": 5,
        "description": 3,
        "date_format": None,
    }
    assert (p["total_rows"], p["new_rows"], p["new_trades"], p["invalid_rows"]) == (6, 5, 2, 1)
    trades = [r["trade"] for r in p["rows"] if r["status"] == "new"]
    assert trades == [None, "Buy 4 FAKE", None, "Sell 1 FAKE", None]  # a short sale isn't a trade
    assert p["rows"][1]["description"] == "YOU BOUGHT FAKE FUND (FAKE)"


def test_import_sorts_trades_and_dividends_then_skips_duplicates(client, brokerage):
    r = ok(send(client, brokerage, "commit", skip_invalid_rows=True, file_name="fake.csv"))
    assert (r["imported"], r["trades"], r["dividends_found"], r["skipped_invalid"]) == (5, 2, 1, 1)

    lots = client.get("/api/local/stocks/lots").json()
    assert [(lot["symbol"], lot["shares_micro"], lot["cost_basis_cents"]) for lot in lots] == [
        ("FAKE", 4 * SH, 40_000)
    ]
    sale = client.get("/api/local/stocks/sales").json()[0]
    assert (sale["proceeds_cents"], sale["cost_basis_cents"], sale["gain_cents"]) == (
        14_995,
        10_000,
        4_995,
    )
    assert lots[0]["transaction_id"] and sale["transaction_id"]
    dividends = client.get("/api/local/dividends/2026").json()["dividends"]
    assert [(d["amount_cents"], d["taxed"]) for d in dividends] == [(310, True)]

    history = client.get("/api/local/imports").json()
    assert [(h["kind"], h["file_name"], h["rows_added"]) for h in history] == [
        ("activity", "fake.csv", 5)
    ]
    again = ok(send(client, brokerage, "commit", skip_invalid_rows=True))
    assert (again["imported"], again["skipped_duplicates"]) == (0, 5)

    # Undoing the import takes the trades and dividend with it.
    assert client.delete(f"/api/local/imports/{history[0]['id']}").status_code == 204
    assert client.get("/api/local/stocks/lots").json() == []
    assert client.get("/api/local/dividends/2026").json()["dividends"] == []


def test_problems_and_wrong_account(client, brokerage, make_account):
    refused = send(client, brokerage, "commit")
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "invalid_rows")
    checking = make_account()["id"]
    wrong = send(client, checking)
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "not_an_investment_account")
    sale_first = "Date,Action,Symbol,Quantity,Amount\r\n01/05/2026,YOU SOLD FAKE,FAKE,-1,10.00\r\n"
    short = send(client, brokerage, "commit", body=sale_first)
    assert (short.status_code, short.json()["error"]["code"]) == (422, "not_enough_shares")
    assert client.get("/api/local/imports").json() == []  # nothing was imported
    nameless = send(client, brokerage, body="Foo,Bar\r\n1,2\r\n")
    assert nameless.json()["error"]["code"] == "columns_not_found"
