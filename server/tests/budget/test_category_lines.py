"""Category lines (ADR-0017, roadmap 10f-2): a split transaction counts per part in the summary,
spending pace and category filter; with no splits nothing changes. Fake data only."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category
from app.services.budget.category_lines import category_lines

SUMMARY = "/api/local/summary/monthly"
PACE = "/api/local/summary/pace"
TXNS = "/api/local/transactions"


@pytest.fixture
def checking(make_account):
    return make_account()["id"]


@pytest.fixture
def cats(client):
    with Session(client.app.state.engine) as session:
        return {c.name: c.id for c in session.scalars(select(Category))}


def month(client):
    return client.get(SUMMARY, params={"month": "2026-01"}).json()


def actuals(summary):
    return {c["name"]: c["actual_cents"] for c in summary["categories"]}


def split(client, txn_id, parts):
    body = {"splits": [{"category_id": c, "amount_cents": a, "note": None} for c, a in parts]}
    assert client.put(f"{TXNS}/{txn_id}/splits", json=body).status_code == 200


def ledger(add_txn, checking, cats):
    add_txn(checking, 300_000, category_id=cats["Paycheck"])
    big = add_txn(checking, -10_000, category_id=cats["Groceries"], date="2026-01-10")
    add_txn(checking, -2_500, category_id=cats["Dining Out"], date="2026-01-12")
    add_txn(checking, 1_000, kind="refund", category_id=cats["Shopping"], date="2026-01-20")
    add_txn(checking, -700, date="2026-01-21")
    return big


def test_no_splits_is_identical_to_a_part_into_one_category(client, add_txn, checking, cats):
    big = ledger(add_txn, checking, cats)
    before, pace_before = month(client), client.get(PACE, params={"month": "2026-01"}).json()
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Groceries"], -4_000)])
    assert month(client) == before
    assert client.get(PACE, params={"month": "2026-01"}).json() == pace_before


def test_split_counts_per_part_and_grand_total_is_unchanged(client, add_txn, checking, cats):
    big = ledger(add_txn, checking, cats)
    before = month(client)
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Shopping"], -4_000)])
    after = month(client)
    was, now = actuals(before), actuals(after)
    assert now["Groceries"] == was["Groceries"] - 4_000
    assert now["Shopping"] == was["Shopping"] + 4_000
    assert {k: v for k, v in now.items() if k not in ("Groceries", "Shopping")} == {
        k: v for k, v in was.items() if k not in ("Groceries", "Shopping")
    }
    assert after["spending_cents"] == before["spending_cents"]
    assert after["unassigned_count"] == before["unassigned_count"]


def test_pace_follows_the_parts(client, add_txn, checking, cats):
    big = add_txn(checking, -10_000, category_id=cats["Groceries"], date="2026-01-10")
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Paycheck"], -4_000)])
    pace = client.get(PACE, params={"month": "2026-01"}).json()
    assert pace["days"][9]["spent_cents"] == 6_000  # the income-category part isn't spending
    assert month(client)["spending_cents"] == 6_000


def test_a_part_in_the_transfer_group_is_ignored(client, add_txn, checking, cats):
    big = add_txn(checking, -10_000, date="2026-01-10")
    split(client, big["id"], [(cats["Groceries"], -3_000), (cats["Transfer"], -7_000)])
    s = month(client)
    assert s["spending_cents"] == 3_000 and s["unassigned_count"] == 0


def test_an_unsorted_split_is_not_unassigned_and_parts_place_refunds(
    client, add_txn, checking, cats
):
    refund = add_txn(checking, 5_000, kind="refund", date="2026-01-11")
    split(client, refund["id"], [(cats["Groceries"], 2_000), (cats["Paycheck"], 3_000)])
    s = month(client)
    assert actuals(s)["Groceries"] == -2_000
    assert (s["unassigned_in_cents"], s["unassigned_count"]) == (3_000, 1)


def test_a_refund_split_into_two_unplaced_parts_counts_once(client, add_txn, checking, cats):
    refund = add_txn(checking, 5_000, kind="refund", date="2026-01-11")
    split(client, refund["id"], [(cats["Paycheck"], 2_000), (cats["Paycheck"], 3_000)])
    s = month(client)
    assert (s["unassigned_in_cents"], s["unassigned_count"]) == (5_000, 1)


def test_through_keeps_a_split_whole(client, add_txn, checking, cats):
    big = add_txn(checking, -10_000, category_id=cats["Groceries"], date="2026-01-10")
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Shopping"], -4_000)])
    early = client.get(SUMMARY, params={"month": "2026-01", "through": "2026-01-09"}).json()
    late = client.get(SUMMARY, params={"month": "2026-01", "through": "2026-01-10"}).json()
    assert early["spending_cents"] == 0
    assert late["spending_cents"] == 10_000


def test_category_filter_finds_a_split_by_any_part(client, add_txn, checking, cats):
    big = add_txn(checking, -10_000, category_id=cats["Groceries"])
    other = add_txn(checking, -100, category_id=cats["Shopping"])
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Shopping"], -4_000)])
    for name, expected in [("Groceries", {big["id"]}), ("Shopping", {big["id"], other["id"]})]:
        found = client.get(TXNS, params={"category_id": cats[name]}).json()["items"]
        assert {t["id"] for t in found} == expected
        assert len(found) == len(expected)  # a split is listed once
    assert client.get(TXNS, params={"category_id": cats["Dining Out"]}).json()["items"] == []


def test_lines_are_one_per_part_and_never_the_split_itself(client, add_txn, checking, cats):
    big = ledger(add_txn, checking, cats)
    split(client, big["id"], [(cats["Groceries"], -6_000), (cats["Shopping"], -4_000)])
    with Session(client.app.state.engine) as session:
        lines = category_lines()
        rows = session.execute(select(lines.c.transaction_id, lines.c.amount_cents)).all()
    mine = [amount for txn, amount in rows if txn == big["id"]]
    assert sorted(mine) == [-6_000, -4_000]
    assert len(rows) == 5 - 1 + 2
