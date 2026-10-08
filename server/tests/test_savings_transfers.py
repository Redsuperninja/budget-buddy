"""Transfers into your own savings accounts count as saved (roadmap 10b). Fake data only."""

import pytest
from test_categories_summary_api import cid, summary


@pytest.fixture
def move(client, make_account, add_txn):
    """Link a transfer of ``cents`` from one account to another, dated ``date``."""

    def link(source: int, target: int, cents: int, date: str = "2026-01-10") -> None:
        out = add_txn(source, -cents, date=date, category_id=None)
        into = add_txn(target, cents, date=date, category_id=None)
        url = f"/api/local/transactions/{out['id']}/transfer"
        assert client.post(url, json={"other_id": into["id"]}).status_code == 200

    return link


@pytest.fixture
def accts(make_account):
    names = ("checking", "savings", "brokerage", "retirement", "hsa", "credit_card", "loan")
    return {kind: make_account(name=kind, kind=kind)["id"] for kind in names}


def savings_group(s):
    return next(g for g in s["groups"] if g["group"] == "savings")


def test_transfers_into_savings_kinds_count_as_saved(client, move, accts, add_txn):
    add_txn(accts["checking"], 400_000, category_id=cid(client, "Paycheck"))
    move(accts["checking"], accts["savings"], 50_000)
    move(accts["checking"], accts["retirement"], 20_000)
    move(accts["checking"], accts["hsa"], 5_000)
    move(accts["checking"], accts["brokerage"], 10_000)
    add_txn(accts["checking"], -1_000, category_id=cid(client, "Emergency Fund"))

    s = summary(client)
    assert s["saved_by_transfer_cents"] == 85_000
    assert s["saved_cents"] == 86_000
    assert savings_group(s)["actual_cents"] == 86_000
    assert savings_group(s)["percent_of_income_bp"] == 2_150
    assert (s["income_cents"], s["spending_cents"]) == (400_000, 0)  # transfers stay out


def test_withdrawals_lower_saved(client, move, accts):
    move(accts["checking"], accts["savings"], 30_000)
    move(accts["savings"], accts["checking"], 45_000)
    s = summary(client)
    assert s["saved_by_transfer_cents"] == -15_000
    assert s["saved_cents"] == -15_000


def test_moves_that_are_not_new_saving_are_left_out(client, move, accts):
    move(accts["savings"], accts["brokerage"], 10_000)  # savings to savings
    move(accts["checking"], accts["credit_card"], 20_000)  # paying a card
    move(accts["checking"], accts["loan"], 30_000)  # paying a loan (issue #30)
    assert summary(client)["saved_by_transfer_cents"] == 0


def test_only_this_month_and_only_linked_transfers(client, move, accts, add_txn):
    move(accts["checking"], accts["savings"], 7_000, date="2025-12-31")
    move(accts["checking"], accts["savings"], 3_000, date="2026-02-01")
    add_txn(accts["savings"], 9_000, category_id=None)  # not linked: unsorted money in
    s = summary(client)
    assert s["saved_by_transfer_cents"] == 0
    assert summary(client, "2025-12")["saved_by_transfer_cents"] == 7_000


def test_unlinking_takes_it_back_out(client, move, accts):
    move(accts["checking"], accts["savings"], 5_000)
    first = client.get("/api/local/transactions", params={"kind": "transfer"}).json()["items"][0]
    assert client.delete(f"/api/local/transactions/{first['id']}/transfer").is_success
    assert summary(client)["saved_by_transfer_cents"] == 0
