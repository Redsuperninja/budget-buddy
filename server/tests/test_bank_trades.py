"""Stock trades named in a bank-style file (like J.P. Morgan / Chase), linked with their deposit
sweeps, kept out of the budget, and recorded with a ticker and shares. Fake numbers only."""

import pytest
from csv_helpers import ok, send

TRADES = "/api/local/stocks/bank-trades"
TRADE_LINE = (
    "ABBOTT LABORATORIES UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A "
    "COMMISSION EQUIVALENT - DETAILS ON REQUEST ROM"
)
FILE = (
    "Date,Description,Amount\r\n"
    f"10/01/2026,{TRADE_LINE},-1234.56\r\n"
    "10/01/2026,CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY WITHDRWAL,1234.56\r\n"
    "10/02/2026,KENVUE INC COMMON STOCK CASH DIV ON 1 SHS REC 09/21/26 PAY 10/02/26,0.21\r\n"
    "10/02/2026,CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY DEPOSIT,-0.21\r\n"
)


@pytest.fixture
def ira(make_account) -> int:
    return make_account(name="Fake IRA", kind="retirement")["id"]


@pytest.fixture
def brokerage(make_account) -> int:
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def trades(client) -> list[dict]:
    return client.get(TRADES).json()["items"]


def by_description(client, account_id) -> dict[str, dict]:
    items = client.get("/api/local/transactions", params={"account_id": account_id}).json()
    return {t["description"]: t for t in items["items"]}


def test_a_buy_and_its_sweep_are_linked_and_listed(client, ira):
    result = ok(send(client, ira, FILE, "commit"))
    assert (result["trades_found"], result["trade_sweeps_linked"]) == (1, 1)
    assert (result["dividends_found"], result["dividend_sweeps_linked"]) == (1, 1)

    [trade] = trades(client)
    rows = by_description(client, ira)
    assert trade["security"] == "ABBOTT LABORATORIES"
    assert trade["side"] == "buy"
    assert trade["amount_cents"] == 123456
    assert trade["date"] == "2026-10-01"
    assert trade["recorded"] is False
    assert trade["transaction_id"] == rows[TRADE_LINE]["id"]
    sweep = rows["CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY WITHDRWAL"]
    assert trade["sweep_transaction_id"] == sweep["id"]


def test_trades_and_sweeps_need_no_category_and_stay_out_of_the_budget(client, brokerage):
    ok(send(client, brokerage, FILE, "commit"))
    waiting = client.get("/api/local/transactions", params={"uncategorized": "true"}).json()
    assert waiting["items"] == []  # the trade, its sweep and the dividend's sweep
    summary = client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()
    assert summary["spending_cents"] == 0
    assert summary["income_cents"] == 21  # the dividend, in a taxable account


def test_recording_shares_shows_the_price_and_remembers_the_ticker(client, ira):
    ok(send(client, ira, FILE, "commit"))
    [trade] = trades(client)
    lot = {"transaction_id": trade["transaction_id"], "symbol": "ABT", "acquired_on": "2026-10-01",
           "shares": "10", "cost_basis_cents": 123456}  # fmt: skip
    assert client.post("/api/local/stocks/lots", json=lot).status_code == 201

    [trade] = trades(client)
    assert (trade["recorded"], trade["symbol"], trade["shares_micro"]) == (True, "ABT", 10_000_000)
    assert trade["price_cents"] == 12346  # $1,234.56 / 10, rounded to the cent

    later = (
        "Date,Description,Amount\r\n"
        f"10/20/2026,{TRADE_LINE},-500.00\r\n"
        "10/21/2026,CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY WITHDRWAL,500.00\r\n"
    )
    ok(send(client, ira, later, "commit"))
    newest = trades(client)[0]
    assert (newest["date"], newest["suggested_symbol"], newest["recorded"]) == (
        "2026-10-20", "ABT", False)  # fmt: skip
    assert newest["sweep_transaction_id"] is not None


def test_a_sale_links_the_sweep_that_parks_the_money(client, ira):
    body = (
        "Date,Description,Amount\r\n"
        f"10/05/2026,{TRADE_LINE},800.00\r\n"
        "10/05/2026,CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY DEPOSIT,-800.00\r\n"
    )
    ok(send(client, ira, body, "commit"))
    [trade] = trades(client)
    assert trade["side"] == "sell"
    assert trade["sweep_transaction_id"] is not None


def test_not_a_trade_frees_the_sweep_and_is_remembered(client, ira):
    ok(send(client, ira, FILE, "commit"))
    [trade] = trades(client)
    assert client.post(f"{TRADES}/{trade['id']}/dismiss").status_code == 204
    assert trades(client) == []
    assert client.post(f"{TRADES}/find").json() == {"found": 0, "sweeps_linked": 0}


def test_find_looks_through_older_transactions(client, ira, add_txn):
    add_txn(ira, -50_000, date="2026-10-01", description=TRADE_LINE)
    add_txn(ira, 50_000, date="2026-10-02", description="FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL")
    assert len(trades(client)) == 1  # found as each was added
    assert client.post(f"{TRADES}/find").json() == {"found": 0, "sweeps_linked": 0}


@pytest.mark.parametrize(
    ("description", "kind", "expected"),
    [
        (TRADE_LINE, "retirement", True),
        ("YOU BOUGHT FAKE FUND (FAKE)", "brokerage", True),
        ("FAKE GARAGE SALE SOLD ITEMS", "checking", False),  # not an investment account
        ("CHASE DEPOSIT SWEEP JPMORGAN CHASE BANK NA INTRA-DAY WITHDRWAL", "retirement", False),
        ("KENVUE INC COMMON STOCK CASH DIV ON 1 SHS", "retirement", False),  # a dividend
        # A cancelled or corrected trade reverses money; it isn't the opposite trade.
        (f"CXL {TRADE_LINE}", "retirement", False),
        (f"{TRADE_LINE} CORRECTION", "retirement", False),
        # Cash funds and bonds coming due aren't stock trades.
        ("YOU BOUGHT JPMORGAN US GOVT MMKT", "brokerage", False),
        ("SOLD TO COVER FAKECO", "brokerage", False),
        ("FAKE BOND SOLD AT MATURITY", "brokerage", False),
    ],
)
def test_what_counts_as_a_trade(client, make_account, add_txn, description, kind, expected):
    account = make_account(kind=kind)["id"]
    add_txn(account, -10_000, date="2026-10-01", description=description)
    assert bool(trades(client)) is expected


def test_the_ticker_in_brackets_is_offered(client, brokerage, add_txn):
    add_txn(brokerage, -40_000, date="2026-01-05", description="YOU BOUGHT FAKE FUND (FAKE)")
    [trade] = trades(client)
    assert (trade["security"], trade["suggested_symbol"]) == ("FAKE FUND", "FAKE")
