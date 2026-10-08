"""Filing gifts under a category: "Charitable giving" for charity, "Gifts" for presents."""

import datetime as dt

import pytest

from app.schemas import donations as donation_schemas

DONATIONS = "/api/local/donations"
TXN = "/api/local/transactions"
CATEGORIES = "/api/local/categories"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(donation_schemas, "_today", lambda: dt.date(2030, 1, 1))


@pytest.fixture
def payment(add_txn, checking) -> dict:
    return add_txn(checking, -4_000, description="FAKE FOOD BANK")


def category(client, category_id: int) -> dict:
    return next(c for c in client.get(CATEGORIES).json() if c["id"] == category_id)


def gift(payment_id: int | None) -> dict:
    return {
        "date": "2026-01-15",
        "organization": "Fake Food Bank",
        "kind": "cash",
        "amount_cents": 4_000,
        "transaction_id": payment_id,
    }


def test_charity_gift_files_the_payment_under_charitable_giving(client, payment, add_txn, checking):
    client.post(DONATIONS, json=gift(payment["id"]))
    filed = client.get(f"{TXN}/{payment['id']}").json()
    made = category(client, filed["category_id"])
    assert (made["name"], made["group"]) == ("Charitable giving", "wants")
    # A second gift reuses the same category.
    other = add_txn(checking, -5_000)
    client.post(DONATIONS, json=gift(other["id"]))
    assert client.get(f"{TXN}/{other['id']}").json()["category_id"] == made["id"]


def test_linking_later_files_it_too(client, payment):
    created = client.post(DONATIONS, json=gift(None)).json()
    client.patch(f"{DONATIONS}/{created['id']}", json={"transaction_id": payment["id"]})
    filed = client.get(f"{TXN}/{payment['id']}").json()
    assert category(client, filed["category_id"])["name"] == "Charitable giving"


def test_an_existing_category_is_reused_whatever_its_case(client, payment):
    mine = client.post(CATEGORIES, json={"name": "charitable GIVING", "group": "needs"}).json()
    client.post(DONATIONS, json=gift(payment["id"]))
    assert client.get(f"{TXN}/{payment['id']}").json()["category_id"] == mine["id"]


def test_an_income_category_of_that_name_is_never_used(client, payment):
    client.post(CATEGORIES, json={"name": "Gifts", "group": "income"})
    response = client.post(f"{TXN}/{payment['id']}/personal-gift")
    assert response.status_code == 200
    assert response.json()["category_id"] is None


def test_personal_gift_files_under_gifts_with_no_tax_record(client, payment):
    response = client.post(f"{TXN}/{payment['id']}/personal-gift")
    assert response.status_code == 200
    made = category(client, response.json()["category_id"])
    assert (made["name"], made["group"]) == ("Gifts", "wants")
    assert response.json()["donation_id"] is None
    assert client.get(DONATIONS).json()["total"] == 0


def test_personal_gift_needs_money_paid_out(client, add_txn, checking):
    money_in = add_txn(checking, 4_000)
    response = client.post(f"{TXN}/{money_in['id']}/personal-gift")
    assert response.status_code == 422


def test_a_charity_gift_cant_also_be_a_personal_gift(client, payment):
    client.post(DONATIONS, json=gift(payment["id"]))
    response = client.post(f"{TXN}/{payment['id']}/personal-gift")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "linked_to_donation"
