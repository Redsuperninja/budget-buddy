"""One month of investing across a checking account, a brokerage and an IRA, checked end to
end: trades, dividends and their sweeps are found, linked and kept out of the budget; a real
transfer is still matched; a cash fund is left to sort; and "not a trade" / "not a dividend" put a
line back in the budget for good. Each feature is tested on its own elsewhere; this checks they
agree. Fake numbers only."""

import pytest
from csv_helpers import ok, send

TXNS = "/api/local/transactions"
TRADE = (
    "FAKECO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION EQUIVALENT"
)
SWEEP_IN = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"  # money into cash: pays for a buy
SWEEP_OUT = "FAKE DEPOSIT SWEEP INTRA-DAY DEPOSIT"  # money out of cash: parks a sale or dividend
CASH_FUND = "YOU BOUGHT JPMORGAN US GOVT MMKT"

BROKERAGE_FILE = (
    "Date,Description,Amount\r\n"
    "10/01/2026,ONLINE TRANSFER FROM CHECKING,1000.00\r\n"
    f"10/02/2026,{TRADE},-500.00\r\n"
    f"10/02/2026,{SWEEP_IN},500.00\r\n"
    "10/03/2026,FAKECO INC CASH DIV ON 10 SHS,12.34\r\n"
    f"10/03/2026,{SWEEP_OUT},-12.34\r\n"
    f"10/06/2026,{TRADE},300.00\r\n"
    f"10/07/2026,{SWEEP_OUT},-300.00\r\n"
    f"10/08/2026,{CASH_FUND},-50.00\r\n"
)
IRA_FILE = (
    "Date,Description,Amount\r\n"
    "10/03/2026,FAKE FUND DIVIDEND,5.00\r\n"
    f"10/03/2026,{SWEEP_OUT},-5.00\r\n"
)
CHECKING_FILE = "Date,Description,Amount\r\n10/01/2026,ONLINE TRANSFER TO BROKERAGE,-1000.00\r\n"


@pytest.fixture
def accounts(client, make_account) -> dict[str, int]:
    ids = {
        "checking": make_account(name="Fake Checking", kind="checking")["id"],
        "brokerage": make_account(name="Fake Brokerage", kind="brokerage")["id"],
        "ira": make_account(name="Fake IRA", kind="retirement")["id"],
    }
    ok(send(client, ids["checking"], CHECKING_FILE, "commit"))
    ok(send(client, ids["brokerage"], BROKERAGE_FILE, "commit"))
    ok(send(client, ids["ira"], IRA_FILE, "commit"))
    return ids


def descriptions(client, **params) -> list[str]:
    items = client.get(TXNS, params={"limit": 200, **params}).json()["items"]
    return sorted(t["description"] for t in items)


def summary(client) -> dict:
    return client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()


def trades(client) -> list[dict]:
    return client.get("/api/local/stocks/bank-trades").json()["items"]


def test_trades_dividends_and_sweeps_are_found_and_linked(client, accounts):
    found = trades(client)
    assert sorted(t["side"] for t in found) == ["buy", "sell"]
    assert all(t["sweep_transaction_id"] is not None for t in found)

    dividends = client.get("/api/local/dividends/2026").json()
    # The IRA's dividend isn't taxed.
    assert (dividends["total_cents"], dividends["taxed_cents"]) == (1734, 1234)
    assert all(d["sweep_transaction_id"] is not None for d in dividends["dividends"])


def test_only_the_cash_fund_needs_a_category(client, accounts):
    client.post(f"{TXNS}/match-transfers")
    assert descriptions(client, uncategorized="true") == [CASH_FUND]


def test_the_real_transfer_is_matched_and_no_sweep_is(client, accounts):
    client.post(f"{TXNS}/match-transfers")
    assert descriptions(client, kind="transfer") == [
        "ONLINE TRANSFER FROM CHECKING", "ONLINE TRANSFER TO BROKERAGE"]  # fmt: skip


def test_the_budget_counts_only_the_taxable_dividend(client, accounts):
    month = summary(client)
    assert month["income_cents"] == 1234
    assert month["spending_cents"] == 0
    # Only the cash fund is unsorted (the transfer was matched on import).
    assert (month["unassigned_out_cents"], month["unassigned_count"]) == (5000, 1)


def test_hiding_dividends_hides_trades_and_every_sweep(client, accounts):
    shown = descriptions(client, account_id=accounts["brokerage"], hide_dividends="true")
    assert shown == sorted([CASH_FUND, "ONLINE TRANSFER FROM CHECKING"])


def test_recording_shares_keeps_the_trade_out_of_the_budget(client, accounts):
    buy = next(t for t in trades(client) if t["side"] == "buy")
    lot = {"transaction_id": buy["transaction_id"], "symbol": "FAKE", "acquired_on": "2026-10-02",
           "shares": "5", "cost_basis_cents": 50_000}  # fmt: skip
    assert client.post("/api/local/stocks/lots", json=lot).status_code == 201
    assert summary(client)["unassigned_count"] == 1
    assert next(t for t in trades(client) if t["side"] == "buy")["price_cents"] == 10_000


def test_not_a_trade_puts_it_and_its_sweep_back_for_good(client, accounts):
    sale = next(t for t in trades(client) if t["side"] == "sell")
    assert client.post(f"/api/local/stocks/bank-trades/{sale['id']}/dismiss").status_code == 204
    waiting = descriptions(client, uncategorized="true")
    assert waiting == sorted([CASH_FUND, TRADE, SWEEP_OUT])
    assert client.post("/api/local/stocks/bank-trades/find").json()["found"] == 0


def test_not_a_dividend_in_the_ira_counts_it_again_for_good(client, accounts):
    dividends = client.get("/api/local/dividends/2026").json()["dividends"]
    kept = next(d for d in dividends if not d["taxed"])
    assert client.post(f"/api/local/dividends/{kept['id']}/dismiss").status_code == 204
    month = summary(client)
    assert month["income_cents"] == 1234  # the payment has no category now: unassigned money in
    assert month["unassigned_in_cents"] == 500
    assert client.post("/api/local/dividends/find").json()["found"] == 0
