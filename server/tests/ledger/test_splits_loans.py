"""Loan payments as principal plus interest (ADR-0017 decision 5, roadmap 10f-4). Fake data only."""

# ruff: noqa: F811  (fixtures imported from test_splits are used as arguments)

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_splits import URL, cats, checking, part, put  # noqa: F401

from app.models import Transaction

SUMMARY = "/api/local/summary/monthly"


@pytest.fixture
def loan(make_account):
    return make_account(name="Fake Mortgage", kind="loan")["id"]


@pytest.fixture
def payment(client, add_txn, checking, cats):  # noqa: F811
    """-$1,500 out of checking: $1,200 principal (Transfer) and $300 interest."""
    txn = add_txn(checking, -150_000)
    parts = [part(cats["Transfer"], -120_000), part(cats["Rent/Mortgage"], -30_000)]
    assert put(client, txn["id"], parts).status_code == 200
    return txn["id"]


@pytest.fixture
def deposit(add_txn, loan):
    return add_txn(loan, 120_000)["id"]


def link(client, one, other):
    return client.post(f"{URL}/{one}/transfer", json={"other_id": other})


def get(client, txn_id):
    return client.get(f"{URL}/{txn_id}").json()


def error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_link_sets_both_sides(client, payment, deposit, cats):  # noqa: F811
    assert link(client, payment, deposit).status_code == 200
    split, loan_side = get(client, payment), get(client, deposit)
    assert (split["transfer_pair_id"], loan_side["transfer_pair_id"]) == (deposit, payment)
    assert (split["kind"], split["category_id"]) == ("normal", None)
    assert len(split["splits"]) == 2 and split["transfer_type"] == "loan_payment"
    assert (loan_side["kind"], loan_side["category_id"]) == ("transfer", cats["Transfer"])
    assert loan_side["transfer_type"] == "loan_payment"


def test_link_works_from_the_loan_side_too(client, payment, deposit):
    assert link(client, deposit, payment).status_code == 200
    assert get(client, payment)["transfer_pair_id"] == deposit


def test_interest_counts_as_spending_and_principal_does_not(
    client,
    add_txn,
    checking,
    cats,
    payment,
    deposit,  # noqa: F811
):
    add_txn(checking, 300_000, category_id=cats["Paycheck"], description="FAKE PAY")
    before = client.get(SUMMARY, params={"month": "2026-01"}).json()
    assert link(client, payment, deposit).status_code == 200
    after = client.get(SUMMARY, params={"month": "2026-01"}).json()
    assert after["spending_cents"] == before["spending_cents"] == 30_000
    assert after["income_cents"] == before["income_cents"]
    assert after["unassigned_count"] == 0
    assert {c["name"]: c["actual_cents"] for c in after["categories"]}["Rent/Mortgage"] == 30_000
    assert after.get("saved_cents", 0) == before.get("saved_cents", 0)


def test_unlink_restores_both_sides(client, payment, deposit):
    link(client, payment, deposit)
    assert client.delete(f"{URL}/{payment}/transfer").status_code == 200
    split, loan_side = get(client, payment), get(client, deposit)
    for side in (split, loan_side):
        assert (side["transfer_pair_id"], side["kind"]) == (None, "normal")
    assert loan_side["category_id"] is None and split["category_id"] is None
    assert len(split["splits"]) == 2
    assert client.delete(f"{URL}/{payment}").status_code == 204  # deletable again


def _category_fields(txn):
    return (txn["category_id"], txn["category_source"], txn["sorted_by_rule_id"])


def test_unlink_gives_back_a_category_you_set(client, payment, deposit, cats):
    assert (
        client.patch(f"{URL}/{deposit}", json={"category_id": cats["Groceries"]}).status_code == 200
    )
    before = _category_fields(get(client, deposit))
    assert before[0] == cats["Groceries"] and before[1] is not None
    link(client, payment, deposit)
    assert get(client, deposit)["category_id"] == cats["Transfer"]
    client.delete(f"{URL}/{payment}/transfer")
    assert _category_fields(get(client, deposit)) == before


def test_unlink_gives_back_a_rule_sorted_category(client, add_txn, loan, payment, cats):
    rule = {"pattern": "FAKELOAN", "category_id": cats["Groceries"]}
    assert client.post("/api/local/category-rules", json=rule).status_code == 201
    dep = add_txn(loan, 120_000, description="FAKELOAN PMT")["id"]
    assert client.post("/api/local/category-rules/apply").status_code == 200
    before = _category_fields(get(client, dep))
    assert before[0] == cats["Groceries"] and before[2] is not None
    link(client, payment, dep)
    client.delete(f"{URL}/{payment}/transfer")
    assert _category_fields(get(client, dep)) == before


@pytest.mark.parametrize("kind", ["savings", "brokerage", "retirement", "hsa"])
def test_split_cannot_come_from_a_savings_type_account(
    client, add_txn, make_account, loan, cats, kind
):
    account = make_account(name="Fake Savings Type", kind=kind)["id"]
    txn = add_txn(account, -150_000)
    parts = [part(cats["Transfer"], -120_000), part(cats["Rent/Mortgage"], -30_000)]
    assert put(client, txn["id"], parts).status_code == 200
    response = link(client, txn["id"], add_txn(loan, 120_000)["id"])
    error(response, 422, "invalid_transfer")
    assert "everyday" in response.json()["error"]["message"]
    assert get(client, txn["id"])["transfer_pair_id"] is None


def test_locked_while_linked(client, payment, deposit, cats):  # noqa: F811
    link(client, payment, deposit)
    parts = [part(cats["Transfer"], -100_000), part(cats["Rent/Mortgage"], -50_000)]
    error(put(client, payment, parts), 409, "part_of_transfer")
    error(put(client, payment, []), 409, "part_of_transfer")
    for body in ({"amount_cents": -100}, {"category_id": cats["Groceries"]}, {"kind": "refund"}):
        error(client.patch(f"{URL}/{payment}", json=body), 409, "part_of_transfer")
    error(client.delete(f"{URL}/{payment}"), 409, "part_of_transfer")
    assert len(get(client, payment)["splits"]) == 2
    client.delete(f"{URL}/{payment}/transfer")
    assert put(client, payment, []).status_code == 200  # free again once unlinked


def test_other_side_must_be_a_loan(client, add_txn, make_account, payment):
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    error(link(client, payment, add_txn(savings, 120_000)["id"]), 409, "split_transaction")


def test_wrong_amount_is_refused(client, add_txn, loan, payment):
    error(link(client, payment, add_txn(loan, 150_000)["id"]), 422, "invalid_transfer")
    assert get(client, payment)["transfer_pair_id"] is None


def test_exactly_one_transfer_part_is_needed(client, add_txn, checking, loan, cats):  # noqa: F811
    two = add_txn(checking, -100_000)
    parts = [part(cats["Transfer"], -60_000), part(cats["Transfer"], -40_000)]
    assert put(client, two["id"], parts).status_code == 200
    error(link(client, two["id"], add_txn(loan, 60_000)["id"]), 422, "invalid_transfer")
    none = add_txn(checking, -100_000)
    assert (
        put(
            client, none["id"], [part(cats["Groceries"], -60_000), part(cats["Shopping"], -40_000)]
        ).status_code
        == 200
    )  # noqa: E501
    error(link(client, none["id"], add_txn(loan, 60_000)["id"]), 422, "invalid_transfer")


def test_a_loan_deposit_alone_still_needs_a_matching_payment(client, add_txn, checking, loan):  # noqa: F811
    plain = add_txn(checking, -120_000)
    assert link(client, plain["id"], add_txn(loan, 120_000)["id"]).status_code == 200


def test_other_refusals_stay(client, payment, deposit, add_txn, checking):  # noqa: F811
    error(link(client, payment, payment), 422, "invalid_transfer")
    error(link(client, payment, add_txn(checking, 120_000)["id"]), 422, "invalid_transfer")
    other_loan = add_txn(deposit and get(client, deposit)["account_id"], 120_000)["id"]
    link(client, payment, deposit)
    error(link(client, payment, other_loan), 409, "already_linked")


def test_matching_never_links_a_split(client, payment, deposit):
    client.post(f"{URL}/match-transfers")
    client.post(f"{URL}/match-again")
    assert get(client, payment)["transfer_pair_id"] is None
    assert get(client, deposit)["transfer_pair_id"] is None


def test_deleting_the_loan_side_is_refused_while_linked(client, payment, deposit):
    link(client, payment, deposit)
    error(client.delete(f"{URL}/{deposit}"), 409, "part_of_transfer")
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(Transaction.transfer_pair_id).where(Transaction.id == payment))
