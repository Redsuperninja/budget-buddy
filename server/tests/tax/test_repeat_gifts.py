"""Recurring gifts: a new payment to a charity you gave to before is filed and recorded for you.
Fake data only."""

import datetime as dt

import pytest
from csv_helpers import ok, send

from app.schemas.tax import donations as donation_schemas

URL = "/api/local/donations"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(donation_schemas, "_today", lambda: dt.date(2030, 1, 1))


@pytest.fixture
def first_gift(client, add_txn, checking) -> dict:
    """$40.00 to a fake food bank, sorted into charity as a whole-payment gift."""
    payment = add_txn(checking, -4_000, date="2026-01-15", description="FAKE FOOD BANK 0115")
    body = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": payment["id"]}  # fmt: skip
    created = client.post(URL, json=body)
    assert created.status_code == 201, created.text
    return created.json()


def donations(client) -> list[dict]:
    return client.get(URL, params={"tax_year": 2026}).json()["items"]


def category_name(client, category_id) -> str | None:
    names = {c["id"]: c["name"] for c in client.get("/api/local/categories").json()}
    return names.get(category_id)


def test_a_repeat_payment_is_recorded_and_filed(client, add_txn, checking, first_gift):
    again = add_txn(checking, -4_000, date="2026-02-15", description="FAKE FOOD BANK 0215")

    auto = [d for d in donations(client) if d["transaction_id"] == again["id"]]
    assert len(auto) == 1
    assert auto[0]["organization"] == "Fake Food Bank"
    assert auto[0]["amount_cents"] == 4_000
    assert auto[0]["date"] == "2026-02-15"
    assert auto[0]["auto_added"] is True
    assert first_gift["auto_added"] is False
    payment = client.get(f"/api/local/transactions/{again['id']}").json()
    assert category_name(client, payment["category_id"]) == "Charitable giving"


def test_a_different_amount_is_filed_but_not_recorded(client, add_txn, checking, first_gift):
    # More than usual may be a membership with perks or an event: you add the gift part yourself.
    again = add_txn(checking, -5_500, date="2026-02-15", description="FAKE FOOD BANK 0215")
    assert len(donations(client)) == 1
    payment = client.get(f"/api/local/transactions/{again['id']}").json()
    assert category_name(client, payment["category_id"]) == "Charitable giving"


def test_budget_buddy_files_it_not_you(client, add_txn, checking, first_gift):
    again = add_txn(checking, -4_000, date="2026-02-15", description="FAKE FOOD BANK 0215")
    payment = client.get(f"/api/local/transactions/{again['id']}").json()
    assert payment["category_source"] is None  # auto-sort learning doesn't count it as yours


def test_a_check_to_a_charity_doesnt_make_every_check_a_gift(client, add_txn, checking):
    paid = add_txn(checking, -4_000, date="2026-01-15", description="CHECK 1043")
    body = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": paid["id"]}  # fmt: skip
    assert client.post(URL, json=body).status_code == 201
    rent = add_txn(checking, -4_000, date="2026-02-01", description="CHECK 1044")
    assert len(donations(client)) == 1
    assert client.get(f"/api/local/transactions/{rent['id']}").json()["category_id"] is None


def test_a_charity_with_a_part_gift_is_left_alone(client, add_txn, checking, first_gift):
    gala = add_txn(checking, -10_000, date="2026-01-20", description="FAKE FOOD BANK GALA")
    body = {"date": "2026-01-20", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 6_000, "transaction_id": gala["id"]}  # fmt: skip
    assert client.post(URL, json=body).status_code == 201
    add_txn(checking, -4_000, date="2026-02-15", description="FAKE FOOD BANK 0215")
    assert len(donations(client)) == 2


def test_other_payments_are_left_alone(client, add_txn, checking, first_gift):
    add_txn(checking, -4_000, date="2026-02-15", description="FAKE GROCERY 0215")
    add_txn(checking, 4_000, date="2026-02-16", description="FAKE FOOD BANK REFUND")
    assert len(donations(client)) == 1


def test_a_part_gift_is_never_repeated(client, add_txn, checking):
    dinner = add_txn(checking, -10_000, date="2026-01-15", description="FAKE GALA DINNER")
    body = {"date": "2026-01-15", "organization": "Fake Gala", "kind": "cash",
            "amount_cents": 6_000, "transaction_id": dinner["id"]}  # fmt: skip
    assert client.post(URL, json=body).status_code == 201
    add_txn(checking, -10_000, date="2026-02-15", description="FAKE GALA DINNER")
    assert len(donations(client)) == 1


def test_deleting_an_automatic_donation_is_final(client, add_txn, checking, first_gift):
    again = add_txn(checking, -4_000, date="2026-02-15", description="FAKE FOOD BANK 0215")
    auto = next(d for d in donations(client) if d["transaction_id"] == again["id"])
    assert client.delete(f"{URL}/{auto['id']}").status_code == 204
    client.post("/api/local/transactions/match-transfers")  # nothing looks at old payments again
    assert [d["id"] for d in donations(client)] == [first_gift["id"]]


def test_a_bank_file_records_repeat_gifts(client, add_txn, checking, first_gift):
    body = (
        "Date,Description,Amount\r\n"
        "02/15/2026,FAKE FOOD BANK 0215,-40.00\r\n"
        "03/15/2026,FAKE FOOD BANK 0315,-40.00\r\n"
        "03/16/2026,FAKE COFFEE,-4.00\r\n"
    )
    result = ok(send(client, checking, body, "commit"))
    assert result["donations_added"] == 2
    assert len(donations(client)) == 3
