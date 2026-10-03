"""Transactions API: CRUD, money input, filters, pagination, transfers. Fake data only."""

import pytest

URL = "/api/local/transactions"


@pytest.fixture
def accounts(client, make_account):
    return make_account()["id"], make_account(name="Savings", kind="savings")["id"]


def category_id(client, name="Groceries"):
    # The seeded starter categories (migration 0002) include "Groceries" and "Paycheck".
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Category

    with SessionLocal(bind=client.app.state.engine) as session:
        return session.scalar(select(Category.id).where(Category.name == name))


def test_transaction_crud(client, add_txn, accounts):
    checking, savings = accounts
    groceries = category_id(client)
    created = add_txn(checking, -4_215, category_id=groceries, notes="fake note")
    assert created["source"] == "manual"
    assert created["kind"] == "normal"
    assert created["category_id"] == groceries
    txn_id = created["id"]

    assert client.get(f"{URL}/{txn_id}").json()["amount_cents"] == -4_215

    response = client.patch(
        f"{URL}/{txn_id}",
        json={"amount": "-50.10", "account_id": savings, "category_id": None, "kind": "refund"},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert (updated["amount_cents"], updated["account_id"]) == (-5_010, savings)
    assert (updated["category_id"], updated["kind"]) == (None, "refund")
    assert updated["description"] == "Fake"

    assert client.delete(f"{URL}/{txn_id}").status_code == 204
    assert client.get(f"{URL}/{txn_id}").status_code == 404


def test_create_with_dollar_amount(client, add_txn, accounts):
    created = add_txn(accounts[0], None, amount="-12.30")
    assert created["amount_cents"] == -1_230


@pytest.mark.parametrize(
    ("overrides", "phrase"),
    [
        ({"amount": "12.345"}, "fractions of a cent"),
        ({"amount": "$12.00"}, "without a $ sign"),
        ({"amount": "1,200.00"}, "without a $ sign"),
        ({"amount": "1e3"}, "without a $ sign"),
        ({"amount": "999999999999"}, "too large"),
        ({"amount": 12.5}, "amount"),  # a JSON number, not text
        ({"amount_cents": 12.5}, "amount_cents"),
        ({"amount_cents": "1250"}, "amount_cents"),
        ({"amount_cents": 0}, "can't be zero"),
        ({"amount_cents": 100, "amount": "1.00"}, "not both"),
        ({}, "amount is required"),
    ],
)
def test_bad_money_input(client, accounts, overrides, phrase):
    body = {"account_id": accounts[0], "date": "2026-01-15", "description": "Fake", **overrides}
    response = client.post(URL, json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert phrase in error["message"]


def test_bad_references_and_dates(client, accounts):
    body = {"account_id": accounts[0], "date": "2026-01-15", "description": "x", "amount_cents": 1}
    assert client.post(URL, json={**body, "account_id": 999}).status_code == 404
    assert client.post(URL, json={**body, "category_id": 999}).status_code == 404
    assert client.post(URL, json={**body, "date": "01/15/2026"}).status_code == 422
    assert client.post(URL, json={**body, "kind": "transfer"}).status_code == 422


def test_filters(client, add_txn, accounts):
    checking, savings = accounts
    groceries = category_id(client)
    add_txn(checking, -1_000, date="2026-01-05", description="Corner Market", category_id=groceries)
    add_txn(checking, -2_000, date="2026-02-10", description="Movie night")
    add_txn(savings, 3_000, date="2026-02-20", description="Interest 100%")
    add_txn(checking, 500, date="2026-03-01", description="market refund", kind="refund")

    def descriptions(**params):
        response = client.get(URL, params=params)
        assert response.status_code == 200, response.text
        return [t["description"] for t in response.json()["items"]]

    assert descriptions() == ["market refund", "Interest 100%", "Movie night", "Corner Market"]
    assert descriptions(account_id=savings) == ["Interest 100%"]
    assert descriptions(category_id=groceries) == ["Corner Market"]
    assert descriptions(date_from="2026-02-01", date_to="2026-02-28") == [
        "Interest 100%",
        "Movie night",
    ]
    assert descriptions(kind="refund") == ["market refund"]
    assert descriptions(q="MARKET") == ["market refund", "Corner Market"]
    assert descriptions(q="%") == ["Interest 100%"]  # wildcards are matched literally
    assert descriptions(q="_") == []
    assert client.get(URL, params={"kind": "bogus"}).status_code == 422


def test_pagination(client, add_txn, accounts):
    for day in range(1, 8):
        add_txn(accounts[0], -day, date=f"2026-01-{day:02d}")
    page = client.get(URL, params={"limit": 3, "offset": 2}).json()
    assert page["total"] == 7
    assert (page["limit"], page["offset"]) == (3, 2)
    assert [t["date"] for t in page["items"]] == ["2026-01-05", "2026-01-04", "2026-01-03"]
    assert client.get(URL, params={"offset": 7}).json()["items"] == []
    assert client.get(URL, params={"limit": 0}).status_code == 422
    assert client.get(URL, params={"limit": 501}).status_code == 422


def test_link_transfer(client, add_txn, accounts):
    checking, savings = accounts
    out = add_txn(checking, -50_000)
    into = add_txn(savings, 50_000)

    response = client.post(f"{URL}/{out['id']}/transfer", json={"other_id": into["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "transfer"
    assert response.json()["transfer_pair_id"] == into["id"]
    other = client.get(f"{URL}/{into['id']}").json()
    assert (other["kind"], other["transfer_pair_id"]) == ("transfer", out["id"])

    # Linking again is harmless; linking either side to something else is not allowed.
    assert (
        client.post(f"{URL}/{into['id']}/transfer", json={"other_id": out["id"]}).status_code == 200
    )
    third = add_txn(checking, 50_000)
    conflict = client.post(f"{URL}/{third['id']}/transfer", json={"other_id": into["id"]})
    assert conflict.json()["error"]["code"] == "already_linked"

    # A linked transaction's amount can't change on one side only.
    locked = client.patch(f"{URL}/{out['id']}", json={"amount_cents": -1})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "part_of_transfer"
    assert client.patch(f"{URL}/{out['id']}", json={"description": "Move"}).status_code == 200

    unlinked = client.delete(f"{URL}/{out['id']}/transfer")
    assert unlinked.json()["kind"] == "normal"
    assert client.get(f"{URL}/{into['id']}").json()["transfer_pair_id"] is None
    assert client.delete(f"{URL}/{out['id']}/transfer").status_code == 409


def test_deleting_half_a_transfer_is_blocked(client, add_txn, accounts):
    out = add_txn(accounts[0], -100)
    into = add_txn(accounts[1], 100)
    client.post(f"{URL}/{out['id']}/transfer", json={"other_id": into["id"]})
    for side in (out, into):
        response = client.delete(f"{URL}/{side['id']}")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "part_of_transfer"
        assert "Remove the transfer link" in response.json()["error"]["message"]
    # Both halves are untouched.
    for side, partner in ((out, into), (into, out)):
        kept = client.get(f"{URL}/{side['id']}").json()
        assert (kept["kind"], kept["transfer_pair_id"]) == ("transfer", partner["id"])

    # Unlinking on purpose first makes deleting possible.
    assert client.delete(f"{URL}/{out['id']}/transfer").status_code == 200
    assert client.delete(f"{URL}/{out['id']}").status_code == 204


@pytest.mark.parametrize(
    ("second_account", "first_amount", "second_amount", "reason"),
    [
        (0, -100, 100, "two different accounts"),
        (1, -100, -100, "same amount coming in"),
        (1, -100, 99, "same amount coming in"),
        (1, 100, 100, "same amount coming in"),
    ],
)
def test_transfer_validation(
    client, add_txn, accounts, second_account, first_amount, second_amount, reason
):
    first = add_txn(accounts[0], first_amount)
    second = add_txn(accounts[second_account], second_amount)
    response = client.post(f"{URL}/{first['id']}/transfer", json={"other_id": second["id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_transfer"
    assert reason in response.json()["error"]["message"]
    assert client.get(f"{URL}/{first['id']}").json()["kind"] == "normal"


def test_transfer_needs_two_existing_transactions(client, add_txn, accounts):
    first = add_txn(accounts[0], -100)
    same = client.post(f"{URL}/{first['id']}/transfer", json={"other_id": first["id"]})
    assert same.status_code == 422
    assert client.post(f"{URL}/{first['id']}/transfer", json={"other_id": 999}).status_code == 404


HUGE = 99_999_999_999_999_999_999  # bigger than SQLite's 64-bit integers
BIGGEST_ID = 2**63 - 1


def test_huge_ids_are_a_validation_error_not_a_crash(client, add_txn, accounts):
    txn = add_txn(accounts[0], -100)
    body = {"account_id": accounts[0], "date": "2026-01-15", "description": "x", "amount_cents": 1}
    requests = [
        ("get", f"/api/local/accounts/{HUGE}", None, None),
        ("patch", f"/api/local/accounts/{HUGE}", None, {"name": "x"}),
        ("delete", f"/api/local/accounts/{HUGE}", None, None),
        ("get", f"{URL}/{HUGE}", None, None),
        ("patch", f"{URL}/{HUGE}", None, {"description": "x"}),
        ("delete", f"{URL}/{HUGE}", None, None),
        ("post", f"{URL}/{HUGE}/transfer", None, {"other_id": txn["id"]}),
        ("delete", f"{URL}/{HUGE}/transfer", None, None),
        ("get", URL, {"account_id": HUGE}, None),
        ("get", URL, {"category_id": HUGE}, None),
        ("get", URL, {"offset": HUGE}, None),
        ("post", URL, None, {**body, "account_id": HUGE}),
        ("post", URL, None, {**body, "category_id": HUGE}),
        ("patch", f"{URL}/{txn['id']}", None, {"account_id": HUGE}),
        ("patch", f"{URL}/{txn['id']}", None, {"category_id": HUGE}),
        ("post", f"{URL}/{txn['id']}/transfer", None, {"other_id": HUGE}),
    ]
    for method, path, params, json in requests:
        response = client.request(method, path, params=params, json=json)
        assert response.status_code == 422, (method, path, params, json)
        assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("bad_id", [0, -1])
def test_ids_start_at_one(client, bad_id):
    assert client.get(f"{URL}/{bad_id}").status_code == 422
    assert client.get(URL, params={"account_id": bad_id}).status_code == 422


def test_biggest_possible_id_is_just_not_found(client, accounts):
    assert client.get(f"/api/local/accounts/{BIGGEST_ID}").status_code == 404
    assert client.get(f"{URL}/{BIGGEST_ID}").status_code == 404
    assert client.get(URL, params={"offset": BIGGEST_ID}).json()["items"] == []
