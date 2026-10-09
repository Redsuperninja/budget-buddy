"""Pay deposits waiting for a paycheck, and adding a paycheck linked to one. Fake data only."""

import pytest

URL = "/api/local/paychecks"


@pytest.fixture
def checking(make_account):
    return make_account()["id"]


def deposits(client, year=2026):
    response = client.get(f"{URL}/deposits", params={"year": year})
    assert response.status_code == 200, response.text
    return response.json()


def test_pay_deposits_are_offered_until_a_paycheck_uses_them(client, checking, add_txn):
    pay = add_txn(checking, 250_000, date="2026-03-13", description="FAKECO INC PAYROLL PPD ID: 1")
    add_txn(checking, 1_000, date="2026-03-14", description="Fake refund")
    add_txn(checking, -250_000, date="2026-03-15", description="FAKECO PAYROLL REVERSAL")
    waiting = deposits(client)
    assert [(d["transaction_id"], d["employer"], d["amount_cents"]) for d in waiting] == [
        (pay["id"], "FAKECO INC", 250_000)
    ]
    assert deposits(client, 2025) == []

    stub = {"pay_date": "2026-03-13", "employer": "FakeCo", "gross_cents": 300_000}
    stub |= {"federal_tax_cents": 50_000, "net_cents": 250_000}
    made = client.post(URL, json=stub | {"deposit_transaction_id": pay["id"]})
    assert made.status_code == 201, made.text
    assert (made.json()["deposit_transaction_id"], made.json()["account_id"]) == (
        pay["id"],
        checking,
    )
    assert deposits(client) == []


def test_the_starter_paycheck_category_counts(client, checking, add_txn):
    paycheck = next(
        c["id"] for c in client.get("/api/local/categories").json() if c["name"] == "Paycheck"
    )
    add_txn(checking, 100_000, date="2026-03-13", description="FAKE ACH", category_id=paycheck)
    assert len(deposits(client)) == 1


def test_a_wrong_deposit_adds_no_paycheck(client, checking, add_txn):
    pay = add_txn(checking, 250_000, date="2026-03-13", description="FAKECO PAYROLL")
    stub = {"pay_date": "2026-03-13", "employer": "FakeCo", "gross_cents": 200_000}
    refused = client.post(
        URL, json=stub | {"net_cents": 200_000, "deposit_transaction_id": pay["id"]}
    )
    assert refused.status_code == 422
    assert client.get(URL, params={"year": 2026}).json()["items"] == []
