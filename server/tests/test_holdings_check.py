"""Checking recorded purchases and sales against the broker's positions file and the transactions
behind them, both ways. Fake data only."""

import pytest

POSITIONS = "/api/local/stocks/positions"
LOTS = "/api/local/stocks/lots"
SALES = "/api/local/stocks/sales"
SH = 1_000_000


@pytest.fixture
def ira(make_account) -> int:
    return make_account(name="Fake IRA", kind="retirement")["id"]


def positions_file(client, account_id, lines: str, as_of="2026-10-08") -> None:
    body = "Symbol,Quantity\r\n" + lines
    response = client.post(
        f"{POSITIONS}/import",
        content=body.encode(),
        params={"account_id": account_id, "as_of": as_of},
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text


def buy(client, account_id, symbol, shares, on="2026-01-05", **extra) -> dict:
    body = {"account_id": account_id, "symbol": symbol, "acquired_on": on, "shares": shares,
            "cost_basis_cents": 10_000, **extra}  # fmt: skip
    response = client.post(LOTS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def sell(client, account_id, symbol, shares, on="2026-06-01") -> dict:
    body = {"account_id": account_id, "symbol": symbol, "sold_on": on, "shares": shares,
            "proceeds_cents": 5_000}  # fmt: skip
    response = client.post(SALES, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def lines(client) -> dict[str, dict]:
    [account] = client.get(POSITIONS).json()["accounts"]
    return {p["symbol"]: p for p in account["positions"]}


def checked(client, url) -> dict[str, str | None]:
    return {f"{r['symbol']} {r.get('acquired_on') or r['sold_on']}": r["checked_by"]
            for r in client.get(url).json()}  # fmt: skip


def test_a_symbol_you_hold_but_the_file_leaves_out_is_flagged(client, ira):
    buy(client, ira, "FAKE", "10")
    buy(client, ira, "GONE", "5")
    positions_file(client, ira, "FAKE,10\r\n")

    got = lines(client)
    assert (got["FAKE"]["matches"], got["FAKE"]["in_file"]) == (True, True)
    assert got["GONE"]["in_file"] is False
    assert got["GONE"]["matches"] is False
    assert (got["GONE"]["shares_micro"], got["GONE"]["recorded_shares_micro"]) == (0, 5 * SH)


def test_a_symbol_sold_out_and_not_in_the_file_is_fine(client, ira):
    buy(client, ira, "FAKE", "10")
    buy(client, ira, "SOLD", "3")
    sell(client, ira, "SOLD", "3")
    positions_file(client, ira, "FAKE,10\r\n")
    assert set(lines(client)) == {"FAKE"}


def test_purchases_and_sales_say_what_backs_them_up(client, ira, add_txn):
    paid = add_txn(ira, -10_000, date="2026-01-05", description="YOU BOUGHT FAKE FUND (FAKE)")
    buy(client, ira, "FAKE", "4", transaction_id=paid["id"])
    buy(client, ira, "FAKE", "6", on="2026-02-05")
    buy(client, ira, "MISS", "2", on="2026-03-05")
    buy(client, ira, "LATE", "1", on="2026-10-09")  # after the file's day
    buy(client, ira, "SOLD", "3")
    sell(client, ira, "SOLD", "3")
    positions_file(client, ira, "FAKE,10\r\nMISS,5\r\n")

    assert checked(client, LOTS) == {
        "FAKE 2026-01-05": "transaction",  # linked to its payment
        "FAKE 2026-02-05": "positions_file",  # the file's 10 shares match
        "MISS 2026-03-05": None,  # the file says 5: something's missing
        "LATE 2026-10-09": None,  # newer than the file
        "SOLD 2026-01-05": "positions_file",  # none on both sides
    }
    assert checked(client, SALES) == {"SOLD 2026-06-01": "positions_file"}


def test_bank_trades_waiting_for_shares_are_counted(client, ira, add_txn):
    line = "FAKECO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL"
    add_txn(ira, -50_000, date="2026-10-01", description=line)
    add_txn(ira, -50_000, date="2026-10-20", description=line)  # after the file
    positions_file(client, ira, "FAKE,10\r\n")
    [account] = client.get(POSITIONS).json()["accounts"]
    assert account["bank_trades_waiting"] == 1


def test_without_a_positions_file_only_transactions_back_things_up(client, ira):
    buy(client, ira, "FAKE", "10")
    assert checked(client, LOTS) == {"FAKE 2026-01-05": None}
