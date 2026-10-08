"""The suggested budget (roadmap #10): 50/30/20 from recent months. Fake data only."""

import pytest
from test_categories_summary_api import CATS, cid

from app.models import CategoryGroup
from app.services.budget_engine import group_amounts, months_before, split, split_savings

SUGGEST = "/api/local/budget/suggestion"
NEEDS, WANTS, SAVINGS = CategoryGroup.NEEDS, CategoryGroup.WANTS, CategoryGroup.SAVINGS


@pytest.fixture
def history(client, make_account, add_txn):
    """July to September 2026: $4,000 pay, $2,000 needs, $400 wants, $400 saved each month."""
    checking = make_account()["id"]
    savings = make_account(name="Savings", kind="savings")["id"]
    for month in ("07", "08", "09"):
        day = f"2026-{month}-05"
        add_txn(checking, 400_000, date=day, category_id=cid(client, "Paycheck"))
        add_txn(checking, -150_000, date=day, category_id=cid(client, "Rent/Mortgage"))
        add_txn(checking, -50_000, date=day, category_id=cid(client, "Groceries"))
        add_txn(checking, -30_000, date=day, category_id=cid(client, "Dining Out"))
        add_txn(checking, -10_000, date=day, category_id=cid(client, "Shopping"))
        add_txn(checking, -20_000, date=day, category_id=cid(client, "Emergency Fund"))
        out = add_txn(checking, -20_000, date=day, category_id=None)
        into = add_txn(savings, 20_000, date=day, category_id=None)
        url = f"/api/local/transactions/{out['id']}/transfer"
        assert client.post(url, json={"other_id": into["id"]}).is_success
    return checking


def suggestion(client, month="2026-10"):
    response = client.get(SUGGEST, params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def by_name(s):
    return {c["name"]: c for c in s["categories"]}


def groups(s):
    return {g["group"]: g for g in s["groups"]}


def test_months_before_crosses_years():
    assert months_before(2026, 2, 3) == [(2025, 11), (2025, 12), (2026, 1)]
    assert months_before(2026, 12, 1) == [(2026, 11)]


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (100, [1, 1, 1], [34, 33, 33]),
        (120_000, [30_000, 10_000], [90_000, 30_000]),
        (10, [0, 0], [5, 5]),
        (0, [5, 3], [0, 0]),
        (7, [], []),
        (101, [1, 2], [34, 67]),
    ],
)
def test_split_adds_up_exactly(total, weights, expected):
    assert split(total, weights) == expected
    assert sum(split(total, weights)) == (total if weights else 0)


@pytest.mark.parametrize(
    ("income", "needs", "saved", "expected"),
    [
        (400_000, 200_000, 40_000, (200_000, 120_000, 80_000)),  # textbook 50/30/20
        (400_000, 100_000, 0, (100_000, 120_000, 180_000)),  # leftover goes to savings
        (400_000, 300_000, 0, (300_000, 20_000, 80_000)),  # heavy needs squeeze wants
        (400_000, 350_000, 0, (350_000, 0, 50_000)),  # needs + 20% > income
        (400_000, 450_000, 0, (450_000, 0, 0)),  # needs alone > income
        (400_000, 200_000, 120_000, (200_000, 80_000, 120_000)),  # keeps a higher saving rate
        (0, 200_000, 0, (0, 0, 0)),  # no income: nothing to plan
    ],
)
def test_group_amounts(income, needs, saved, expected):
    amounts = group_amounts(income, needs, saved)
    assert (amounts[NEEDS], amounts[WANTS], amounts[SAVINGS]) == expected


def test_suggestion_from_three_months(client, history):
    s = suggestion(client)
    assert s["looked_at"] == ["2026-07", "2026-08", "2026-09"]
    assert (s["months_with_data"], s["income_source"]) == (3, "average")
    assert (s["income_cents"], s["average_income_cents"]) == (400_000, 400_000)
    cats = by_name(s)
    assert cats["Rent/Mortgage"]["suggested_cents"] == 150_000  # needs keep their average
    assert cats["Rent/Mortgage"]["suggested_percent_bp"] == 3_750
    assert cats["Dining Out"]["suggested_cents"] == 90_000  # wants share 30% by history
    assert cats["Shopping"]["suggested_cents"] == 30_000
    assert cats["Travel"]["suggested_cents"] == 0
    # Savings share by history: half in the category, half moved into the savings account.
    assert cats["Emergency Fund"]["suggested_cents"] == 40_000
    assert s["savings_by_transfer_cents"] == 40_000
    assert cats["Dining Out"]["average_cents"] == 30_000
    g = groups(s)
    assert [g[x]["suggested_percent_bp"] for x in ("needs", "wants", "savings")] == [
        5_000,
        3_000,
        2_000,
    ]
    assert g["savings"]["average_cents"] == 40_000  # includes the transfer into savings
    assert s["notes"] == []
    assert "Paycheck" not in cats  # income isn't budgeted here


def test_planned_income_is_used_when_set(client, history):
    client.put("/api/local/budget/plan", json={"planned_income_cents": 500_000})
    s = suggestion(client)
    assert (s["income_cents"], s["income_source"]) == (500_000, "planned")
    assert groups(s)["wants"]["suggested_cents"] == 150_000
    assert groups(s)["savings"]["suggested_cents"] == 150_000


def test_short_history_and_no_history(client, make_account, add_txn):
    assert suggestion(client)["notes"] == [
        "There's no history yet. Add or import a few months of transactions first."
    ]
    checking = make_account()["id"]
    add_txn(checking, 300_000, date="2026-09-01", category_id=cid(client, "Paycheck"))
    add_txn(checking, -260_000, date="2026-09-02", category_id=cid(client, "Rent/Mortgage"))
    s = suggestion(client)
    assert s["months_with_data"] == 1
    assert s["average_income_cents"] == 300_000  # not diluted by the empty months
    assert "only 1 month(s)" in s["notes"][0]
    assert any("more than half" in n for n in s["notes"])
    assert any("less than 20%" in n for n in s["notes"])


def test_no_income_gives_zeros_and_cannot_be_applied(client, make_account, add_txn):
    checking = make_account()["id"]
    add_txn(checking, -5_000, date="2026-09-01", category_id=cid(client, "Groceries"))
    s = suggestion(client)
    assert s["income_cents"] == 0
    assert all(c["suggested_cents"] == 0 for c in s["categories"])
    assert any("no income to plan" in n for n in s["notes"])
    refused = client.post(f"{SUGGEST}/apply", json={"month": "2026-10"})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "no_income")


def test_apply_as_amounts(client, history):
    client.patch(f"{CATS}/{cid(client, 'Travel')}", json={"budget_percent_bp": 500})
    result = client.post(f"{SUGGEST}/apply", json={"month": "2026-10"})
    assert result.json()["updated"] == len(suggestion(client)["categories"])
    cats = {c["name"]: c for c in client.get(CATS).json()}
    assert (cats["Dining Out"]["budget_cents"], cats["Dining Out"]["budget_percent_bp"]) == (
        90_000,
        None,
    )
    assert (cats["Travel"]["budget_cents"], cats["Travel"]["budget_percent_bp"]) == (0, None)
    assert cats["Paycheck"]["budget_cents"] == 0  # income categories untouched


def test_apply_as_percentages(client, history):
    client.post(f"{SUGGEST}/apply", json={"month": "2026-10", "use": "percentages"})
    cats = {c["name"]: c for c in client.get(CATS).json()}
    assert (cats["Rent/Mortgage"]["budget_percent_bp"], cats["Rent/Mortgage"]["budget_cents"]) == (
        3_750,
        0,
    )
    assert cats["Travel"]["budget_percent_bp"] is None  # 0% can't be a percentage budget
    assert cats["Travel"]["budget_cents"] == 0


@pytest.mark.parametrize("month", ["2026-13", "26-01", "October"])
def test_month_is_checked(client, month):
    assert client.get(SUGGEST, params={"month": month}).status_code == 422
    applied = client.post(f"{SUGGEST}/apply", json={"month": month})
    assert applied.status_code == 422


def test_month_defaults_to_this_month(client):
    assert client.get(SUGGEST).status_code == 200


def test_split_savings_with_and_without_categories():
    assert split_savings(80_000, [20_000, 0], 20_000) == ([40_000, 0], 40_000)
    assert split_savings(80_000, [], 0) == ([], 80_000)  # nowhere else to put it
    assert split_savings(90, [0, 0, 0], 0) == ([30, 30, 30], 0)


def test_needs_above_income_note(client, make_account, add_txn):
    checking = make_account()["id"]
    add_txn(checking, 100_000, date="2026-09-01", category_id=cid(client, "Paycheck"))
    add_txn(checking, -120_000, date="2026-09-02", category_id=cid(client, "Rent/Mortgage"))
    notes = suggestion(client)["notes"]
    assert any("as much as your income or more" in n for n in notes)
    assert not any("less than 20%" in n for n in notes)


def test_percentages_without_a_plan_save_the_average_income(client, history):
    result = client.post(f"{SUGGEST}/apply", json={"month": "2026-10", "use": "percentages"})
    assert result.json()["planned_income_cents"] == 400_000
    assert client.get("/api/local/budget/plan").json()["planned_income_cents"] == 400_000
    rent = next(c for c in client.get(CATS).json() if c["name"] == "Rent/Mortgage")
    assert rent["budget_percent_bp"] == 3_750  # 30% of nothing on day 1 no longer happens
    amounts = client.post(f"{SUGGEST}/apply", json={"month": "2026-10"}).json()
    assert amounts["planned_income_cents"] is None
