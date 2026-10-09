"""Categories API and the monthly income/spending summary. Fake data only."""

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category

CATS = "/api/local/categories"
SUMMARY = "/api/local/summary/monthly"


def cid(client, name):
    with SessionLocal(bind=client.app.state.engine) as session:
        return session.scalar(select(Category.id).where(Category.name == name))


def summary(client, month="2026-01"):
    response = client.get(SUMMARY, params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def unassigned(s):
    return (s["unassigned_in_cents"], s["unassigned_out_cents"], s["unassigned_count"])


@pytest.fixture
def accounts(make_account):
    return make_account()["id"], make_account(name="Savings", kind="savings")["id"]


def test_category_list_add_rename_budget(client):
    starter = client.get(CATS).json()
    assert {"Groceries", "Paycheck", "Transfer"} <= {c["name"] for c in starter}

    created = client.post(CATS, json={"name": "  Pets ", "group": "wants", "budget_cents": 5_000})
    assert created.status_code == 201
    pets = created.json()
    assert (pets["name"], pets["group"], pets["budget_cents"]) == ("Pets", "wants", 5_000)

    renamed = client.patch(f"{CATS}/{pets['id']}", json={"name": "Pet care"})
    assert renamed.json()["name"] == "Pet care"
    assert renamed.json()["budget_cents"] == 5_000
    budgeted = client.patch(f"{CATS}/{pets['id']}", json={"budget_cents": 0})
    assert budgeted.json()["budget_cents"] == 0
    assert client.get(f"{CATS}/{pets['id']}").json()["name"] == "Pet care"


def test_transfer_group_cannot_be_created(client):
    response = client.post(CATS, json={"name": "Moves", "group": "transfer"})
    assert response.status_code == 422
    assert (
        "Transfer is a built-in category. Pick needs, wants, savings, or income."
        in response.json()["error"]["message"]
    )


def test_name_unique_by_casefold(client):
    assert client.post(CATS, json={"name": "Stra\u00dfe", "group": "wants"}).status_code == 201
    dup = client.post(CATS, json={"name": "STRASSE", "group": "wants"})
    assert (dup.status_code, dup.json()["error"]["code"]) == (409, "name_taken")


def test_database_duplicate_becomes_name_taken(client, monkeypatch):
    from app.services import categories

    monkeypatch.setattr(categories, "_check_name_free", lambda *a, **k: None)
    dup = client.post(CATS, json={"name": "Groceries", "group": "needs"})
    assert (dup.status_code, dup.json()["error"]["code"]) == (409, "name_taken")


def test_category_rules(client):
    groceries = cid(client, "Groceries")
    dup = client.post(CATS, json={"name": "groceries", "group": "needs"})
    assert (dup.status_code, dup.json()["error"]["code"]) == (409, "name_taken")
    clash = client.patch(f"{CATS}/{cid(client, 'Utilities')}", json={"name": "GROCERIES"})
    assert clash.status_code == 409
    # Renaming to its own name (different case) is fine.
    assert client.patch(f"{CATS}/{groceries}", json={"name": "GROCERIES"}).status_code == 200

    group_text = "A category's group can't be changed. Make a new category instead."
    cases = (
        ({"budget_cents": -1}, "The budget can't be negative."),
        ({"budget_cents": 12.5}, "whole cents"),
        ({"budget_cents": "5"}, "whole cents"),
        ({"group": "income"}, group_text),
        ({"name": None}, "name can't be empty"),
        ({"name": "  "}, "name"),
    )
    for body, text in cases:
        response = client.patch(f"{CATS}/{groceries}", json=body)
        assert response.status_code == 422, body
        assert text in response.json()["error"]["message"], body
    bad = client.post(CATS, json={"name": "X", "group": "bogus"})
    assert bad.status_code == 422
    negative = client.post(CATS, json={"name": "X", "group": "needs", "budget_cents": -5})
    assert negative.status_code == 422
    assert "The budget can't be negative." in negative.json()["error"]["message"]
    fraction = client.post(CATS, json={"name": "X", "group": "needs", "budget_cents": 1.5})
    assert "whole cents" in fraction.json()["error"]["message"]
    assert client.get(f"{CATS}/9999").status_code == 404
    assert client.patch(f"{CATS}/9999", json={"name": "Y"}).json()["error"]["code"] == "not_found"


def test_summary_counts_only_income_and_spending(client, add_txn, accounts):
    checking, savings = accounts
    pay, groceries = cid(client, "Paycheck"), cid(client, "Groceries")
    dining, retire = cid(client, "Dining Out"), cid(client, "Retirement")
    client.patch(f"{CATS}/{groceries}", json={"budget_cents": 40_000})
    client.patch(f"{CATS}/{dining}", json={"budget_cents": 10_000})

    add_txn(checking, 500_000, kind="adjustment")  # opening balance: not income
    add_txn(checking, 300_000, category_id=pay)
    add_txn(checking, -12_000, category_id=groceries)
    add_txn(checking, -3_000, category_id=dining)
    add_txn(checking, 2_000, category_id=groceries, kind="refund")  # lowers spending
    add_txn(checking, -50_000, category_id=retire)
    add_txn(checking, -9_999, kind="adjustment")  # balance fix: not spending
    # A linked transfer is neither income nor spending (into savings, it counts as saved).
    out = add_txn(checking, -70_000, category_id=groceries)
    into = add_txn(savings, 70_000)
    link = client.post(
        f"/api/local/transactions/{out['id']}/transfer", json={"other_id": into["id"]}
    )
    assert link.is_success

    s = summary(client)
    assert s["month"] == "2026-01"
    assert s["income_cents"] == 300_000
    assert s["spending_cents"] == 12_000 - 2_000 + 3_000  # 13_000
    assert s["saved_cents"] == 50_000 + 70_000  # the move into savings counts as saved (10b)
    assert s["saved_by_transfer_cents"] == 70_000
    assert s["spending_budget_cents"] == 50_000
    assert unassigned(s) == (0, 0, 0)
    by_name = {c["name"]: c for c in s["categories"]}
    assert by_name["Groceries"]["actual_cents"] == 10_000
    assert by_name["Groceries"]["budget_cents"] == 40_000
    assert by_name["Paycheck"]["actual_cents"] == 300_000
    assert "Transfer" not in by_name
    groups = {g["group"]: g for g in s["groups"]}
    assert groups["needs"]["actual_cents"] == 10_000
    assert groups["wants"]["actual_cents"] == 3_000
    assert groups["income"]["actual_cents"] == 300_000


def test_refunds_can_exceed_spending(client, add_txn, accounts):
    add_txn(accounts[0], 4_000, category_id=cid(client, "Shopping"), kind="refund")
    s = summary(client)
    assert s["spending_cents"] == -4_000
    assert s["income_cents"] == 0


def test_refund_is_never_income(client, add_txn, accounts):
    add_txn(accounts[0], 1_000, category_id=cid(client, "Paycheck"), kind="refund")
    add_txn(accounts[0], 2_000, kind="refund")  # no category
    s = summary(client)
    assert s["income_cents"] == 0
    assert s["spending_cents"] == 0
    assert unassigned(s) == (3_000, 0, 2)


def test_uncategorized_is_reported_not_guessed(client, add_txn, accounts):
    add_txn(accounts[0], -2_500)
    add_txn(accounts[0], 500)
    s = summary(client)
    assert (s["income_cents"], s["spending_cents"]) == (0, 0)
    assert unassigned(s) == (500, 2_500, 2)


def test_unlinked_transfer_gets_its_old_category_back(client, add_txn, accounts):
    out = add_txn(accounts[0], -1_000)
    into = add_txn(accounts[1], 1_000)
    base = f"/api/local/transactions/{out['id']}"
    client.post(f"{base}/transfer", json={"other_id": into["id"]})
    assert summary(client)["unassigned_count"] == 0  # linked: not income or spending
    assert client.delete(f"{base}/transfer").is_success
    # They had no category before the link, so they're waiting to be sorted again.
    s = summary(client)
    assert (s["income_cents"], s["spending_cents"], s["unassigned_count"]) == (0, 0, 2)


@pytest.mark.parametrize(
    ("month", "dates", "expected"),
    [
        ("2026-01", ["2025-12-31", "2026-01-01", "2026-01-31", "2026-02-01"], 2_000),
        ("2026-02", ["2026-01-31", "2026-02-01", "2026-02-28", "2026-03-01"], 2_000),
        ("2024-02", ["2024-02-29", "2024-03-01"], 1_000),  # leap day
        ("2025-12", ["2025-12-31", "2026-01-01", "2025-11-30"], 1_000),  # year rollover
    ],
)
def test_month_boundaries(client, add_txn, accounts, month, dates, expected):
    groceries = cid(client, "Groceries")
    for date in dates:
        add_txn(accounts[0], -1_000, date=date, category_id=groceries)
    assert summary(client, month)["spending_cents"] == expected


@pytest.mark.parametrize(
    "month",
    [
        "",
        "2026-13",
        "2026-00",
        "2026-1",
        "26-01",
        "2026-01-15",
        "x",
        "9999-12",
        "1899-12",
        "2026-01\n",
    ],
)
def test_bad_month_is_refused(client, month):
    response = client.get(SUMMARY, params={"month": month})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["message"] == "Enter the month as year-month, like 2026-01."


def test_month_is_required(client):
    response = client.get(SUMMARY)
    assert response.status_code == 422
    assert "year-month" in response.json()["error"]["message"]


def test_earliest_and_latest_months_work(client):
    assert summary(client, "9998-12")["month"] == "9998-12"
    assert summary(client, "1900-01")["month"] == "1900-01"


def test_negative_income_lowers_income(client, add_txn, accounts):
    pay = cid(client, "Paycheck")
    add_txn(accounts[0], 100_000, category_id=pay)
    add_txn(accounts[0], -15_000, category_id=pay)  # e.g. pay clawback
    assert summary(client)["income_cents"] == 85_000


def test_refund_in_savings_lowers_saved(client, add_txn, accounts):
    retire = cid(client, "Retirement")
    add_txn(accounts[0], -30_000, category_id=retire)
    add_txn(accounts[0], 5_000, category_id=retire, kind="refund")
    s = summary(client)
    assert s["saved_cents"] == 25_000
    assert s["spending_cents"] == 0


def test_refund_under_transfer_category_is_unassigned(client, add_txn, accounts):
    add_txn(accounts[0], 700, category_id=cid(client, "Transfer"), kind="refund")
    s = summary(client)
    assert unassigned(s) == (700, 0, 1)
    assert (s["income_cents"], s["spending_cents"], s["saved_cents"]) == (0, 0, 0)


def test_savings_budgets_appear_in_groups_and_income_has_none(client):
    refused = client.patch(f"{CATS}/{cid(client, 'Paycheck')}", json={"budget_cents": 400_000})
    assert refused.status_code == 422
    assert "measured against" in refused.json()["error"]["message"]
    assert client.patch(f"{CATS}/{cid(client, 'Paycheck')}", json={"budget_cents": 0}).is_success
    client.patch(f"{CATS}/{cid(client, 'Retirement')}", json={"budget_cents": 50_000})
    groups = {g["group"]: g for g in summary(client)["groups"]}
    assert groups["income"]["budget_cents"] == 0
    assert groups["savings"]["budget_cents"] == 50_000
    assert groups["savings"]["actual_cents"] == 0


def test_category_without_activity_shows_zero(client):
    rows = summary(client)["categories"]
    assert rows
    assert all(c["actual_cents"] == 0 for c in rows)


def test_empty_month(client):
    s = summary(client, "2030-06")
    assert (s["income_cents"], s["spending_cents"], s["saved_cents"]) == (0, 0, 0)


@pytest.mark.parametrize("peer", ["192.168.1.50", "10.0.0.7"])
def test_home_network_cannot_reach_these_routes(make_client, peer):
    other = make_client(peer=peer)
    assert other.get(CATS).status_code == 403
    assert other.get(SUMMARY, params={"month": "2026-01"}).status_code == 403
    assert other.post(CATS, json={"name": "Z", "group": "needs"}).status_code == 403


def test_category_write_needs_matching_origin(make_client):
    c = make_client(headers={"Origin": "http://evil.example"})
    assert c.post(CATS, json={"name": "Z", "group": "needs"}).status_code == 403
    assert c.get(CATS).status_code == 200
