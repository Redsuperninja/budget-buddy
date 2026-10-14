"""Stock CSV import: header columns, preview, duplicates, sales with FIFO. Fake data only."""

import pytest

PREVIEW = "/api/local/stocks/import/preview"
COMMIT = "/api/local/stocks/import"
SH = 1_000_000

BUYS_AND_SELLS = (
    "Run Date,Action,Symbol,Security Type,Quantity,Price,Amount\r\n"
    "01/10/2025,YOU BOUGHT FAKE FUND,fake,Equity,5,100.00,-500.00\r\n"
    '06/01/2025,Buy,FAKE,Equity,"1,000",0.75,($750.00)\r\n'
    "03/01/2026,YOU SOLD FAKE FUND,FAKE,Equity,-7,150.00,1050.00\r\n"
)


@pytest.fixture
def brokerage(make_account):
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def send(client, body, url=PREVIEW, **params):
    return client.post(
        url, content=body.encode(), params=params, headers={"Content-Type": "text/csv"}
    )


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_finds_columns_and_rows(client, brokerage):
    p = ok(send(client, BUYS_AND_SELLS, account_id=brokerage))
    # "Security Type" isn't taken for buy or sell; "Price" isn't the total.
    assert p["columns"] | {"date_format": None} == {
        "symbol": 2,
        "date": 0,
        "shares": 4,
        "money": 6,
        "kind": 1,
        "date_format": None,
    }
    assert p["columns"]["date_format"] == "MM/DD/YYYY"
    assert (p["total_rows"], p["new_buys"], p["new_sells"], p["invalid_rows"]) == (3, 2, 1, 0)
    assert [
        (r["row_number"], r["kind"], r["symbol"], r["shares"], r["money_cents"]) for r in p["rows"]
    ] == [
        (2, "buy", "FAKE", "5", 50_000),
        (3, "buy", "FAKE", "1000", 75_000),
        (4, "sell", "FAKE", "7", 105_000),
    ]
    assert client.get("/api/local/stocks/lots").json() == []  # a preview saves nothing


def test_import_adds_purchases_and_sales_then_skips_them_next_time(client, brokerage):
    r = ok(send(client, BUYS_AND_SELLS, COMMIT, account_id=brokerage))
    assert r == {
        "purchases_added": 2,
        "sales_added": 1,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
    }
    lots = client.get("/api/local/stocks/lots").json()
    assert [
        (lot["account_id"], lot["shares_micro"], lot["remaining_shares_micro"]) for lot in lots
    ] == [
        (brokerage, 5 * SH, 0),
        (brokerage, 1000 * SH, 998 * SH),
    ]
    sale = client.get("/api/local/stocks/sales").json()[0]
    assert (sale["cost_basis_cents"], sale["gain_cents"]) == (50_000 + 150, 105_000 - 50_150)

    again = ok(send(client, BUYS_AND_SELLS, COMMIT, account_id=brokerage))
    assert again == {
        "purchases_added": 0,
        "sales_added": 0,
        "skipped_duplicates": 3,
        "skipped_invalid": 0,
    }


def test_identical_rows_in_one_file_are_both_kept(client):
    body = "Symbol,Date,Shares,Cost\r\nFAKE,2026-01-05,1,10.00\r\nFAKE,2026-01-05,1,10.00\r\n"
    assert ok(send(client, body, COMMIT))["purchases_added"] == 2
    longer = body + "FAKE,2026-01-05,1,10.00\r\n"
    p = ok(send(client, longer))
    assert (p["new_buys"], p["duplicate_rows"]) == (1, 2)


def test_without_a_type_column_every_row_is_a_purchase(client):
    body = "Ticker,Date Acquired,Qty,Cost Basis\r\nfake,2026-01-05,2.5,250.00\r\n"
    r = ok(send(client, body, COMMIT))
    assert r["purchases_added"] == 1
    lot = client.get("/api/local/stocks/lots").json()[0]
    assert (lot["symbol"], lot["account_id"], lot["shares"]) == ("FAKE", None, "2.5")


def test_bad_rows_are_reported_and_can_be_skipped(client):
    body = (
        "Type,Symbol,Date,Shares,Amount\r\n"
        "Buy,FAKE,2026-01-05,1,10.00\r\n"
        "Dividend,FAKE,2026-01-06,0,1.00\r\n"
        "Buy,FAKE,2026-01-07,1.1234567,10.00\r\n"
        "Buy,FA KE,2026-01-08,1,10.00\r\n"
        "Buy,FAKE,2026-01-09,1,ten\r\n"
    )
    p = ok(send(client, body))
    problems = {r["row_number"]: r["problem"] for r in p["rows"] if r["status"] == "invalid"}
    assert problems == {
        3: "The type should say Buy or Sell.",
        4: "Shares can have at most 6 decimal places.",
        5: "Enter a stock symbol like VTI or BRK.B (letters, numbers, . or -).",
        6: "The cost or amount isn't a dollar amount we can read.",
    }
    refused = send(client, body, COMMIT)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "invalid_rows"
    r = ok(send(client, body, COMMIT, skip_invalid_rows=True))
    assert (r["purchases_added"], r["skipped_invalid"]) == (1, 4)


def test_selling_more_than_owned_imports_nothing(client):
    header = "Type,Symbol,Date,Shares,Amount\r\n"
    body = header + "Buy,FAKE,2026-01-05,1,10\r\nSell,FAKE,2026-01-06,2,30\r\n"
    refused = send(client, body, COMMIT)
    assert refused.status_code == 422
    error = refused.json()["error"]
    assert error["code"] == "not_enough_shares"
    assert "FAKE on 2026-01-06" in error["message"] and "Nothing was imported" in error["message"]
    assert client.get("/api/local/stocks/lots").json() == []


def test_a_file_without_column_names_is_refused(client):
    refused = send(client, "FAKE,2026-01-05,1,10.00\r\n")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "columns_not_found"


def test_unknown_account_and_wrong_file_type(client):
    assert send(client, "Symbol,Date,Shares,Cost\r\n", account_id=999).status_code == 404
    wrong = client.post(PREVIEW, content=b"x", headers={"Content-Type": "image/png"})
    assert wrong.status_code == 415


def test_unreadable_dates(client):
    body = "Symbol,Date,Shares,Cost\r\nFAKE,soon,1,10.00\r\n"
    p = ok(send(client, body))
    assert p["columns"]["date_format"] is None
    assert "format we know" in p["rows"][0]["problem"]


def test_short_sales_options_and_corrections_are_refused(client):
    body = (
        "Action,Symbol,Date,Quantity,Amount\r\n"
        "YOU BOUGHT SALESFORCE INC,FAKE,2026-01-05,2,20.00\r\n"
        "Sell Short,FAKE,2026-01-06,1,10.00\r\n"
        "Buy to Cover,FAKE,2026-01-07,1,10.00\r\n"
        "Sell to Open CALL,FAKE,2026-01-08,1,10.00\r\n"
        "Cancel Buy,FAKE,2026-01-09,1,10.00\r\n"
        "Buy Correction,FAKE,2026-01-10,1,10.00\r\n"
        "Sell,FAKE,2026-01-11,(1),15.00\r\n"
    )
    p = ok(send(client, body))
    statuses = [(r["row_number"], r["status"], r["kind"]) for r in p["rows"]]
    assert statuses[0] == (2, "new", "buy")  # "SALESFORCE" isn't the word "sale"
    assert statuses[-1] == (8, "new", "sell")  # shares sold shown as (1)
    refused = [r for r in p["rows"] if r["status"] == "invalid"]
    assert [r["row_number"] for r in refused] == [3, 4, 5, 6, 7]
    assert all(r["problem"].startswith("Short sales, options and corrections") for r in refused)


def test_negative_shares_need_a_matching_type(client):
    no_type = "Symbol,Date,Shares,Cost\r\nFAKE,2026-01-05,-2,20.00\r\n"
    problem = ok(send(client, no_type))["rows"][0]["problem"]
    assert problem.startswith("The shares are negative, so this looks like a sale.")
    contradicts = "Type,Symbol,Date,Shares,Cost\r\nBuy,FAKE,2026-01-05,2-,20.00\r\n"
    problem = ok(send(client, contradicts))["rows"][0]["problem"]
    assert problem == "The type says Buy, but the number of shares is negative."


def test_price_fee_and_settlement_columns_are_never_used(client):
    body = (
        "Symbol,Settlement Date,Trade Date,Qty,Cost Per Share,Avg Cost,Commission Amount,Total\r\n"
        "FAKE,2026-01-07,2026-01-05,2,10.00,10.00,1.00,21.00\r\n"
    )
    p = ok(send(client, body))
    assert (p["columns"]["date"], p["columns"]["money"]) == (2, 7)
    assert (p["rows"][0]["date"], p["rows"][0]["money_cents"]) == ("2026-01-05", 2_100)
