"""Checking deposit sweeps by hand: free sweep lines, their possible matches, Link and Unlink.
Fake numbers only."""

import pytest

SWEEPS = "/api/local/stocks/sweeps"
TRADE = "FAKECO INC UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION"
SWEEP = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"


@pytest.fixture
def brokerage(make_account) -> int:
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def check(client) -> dict:
    return client.get(SWEEPS).json()


def waiting(client) -> list[str]:
    items = client.get("/api/local/transactions", params={"uncategorized": "true"}).json()
    return [t["description"] for t in items["items"]]


def link(client, sweep_id: int, match: dict, confirm: bool = False):
    body = {"kind": match["kind"], "record_id": match["record_id"], "confirm": confirm}
    return client.post(f"{SWEEPS}/{sweep_id}/link", json=body)


def test_a_sweep_a_week_late_is_listed_with_its_trade_and_can_be_linked(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(brokerage, 50_000, date="2026-10-09", description=SWEEP)
    assert waiting(client) == [SWEEP]  # too late for the finder

    [line] = check(client)["unlinked"]
    assert line["transaction_id"] == sweep["id"]
    [match] = line["matches"]
    assert (match["kind"], match["exact"], match["days_apart"]) == ("trade", True, 7)
    [account] = check(client)["accounts"]
    assert (account["payments"], account["with_sweep"], account["free_sweeps"]) == (1, 0, 1)

    assert link(client, sweep["id"], match).status_code == 204
    after = check(client)
    assert after["unlinked"] == []
    assert after["accounts"][0]["with_sweep"] == 1
    assert waiting(client) == []


def test_a_few_cents_off_is_offered_but_not_as_exact(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(brokerage, 49_995, date="2026-10-02", description=SWEEP)
    [match] = check(client)["unlinked"][0]["matches"]
    assert (match["exact"], match["gap_cents"]) == (False, 5)
    refused = link(client, sweep["id"], match)
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "confirm_gap")
    assert link(client, sweep["id"], match, confirm=True).status_code == 204


def test_exact_amounts_come_first(client, brokerage, add_txn):
    add_txn(brokerage, -49_990, date="2026-10-08", description=TRADE)
    add_txn(brokerage, -50_000, date="2026-10-01", description=TRADE)
    add_txn(brokerage, 50_000, date="2026-10-12", description=SWEEP)
    matches = check(client)["unlinked"][0]["matches"]
    assert [m["amount_cents"] for m in matches] == [-50_000, -49_990]


def test_a_sweep_in_another_account_cant_be_linked(client, brokerage, make_account, add_txn):
    checking = make_account(name="Fake Checking", kind="checking")["id"]
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(checking, 50_000, date="2026-10-02", description=SWEEP)
    lines = {line["transaction_id"]: line for line in check(client)["unlinked"]}
    assert lines[sweep["id"]]["matches"] == []  # only the same account is offered
    [trade] = client.get("/api/local/stocks/bank-trades").json()["items"]
    answer = link(client, sweep["id"], {"kind": "trade", "record_id": trade["id"]})
    assert (answer.status_code, answer.json()["error"]["code"]) == (409, "other_account")


def test_a_taken_sweep_or_a_trade_with_one_is_refused(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    found = add_txn(brokerage, 50_000, date="2026-10-02", description=SWEEP)  # the finder links it
    spare = add_txn(brokerage, 50_000, date="2026-10-10", description=SWEEP)
    [trade] = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert trade["sweep_transaction_id"] == found["id"]
    match = {"kind": "trade", "record_id": trade["id"]}

    answer = link(client, spare["id"], match)
    assert (answer.status_code, answer.json()["error"]["code"]) == (409, "has_sweep")
    answer = link(client, found["id"], match)
    assert (answer.status_code, answer.json()["error"]["code"]) == (409, "not_free")


def test_unlink_frees_a_sweep_you_linked(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(brokerage, 50_000, date="2026-10-14", description=SWEEP)
    [match] = check(client)["unlinked"][0]["matches"]
    link(client, sweep["id"], match)

    assert client.post(f"{SWEEPS}/{sweep['id']}/unlink").status_code == 204
    assert [line["transaction_id"] for line in check(client)["unlinked"]] == [sweep["id"]]
    assert client.post(f"{SWEEPS}/{sweep['id']}/unlink").status_code == 404


def test_a_dividend_can_be_linked_too(client, brokerage, add_txn):
    add_txn(brokerage, 1_234, date="2026-10-02", description="FAKECO CASH DIV ON 10 SHS")
    sweep = add_txn(brokerage, -1_234, date="2026-10-10", description="FAKE DEPOSIT SWEEP")
    [match] = check(client)["unlinked"][0]["matches"]
    assert match["kind"] == "dividend"
    assert link(client, sweep["id"], match).status_code == 204
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    assert dividend["sweep_transaction_id"] == sweep["id"]


def month(client, value: str) -> dict:
    return client.get("/api/local/summary/monthly", params={"month": value}).json()


def refused_code(client, sweep_id: int, kind: str, record_id: int) -> str:
    body = {"kind": kind, "record_id": record_id, "confirm": True}
    answer = client.post(f"{SWEEPS}/{sweep_id}/link", json=body)
    assert answer.status_code == 409
    return answer.json()["error"]["code"]


def only_trade(client) -> int:
    [trade] = client.get("/api/local/stocks/bank-trades").json()["items"]
    return trade["id"]


@pytest.mark.parametrize(
    ("amount", "code"),
    [(-50_000, "same_direction"), (49_000, "too_different")],  # $10 off a $500 trade
)
def test_a_sweep_that_cant_be_the_same_money_is_refused(client, brokerage, add_txn, amount, code):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(brokerage, amount, date="2026-10-02", description=SWEEP)
    assert check(client)["unlinked"][0]["matches"] == []  # not offered either
    assert refused_code(client, sweep["id"], "trade", only_trade(client)) == code


def test_fourteen_days_apart_is_offered_fifteen_is_not(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2028-02-29", description=TRADE)
    near = add_txn(brokerage, 50_000, date="2028-03-14", description=SWEEP)
    far = add_txn(brokerage, 50_000, date="2028-03-15", description=SWEEP)
    lines = {line["transaction_id"]: line["matches"] for line in check(client)["unlinked"]}
    assert [m["days_apart"] for m in lines[near["id"]]] == [14]
    assert lines[far["id"]] == []
    assert refused_code(client, far["id"], "trade", only_trade(client)) == "too_far"


def test_a_hand_link_with_a_gap_leaves_the_sweep_out_of_the_budget(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    sweep = add_txn(brokerage, 49_995, date="2026-10-09", description=SWEEP)
    assert month(client, "2026-10")["unassigned_count"] == 1
    [match] = check(client)["unlinked"][0]["matches"]
    link(client, sweep["id"], match, confirm=True)
    totals = month(client, "2026-10")
    assert (totals["unassigned_count"], totals["income_cents"]) == (0, 0)


def test_a_dividend_sweep_linked_by_hand_stays_out_even_with_a_category(client, brokerage, add_txn):
    add_txn(brokerage, 1_000, date="2026-10-02", description="FAKECO CASH DIV ON 10 SHS")
    sweep = add_txn(brokerage, -1_000, date="2026-10-10", description="FAKE DEPOSIT SWEEP")
    saving = next(c for c in client.get("/api/local/categories").json() if c["group"] == "savings")
    client.patch(f"/api/local/transactions/{sweep['id']}", json={"category_id": saving["id"]})
    [match] = check(client)["unlinked"][0]["matches"]
    link(client, sweep["id"], match)
    totals = month(client, "2026-10")
    assert (totals["income_cents"], totals["saved_cents"]) == (1_000, 0)


def test_a_retirement_dividend_linked_by_hand_stays_out(client, make_account, add_txn):
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    add_txn(ira, 1_000, date="2026-10-02", description="FAKECO CASH DIV ON 10 SHS")
    sweep = add_txn(ira, -1_000, date="2026-10-12", description="FAKE DEPOSIT SWEEP")
    [match] = check(client)["unlinked"][0]["matches"]
    link(client, sweep["id"], match)
    totals = month(client, "2026-10")
    assert (totals["income_cents"], totals["unassigned_count"]) == (0, 0)


def test_match_everything_again_keeps_a_hand_link(client, brokerage, add_txn):
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    by_hand = add_txn(brokerage, 50_000, date="2026-10-12", description=SWEEP)
    [match] = check(client)["unlinked"][0]["matches"]
    link(client, by_hand["id"], match)
    exact = add_txn(brokerage, 50_000, date="2026-10-03", description=SWEEP)  # fits the finder

    client.post("/api/local/transactions/match-again")
    [trade] = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert trade["sweep_transaction_id"] == by_hand["id"]
    assert [line["transaction_id"] for line in check(client)["unlinked"]] == [exact["id"]]


def test_unlink_frees_a_whole_group(client, brokerage, add_txn):
    other = TRADE.replace("FAKECO", "OTHERCO")
    add_txn(brokerage, -50_000, date="2026-10-02", description=TRADE)
    add_txn(brokerage, -30_000, date="2026-10-02", description=other)
    sweep = add_txn(brokerage, 80_000, date="2026-10-02", description=SWEEP)
    client.post("/api/local/stocks/bank-trades/find")  # one sweep for both
    trades = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert {t["sweep_transaction_id"] for t in trades} == {sweep["id"]}

    assert client.post(f"{SWEEPS}/{sweep['id']}/unlink").status_code == 204
    trades = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert {t["sweep_transaction_id"] for t in trades} == {None}
