"""Auto-sort learning and seeing what was auto-sorted. Fake data only."""

import pytest

from app.services.budget.category_learning import LEARN_AFTER, shop_key

TXN = "/api/local/transactions"
RULES = "/api/local/category-rules"


@pytest.mark.parametrize(
    ("description", "key"),
    [
        ("STARBUCKS STORE 12345 SEATTLE", "STARBUCKS STORE"),
        ("POS DEBIT FAKE GROCERY MART #44", "FAKE GROCERY MART"),
        ("SQ *FAKE BAKERY 8005551234", "*FAKE BAKERY"),
        ("AMAZON MKTP US*2K3J4", "AMAZON MKTP"),
        ("Fake Coffee", "Fake Coffee"),
        ("POS 12345", None),  # nothing but generic words and numbers
        ("AB 12", None),  # too few letters
    ],
)
def test_shop_key(description, key):
    assert shop_key(description) == key
    if key:
        assert key in description  # always a piece of the description, so it matches as a rule


@pytest.fixture
def category_id(client) -> int:
    body = {"name": "Fake Coffee Shops", "group": "wants"}
    return client.post("/api/local/categories", json=body).json()["id"]


def pick(client, txn_id: int, category_id: int | None) -> dict:
    response = client.patch(f"{TXN}/{txn_id}", json={"category_id": category_id})
    assert response.status_code == 200, response.text
    return response.json()


def test_picking_a_category_three_times_learns_a_rule(client, add_txn, checking, category_id):
    later = add_txn(checking, -300, description="FAKE BEANS CAFE 0099", category_id=None)
    rows = [add_txn(checking, -500, description=f"FAKE BEANS CAFE {n}00") for n in range(3)]
    results = [pick(client, t["id"], category_id) for t in rows]
    assert [r["learned_rule"] for r in results] == [None, None, "FAKE BEANS CAFE"]
    assert results[0]["category_source"] == "you"
    (rule,) = client.get(RULES).json()
    assert (rule["pattern"], rule["category_id"], rule["learned"]) == (
        "FAKE BEANS CAFE",
        category_id,
        True,
    )
    # It sorted the waiting one, and new ones are sorted as they come in.
    sorted_now = client.get(f"{TXN}/{later['id']}").json()
    assert (sorted_now["category_id"], sorted_now["category_source"]) == (category_id, "rule")
    new = add_txn(checking, -400, description="FAKE BEANS CAFE 0123")
    assert (new["category_id"], new["category_source"], new["sorted_by_rule_id"]) == (
        category_id,
        "rule",
        rule["id"],
    )
    assert client.get(RULES).json()[0]["sorted_count"] == 2


def test_waiting_transactions_get_sorted_when_a_rule_is_learned(
    client, add_txn, checking, category_id
):
    waiting = client.post(
        TXN,
        json={"account_id": checking, "date": "2026-01-15", "amount_cents": -100,
              "description": "FAKE BEANS CAFE 77"},
    ).json()  # fmt: skip
    # Added before any rule, with no category.
    assert waiting["category_id"] is None
    for n in range(LEARN_AFTER):
        pick(client, add_txn(checking, -500, description=f"FAKE BEANS CAFE {n}")["id"], category_id)
    assert client.get(f"{TXN}/{waiting['id']}").json()["category_source"] == "rule"


def test_mixed_picks_teach_nothing(client, add_txn, checking, category_id):
    other = client.post("/api/local/categories", json={"name": "Fake Gifts", "group": "wants"})
    rows = [add_txn(checking, -500, description=f"FAKE MALL {n}") for n in range(4)]
    pick(client, rows[0]["id"], other.json()["id"])
    for t in rows[1:]:
        assert pick(client, t["id"], category_id)["learned_rule"] is None
    assert client.get(RULES).json() == []


def test_a_rule_you_made_is_never_outranked(client, add_txn, checking, category_id):
    groceries = client.post("/api/local/categories", json={"name": "Fake Food", "group": "needs"})
    client.post(RULES, json={"pattern": "FAKE BEANS CAFE", "category_id": groceries.json()["id"]})
    for n in range(LEARN_AFTER):
        t = add_txn(checking, -500, description=f"FAKE BEANS CAFE {n}")
        assert pick(client, t["id"], category_id)["learned_rule"] is None
    assert len(client.get(RULES).json()) == 1


def test_list_what_was_auto_sorted(client, add_txn, checking, category_id):
    client.post(RULES, json={"pattern": "FAKE BEANS", "category_id": category_id})
    auto = add_txn(checking, -500, description="FAKE BEANS 1")
    mine = add_txn(checking, -500, description="OTHER", category_id=category_id)
    add_txn(checking, -500, description="NOTHING")
    by_rule = client.get(TXN, params={"sorted_by": "rule"}).json()["items"]
    by_you = client.get(TXN, params={"sorted_by": "you"}).json()["items"]
    assert [t["id"] for t in by_rule] == [auto["id"]]
    assert [t["id"] for t in by_you] == [mine["id"]]


def test_changing_an_auto_sorted_category_makes_it_yours(client, add_txn, checking, category_id):
    rule = client.post(RULES, json={"pattern": "FAKE BEANS", "category_id": category_id}).json()
    auto = add_txn(checking, -500, description="FAKE BEANS 1")
    assert auto["sorted_by_rule_id"] == rule["id"]
    changed = pick(client, auto["id"], None)
    assert (changed["category_source"], changed["sorted_by_rule_id"]) == (None, None)


def test_deleting_a_rule_keeps_categories_but_forgets_the_rule(
    client, add_txn, checking, category_id
):
    rule = client.post(RULES, json={"pattern": "FAKE BEANS", "category_id": category_id}).json()
    auto = add_txn(checking, -500, description="FAKE BEANS 1")
    client.delete(f"{RULES}/{rule['id']}")
    kept = client.get(f"{TXN}/{auto['id']}").json()
    assert (kept["category_id"], kept["sorted_by_rule_id"]) == (category_id, None)


def test_sort_now_and_csv_import_mark_rows_as_rule_sorted(client, add_txn, checking, category_id):
    old = add_txn(checking, -500, description="FAKE BEANS 1")  # before the rule
    client.post(RULES, json={"pattern": "FAKE BEANS", "category_id": category_id})
    assert client.post(f"{RULES}/apply").json()["categorized"] == 1
    assert client.get(f"{TXN}/{old['id']}").json()["category_source"] == "rule"
