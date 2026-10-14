"""One deposit sweep that pays for several trades or dividends at once. Fake numbers only."""

import pytest
from csv_helpers import ok, send

TRADES = "/api/local/stocks/bank-trades"
TRADE = "FAKECO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION"
OTHER = "OTHERCO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION"
SWEEP_IN = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"
SWEEP_OUT = "FAKE DEPOSIT SWEEP INTRA-DAY DEPOSIT"


@pytest.fixture
def brokerage(make_account) -> int:
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def waiting(client) -> list[str]:
    items = client.get("/api/local/transactions", params={"uncategorized": "true"}).json()
    return sorted(t["description"] for t in items["items"])


def trades(client) -> list[dict]:
    return client.get(TRADES).json()["items"]


def test_two_buys_paid_by_one_sweep(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        f"10/02/2026,{TRADE},-500.00\r\n"
        f"10/02/2026,{OTHER},-300.00\r\n"
        f"10/02/2026,{SWEEP_IN},800.00\r\n"
    )
    result = ok(send(client, brokerage, body, "commit"))
    assert (result["trades_found"], result["trade_sweeps_linked"]) == (2, 1)
    sweeps = {t["sweep_transaction_id"] for t in trades(client)}
    assert len(sweeps) == 1 and None not in sweeps
    assert waiting(client) == []
    month = client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()
    assert month["unassigned_count"] == 0


def test_a_dividend_and_a_sale_swept_together(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        "10/03/2026,FAKECO INC CASH DIV ON 10 SHS,12.34\r\n"
        f"10/03/2026,{TRADE},300.00\r\n"
        f"10/03/2026,{SWEEP_OUT},-312.34\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    [trade] = trades(client)
    assert dividend["sweep_transaction_id"] == trade["sweep_transaction_id"] is not None
    assert waiting(client) == []


def test_an_exact_sweep_is_still_picked_first(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        f"10/02/2026,{TRADE},-500.00\r\n"
        f"10/02/2026,{OTHER},-300.00\r\n"
        f"10/02/2026,{SWEEP_IN},500.00\r\n"
        f"10/02/2026,{SWEEP_IN},300.00\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    assert len({t["sweep_transaction_id"] for t in trades(client)}) == 2


def test_amounts_that_dont_add_up_are_left_alone(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        f"10/02/2026,{TRADE},-500.00\r\n"
        f"10/02/2026,{OTHER},-300.00\r\n"
        f"10/02/2026,{SWEEP_IN},799.99\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    assert all(t["sweep_transaction_id"] is None for t in trades(client))
    assert waiting(client) == [SWEEP_IN]


def test_not_a_trade_frees_the_sweep_from_the_whole_group(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        f"10/02/2026,{TRADE},-500.00\r\n"
        f"10/02/2026,{OTHER},-300.00\r\n"
        f"10/02/2026,{SWEEP_IN},800.00\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    first = trades(client)[0]
    assert client.post(f"{TRADES}/{first['id']}/dismiss").status_code == 204
    [other] = trades(client)
    assert other["sweep_transaction_id"] is None  # $300 alone doesn't add up to $800
    assert SWEEP_IN in waiting(client)


def test_a_mixed_group_when_the_broker_nets_the_day(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        f"10/02/2026,{TRADE},-812.00\r\n"
        "10/02/2026,FAKECO INC CASH DIV ON 10 SHS,12.00\r\n"
        f"10/02/2026,{SWEEP_IN},800.00\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    assert dividend["sweep_transaction_id"] == trades(client)[0]["sweep_transaction_id"] is not None


def test_not_a_dividend_frees_the_sweep_from_the_group(client, brokerage):
    body = (
        "Date,Description,Amount\r\n"
        "10/03/2026,FAKECO INC CASH DIV ON 10 SHS,12.34\r\n"
        f"10/03/2026,{TRADE},300.00\r\n"
        f"10/03/2026,{SWEEP_OUT},-312.34\r\n"
    )
    ok(send(client, brokerage, body, "commit"))
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    assert client.post(f"/api/local/dividends/{dividend['id']}/dismiss").status_code == 204
    assert trades(client)[0]["sweep_transaction_id"] is None
    assert SWEEP_OUT in waiting(client)


def test_deleting_a_member_frees_the_sweep(client, brokerage, add_txn):
    first = add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    add_txn(brokerage, -30_000, date="2026-10-02", description=OTHER)
    add_txn(brokerage, 80_000, date="2026-10-02", description=SWEEP_IN)
    assert all(t["sweep_transaction_id"] for t in trades(client))
    assert client.delete(f"/api/local/transactions/{first['id']}").status_code == 204
    assert [t["sweep_transaction_id"] for t in trades(client)] == [None]
    assert SWEEP_IN in waiting(client)


def test_too_many_nearby_is_left_alone(client, brokerage, add_txn):
    for n in range(11):
        add_txn(brokerage, -(1_000 + n), date="2026-10-02", description=f"{TRADE} {n}")
    add_txn(brokerage, 2_001, date="2026-10-02", description=SWEEP_IN)  # 1000 + 1001
    assert all(t["sweep_transaction_id"] is None for t in trades(client))
