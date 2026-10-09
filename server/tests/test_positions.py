"""Positions from a broker's file: a snapshot per account, compared with recorded trades. Fake
data shaped like a broker's positions export."""

import pytest

URL = "/api/local/stocks/positions"
SH = 1_000_000

POSITIONS_CSV = (
    "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,"
    "Current Value,Today's Gain/Loss Dollar,Percent Of Account,Cost Basis Total,"
    "Average Cost Basis\r\n"
    "X1,Fake IRA,SPAXX**,FAKE MONEY MARKET,,,,$120.50,,1.2%,,\r\n"
    'X1,Fake IRA,FAKE,FAKE FUND,10,$25.00,+$0.10,$250.00,+$1.00,40%,"$1,800.00",$180.00\r\n'
    "X1,Fake IRA,FAKE,FAKE FUND,2,$25.00,+$0.10,$50.00,+$0.20,8%,$40.00,$20.00\r\n"
    "X1,Fake IRA,OTHR,OTHER FUND,1.5,$10.00,,$15.00,,2%,--,--\r\n"
    "\r\n"
    '"The data and information in this spreadsheet is provided to you solely for your use"\r\n'
)


@pytest.fixture
def ira(make_account):
    return make_account(name="Fake IRA", kind="retirement")["id"]


def send(client, account_id, body=POSITIONS_CSV, action="import/preview", as_of="2026-10-08"):
    return client.post(
        f"{URL}/{action}",
        content=body.encode(),
        params={"account_id": account_id, "as_of": as_of},
        headers={"Content-Type": "text/csv"},
    )


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_combines_lines_and_skips_cash_and_notes(client, ira):
    p = ok(send(client, ira))
    # "Last Price Change", "Today's Gain" and "Average Cost Basis" are never used.
    assert p["columns"] == {"symbol": 2, "shares": 4, "cost": 10, "value": 7, "price": 5}
    positions = [r for r in p["rows"] if r["status"] == "ok"]
    assert [
        (r["symbol"], r["shares"], r["cost_basis_cents"], r["value_cents"]) for r in positions
    ] == [
        ("FAKE", "12", 184_000, 30_000),
        ("OTHR", "1.5", None, 1_500),
    ]
    assert (p["positions"], p["skipped"]) == (2, 2)  # the cash fund line and the note
    assert client.get(URL).json()["accounts"] == []  # a preview saves nothing


def test_import_replaces_the_snapshot_and_compares_with_your_trades(client, ira):
    lot = {"account_id": ira, "symbol": "FAKE", "acquired_on": "2026-01-05"}
    assert client.post(
        "/api/local/stocks/lots", json=lot | {"shares": "12", "cost_basis": "1840"}
    ).is_success
    r = ok(send(client, ira, action="import"))
    assert r == {"positions": 2, "prices_updated": 2, "skipped": 2}

    group = client.get(URL).json()["accounts"][0]
    assert (group["account_name"], group["as_of"], group["value_cents"]) == (
        "Fake IRA",
        "2026-10-08",
        31_500,
    )
    assert [
        (x["symbol"], x["recorded_shares_micro"], x["matches"]) for x in group["positions"]
    ] == [
        ("FAKE", 12 * SH, True),
        ("OTHR", 0, False),  # no purchase recorded: one may be missing
    ]
    holding = client.get("/api/local/stocks/holdings").json()["accounts"][0]["holdings"][0]
    assert (holding["price_cents"], holding["price_source"]) == (2_500, "file")

    smaller = "Symbol,Quantity\r\nFAKE,1\r\n"
    ok(send(client, ira, smaller, action="import", as_of="2026-10-01"))
    after = client.get(URL).json()["accounts"][0]["positions"]
    assert [(x["symbol"], x["shares"]) for x in after] == [("FAKE", "1")]  # replaced, not added
    # A file from an earlier day never replaces a later price.
    holding = client.get("/api/local/stocks/holdings").json()["accounts"][0]["holdings"][0]
    assert holding["price_cents"] == 2_500


def test_clear_and_errors(client, ira):
    ok(send(client, ira, action="import"))
    assert client.delete(f"{URL}/{ira}").status_code == 204
    assert client.get(URL).json()["accounts"] == []
    assert send(client, 999).status_code == 404
    refused = send(client, ira, "Name,Amount\r\nx,1\r\n")
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "columns_not_found")
