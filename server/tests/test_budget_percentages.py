"""Percentage budgets and the planned monthly income they're shares of. Fake data only."""

import pytest
from test_categories_summary_api import CATS, cid, summary

PLAN = "/api/local/budget/plan"


def groups(s):
    return {g["group"]: g for g in s["groups"]}


def by_name(s):
    return {c["name"]: c for c in s["categories"]}


def test_plan_starts_empty_and_saves(client):
    assert client.get(PLAN).json() == {"planned_income_cents": None}
    assert client.put(PLAN, json={"planned_income_cents": 400_000}).json() == {
        "planned_income_cents": 400_000
    }
    assert client.get(PLAN).json()["planned_income_cents"] == 400_000
    assert client.put(PLAN, json={"planned_income_cents": None}).status_code == 200
    for bad in (-1, 1.5, "400000"):
        assert client.put(PLAN, json={"planned_income_cents": bad}).status_code == 422


def test_percentage_budget_uses_planned_income(client, checking, add_txn):
    rent = cid(client, "Rent/Mortgage")
    client.put(PLAN, json={"planned_income_cents": 400_000})
    updated = client.patch(f"{CATS}/{rent}", json={"budget_percent_bp": 3_000})
    assert (updated.json()["budget_percent_bp"], updated.json()["budget_cents"]) == (3_000, 0)
    add_txn(checking, 350_000, category_id=cid(client, "Paycheck"))

    s = summary(client)
    assert (s["budget_income_cents"], s["budget_income_source"]) == (400_000, "planned")
    assert by_name(s)["Rent/Mortgage"]["budget_cents"] == 120_000
    assert by_name(s)["Rent/Mortgage"]["budget_percent_bp"] == 3_000
    assert groups(s)["needs"]["budget_cents"] == 120_000
    assert s["spending_budget_cents"] == 120_000


def test_without_a_plan_percentages_follow_actual_income(client, checking, add_txn):
    client.patch(f"{CATS}/{cid(client, 'Groceries')}", json={"budget_percent_bp": 1_250})
    s = summary(client)
    assert (s["budget_income_cents"], s["budget_income_source"]) == (0, "actual")
    assert by_name(s)["Groceries"]["budget_cents"] == 0

    add_txn(checking, 300_001, category_id=cid(client, "Paycheck"))
    s = summary(client)
    assert s["budget_income_cents"] == 300_001
    assert by_name(s)["Groceries"]["budget_cents"] == 37_500  # 12.5%, rounded to the cent


def test_amount_and_percentage_switch_cleanly(client):
    dining = cid(client, "Dining Out")
    client.patch(f"{CATS}/{dining}", json={"budget_percent_bp": 500})
    back = client.patch(f"{CATS}/{dining}", json={"budget_cents": 15_000}).json()
    assert (back["budget_cents"], back["budget_percent_bp"]) == (15_000, None)
    again = client.patch(f"{CATS}/{dining}", json={"budget_percent_bp": 500}).json()
    assert (again["budget_cents"], again["budget_percent_bp"]) == (0, 500)
    cleared = client.patch(f"{CATS}/{dining}", json={"budget_percent_bp": None}).json()
    assert (cleared["budget_cents"], cleared["budget_percent_bp"]) == (0, None)


def test_create_with_percentage(client):
    made = client.post(CATS, json={"name": "Gym", "group": "wants", "budget_percent_bp": 200})
    assert made.status_code == 201
    assert (made.json()["budget_cents"], made.json()["budget_percent_bp"]) == (0, 200)


@pytest.mark.parametrize("bp", [0, -5, 10_001, 12.5, "1500", True])
def test_percentage_must_be_whole_basis_points_in_range(client, bp):
    response = client.patch(f"{CATS}/{cid(client, 'Travel')}", json={"budget_percent_bp": bp})
    assert response.status_code == 422
    assert "1500 is 15%" in response.json()["error"]["message"]


def test_amount_and_percentage_together_are_refused(client):
    both = {"budget_cents": 100, "budget_percent_bp": 100}
    patch = client.patch(f"{CATS}/{cid(client, 'Travel')}", json=both)
    post = client.post(CATS, json={"name": "Z", "group": "wants", **both})
    for response in (patch, post):
        assert response.status_code == 422
        assert "not both" in response.json()["error"]["message"]


def test_income_category_cannot_be_a_percentage(client):
    patch = client.patch(f"{CATS}/{cid(client, 'Paycheck')}", json={"budget_percent_bp": 100})
    post = client.post(CATS, json={"name": "Tips", "group": "income", "budget_percent_bp": 100})
    for response in (patch, post):
        assert response.status_code == 422
        assert "income category" in response.json()["error"]["message"]


def test_group_shares_of_income(client, checking, add_txn):
    add_txn(checking, 300_000, category_id=cid(client, "Paycheck"))
    add_txn(checking, -150_000, category_id=cid(client, "Rent/Mortgage"))
    add_txn(checking, -100_000, category_id=cid(client, "Dining Out"))
    add_txn(checking, -1, category_id=cid(client, "Emergency Fund"))
    g = groups(summary(client))
    assert g["needs"]["percent_of_income_bp"] == 5_000
    assert g["wants"]["percent_of_income_bp"] == 3_333
    assert g["savings"]["percent_of_income_bp"] == 0  # 1 cent of $3,000 rounds to 0.00%
    assert g["income"]["percent_of_income_bp"] is None


def test_no_income_means_no_shares(client, checking, add_txn):
    add_txn(checking, -5_000, category_id=cid(client, "Groceries"))
    assert groups(summary(client))["needs"]["percent_of_income_bp"] is None


def test_phone_snapshot_gets_the_worked_out_budget(client):
    from app.db import SessionLocal
    from app.services.snapshot import _budget
    from app.services.summary import monthly_summary

    client.put(PLAN, json={"planned_income_cents": 200_000})
    client.patch(f"{CATS}/{cid(client, 'Groceries')}", json={"budget_percent_bp": 1_000})
    with SessionLocal(bind=client.app.state.engine) as session:
        budget = _budget(monthly_summary(session, 2026, 1))
    needs = next(g for g in budget["groups"] if g["group"] == "needs")
    groceries = next(c for c in needs["categories"] if c["name"] == "Groceries")
    assert groceries["target_cents"] == 20_000
