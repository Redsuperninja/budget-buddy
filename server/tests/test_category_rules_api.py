"""Auto-categorization rules (roadmap #9). Fake data only."""

import pytest
from csv_helpers import CHECKING_CSV, ok, send, txns
from test_categories_summary_api import cid

RULES = "/api/local/category-rules"


def add_rule(client, pattern, category, status=201):
    response = client.post(RULES, json={"pattern": pattern, "category_id": cid(client, category)})
    assert response.status_code == status, response.text
    return response.json()


def test_rule_list_add_edit_delete(client):
    rule = add_rule(client, "  fake grocery ", "Groceries")
    assert rule["pattern"] == "fake grocery"
    assert [r["id"] for r in client.get(RULES).json()] == [rule["id"]]

    moved = client.patch(f"{RULES}/{rule['id']}", json={"category_id": cid(client, "Dining Out")})
    assert moved.json()["category_id"] == cid(client, "Dining Out")
    assert client.delete(f"{RULES}/{rule['id']}").status_code == 204
    assert client.get(f"{RULES}/{rule['id']}").status_code == 404


def test_rule_checks(client):
    add_rule(client, "Coffee", "Dining Out")
    dup = client.post(RULES, json={"pattern": "COFFEE", "category_id": cid(client, "Groceries")})
    assert (dup.status_code, dup.json()["error"]["code"]) == (409, "pattern_taken")
    missing = client.post(RULES, json={"pattern": "Gym", "category_id": 99_999})
    assert missing.status_code == 404
    short = client.post(RULES, json={"pattern": " a ", "category_id": cid(client, "Groceries")})
    assert short.status_code == 422
    cleared = client.patch(f"{RULES}/1", json={"pattern": None})
    assert cleared.status_code == 422


def test_rules_go_when_their_category_goes(client):
    from app.db import SessionLocal
    from app.models import Category

    pets = client.post("/api/local/categories", json={"name": "Pets", "group": "wants"}).json()
    add_rule(client, "Pet shop", "Pets")
    with SessionLocal(bind=client.app.state.engine) as session:
        session.delete(session.get(Category, pets["id"]))
        session.commit()
    assert client.get(RULES).json() == []


def test_import_sorts_new_rows_and_longest_match_wins(client, checking):
    add_rule(client, "fake", "Shopping")
    add_rule(client, "Fake Coffee", "Dining Out")
    add_rule(client, "PAYROLL", "Paycheck")
    result = ok(send(client, checking, CHECKING_CSV, "commit"))
    assert (result["imported"], result["categorized"]) == (4, 4)
    by_description = {t["description"]: t["category_id"] for t in txns(client, checking)}
    assert by_description == {
        "FAKE GROCERY 123": cid(client, "Shopping"),
        "Fake Payroll": cid(client, "Paycheck"),
        "Fake Coffee": cid(client, "Dining Out"),
    }


def test_same_length_tie_goes_to_older_rule(client, checking, add_txn):
    add_rule(client, "abc", "Groceries")
    add_rule(client, "xyz", "Dining Out")
    txn = add_txn(checking, -100, description="abc xyz")
    assert txn["category_id"] == cid(client, "Groceries")


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "Groceries"),  # no category sent: the rule fills it in
        ({"category_id": None}, None),  # "no category" on purpose: left alone
        ({"kind": "refund"}, None),  # refunds aren't touched
        ({"kind": "adjustment"}, None),  # adjustments can't have a category
    ],
)
def test_manual_entry_uses_rules_only_when_no_category_sent(
    client, checking, add_txn, overrides, expected
):
    add_rule(client, "market", "Groceries")
    amount = 500 if overrides.get("kind") == "refund" else -500
    txn = add_txn(checking, amount, description="Corner Market", **overrides)
    assert txn["category_id"] == (cid(client, expected) if expected else None)


def test_apply_sorts_only_uncategorized_regular_transactions(client, checking, add_txn):
    savings = client.post("/api/local/accounts", json={"name": "S", "kind": "savings"}).json()
    plain = add_txn(checking, -100, description="Corner market", category_id=None)
    chosen = add_txn(checking, -100, description="Market gift", category_id=cid(client, "Shopping"))
    out = add_txn(checking, -100, description="Market move", category_id=None)
    into = add_txn(savings["id"], 100, description="Market move", category_id=None)
    assert (
        client.post(
            f"/api/local/transactions/{out['id']}/transfer", json={"other_id": into["id"]}
        ).status_code
        == 200
    )
    add_rule(client, "market", "Groceries")

    assert ok(client.post(f"{RULES}/apply")) == {"categorized": 1}
    get = lambda t: client.get(f"/api/local/transactions/{t['id']}").json()["category_id"]  # noqa: E731
    assert get(plain) == cid(client, "Groceries")
    assert get(chosen) == cid(client, "Shopping")  # never overrides a choice
    assert get(out) == cid(client, "Transfer")  # transfers keep the Transfer category
    assert ok(client.post(f"{RULES}/apply")) == {"categorized": 0}
