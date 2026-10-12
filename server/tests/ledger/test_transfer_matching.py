"""Automatic transfer matching and what kind each transfer is. Fake data only."""

import pytest

from app.models import AccountKind
from app.transfer_types import TransferType, classify

TXN = "/api/local/transactions"
MATCH = f"{TXN}/match-transfers"


@pytest.fixture
def accounts(make_account) -> dict[str, int]:
    kinds = ["checking", "savings", "credit_card", "brokerage", "retirement", "hsa", "loan"]
    return {k: make_account(name=f"Fake {k}", kind=k)["id"] for k in kinds}


def add(
    client, account_id, cents, date="2026-03-02", description="ONLINE TRANSFER PAYMENT", **extra
):
    body = {
        "account_id": account_id,
        "amount_cents": cents,
        "date": date,
        "description": description,
    }
    response = client.post(TXN, json=body | extra)
    assert response.status_code == 201, response.text
    return response.json()


def get(client, txn) -> dict:
    return client.get(f"{TXN}/{txn['id']}").json()


@pytest.mark.parametrize(
    ("into", "expected"),
    [
        ("credit_card", "card_payment"),
        ("savings", "to_savings"),
        ("brokerage", "to_investments"),
        ("retirement", "to_retirement"),
        ("hsa", "to_hsa"),
        ("loan", "loan_payment"),
    ],
)
def test_entering_both_sides_links_and_classifies(client, accounts, into, expected):
    out = add(client, accounts["checking"], -25_000)
    back = add(client, accounts[into], 25_000, date="2026-03-04")  # shows up two days later
    assert back["kind"] == "transfer" and back["transfer_type"] == expected
    assert get(client, out)["transfer_pair_id"] == back["id"]
    assert get(client, out)["transfer_type"] == expected


def test_money_back_out_of_savings(client, accounts):
    add(client, accounts["savings"], -10_000)
    back = add(client, accounts["checking"], 10_000)
    assert back["transfer_type"] == "from_savings"


def test_too_far_apart_or_different_amounts_dont_match(client, accounts):
    add(client, accounts["checking"], -5_000, date="2026-03-01")
    late = add(client, accounts["savings"], 5_000, date="2026-03-07")  # 6 days
    other = add(client, accounts["savings"], 4_999, date="2026-03-01")
    assert get(client, late)["kind"] == "normal" and get(client, other)["kind"] == "normal"


def test_a_tie_is_left_for_you(client, accounts):
    add(client, accounts["checking"], -5_000, date="2026-03-02")
    add(client, accounts["savings"], 5_000, date="2026-03-01")
    tied = add(client, accounts["brokerage"], 5_000, date="2026-03-03")  # also 1 day away
    assert get(client, tied)["kind"] == "normal"
    assert client.post(MATCH).json() == {"matched": 0}


def test_the_closest_date_wins(client, accounts):
    near = add(client, accounts["savings"], 5_000, date="2026-03-02")
    add(client, accounts["brokerage"], 5_000, date="2026-03-05")
    out = add(client, accounts["checking"], -5_000, date="2026-03-02")
    assert get(client, out)["transfer_pair_id"] == near["id"]


def test_same_account_and_card_spending_dont_match(client, accounts):
    add(client, accounts["checking"], -3_000)
    same = add(client, accounts["checking"], 3_000)
    add(client, accounts["credit_card"], -2_000)  # a card charge doesn't send money anywhere
    refund = add(client, accounts["checking"], 2_000)
    assert get(client, same)["kind"] == "normal" and get(client, refund)["kind"] == "normal"


def test_a_category_you_picked_is_respected(client, accounts):
    food = client.post("/api/local/categories", json={"name": "Fake Food", "group": "needs"})
    add(client, accounts["checking"], -3_000, category_id=food.json()["id"])
    back = add(client, accounts["savings"], 3_000)
    assert back["kind"] == "normal"


def test_five_days_apart_still_matches(client, accounts):
    add(client, accounts["checking"], -5_000, date="2026-03-01")
    back = add(client, accounts["retirement"], 5_000, date="2026-03-06")  # a long weekend
    assert back["kind"] == "transfer"


@pytest.mark.parametrize(
    ("out_text", "in_text"),
    [
        ("FAKE FOOD BANK", "FAKE DEPOSIT"),  # nothing says transfer: a coincidence
        ("ONLINE TRANSFER", "DIVIDEND FAKE FUND"),  # a dividend, not your money moved
        ("ONLINE TRANSFER", "EMPLOYER MATCH"),
        ("ONLINE TRANSFER", "PAYROLL FAKE CO"),
    ],
)
def test_coincidences_dont_match(client, accounts, out_text, in_text):
    add(client, accounts["checking"], -5_000, description=out_text)
    back = add(client, accounts["brokerage"], 5_000, description=in_text)
    assert back["kind"] == "normal"


def test_a_card_refund_is_not_a_payment(client, accounts):
    add(client, accounts["checking"], -3_000, description="ONLINE TRANSFER")
    refund = add(client, accounts["credit_card"], 3_000, description="FAKE STORE CREDIT")
    assert refund["kind"] == "normal"
    payment = add(client, accounts["credit_card"], 3_000, description="PAYMENT THANK YOU")
    assert payment["transfer_type"] == "card_payment"


def test_rule_sorted_transactions_are_left_alone(client, accounts):
    food = client.post("/api/local/categories", json={"name": "Fake Food", "group": "needs"})
    client.post(
        "/api/local/category-rules", json={"pattern": "MART", "category_id": food.json()["id"]}
    )
    add(client, accounts["checking"], -3_000, description="FAKE MART PAYMENT")
    back = add(client, accounts["savings"], 3_000, description="TRANSFER")
    assert back["kind"] == "normal"


def test_undo_puts_the_category_back(client, accounts):
    transfer_category = next(
        c["id"] for c in client.get("/api/local/categories").json() if c["group"] == "transfer"
    )
    out = add(client, accounts["checking"], -7_000)
    back = add(client, accounts["savings"], 7_000)
    assert get(client, out)["category_id"] == transfer_category
    client.delete(f"{TXN}/{out['id']}/transfer")
    for side in (out, back):
        undone = get(client, side)
        assert (undone["kind"], undone["category_id"]) == ("normal", None)


def test_unlinking_is_remembered(client, accounts):
    out = add(client, accounts["checking"], -7_000)
    add(client, accounts["savings"], 7_000)
    client.delete(f"{TXN}/{out['id']}/transfer")
    assert client.post(MATCH).json() == {"matched": 0}
    assert get(client, out)["auto_transfer_off"] is True
    # Linking it yourself still works.
    other = get(client, out)
    partner = client.get(TXN, params={"account_id": accounts["savings"]}).json()["items"][0]
    linked = client.post(f"{TXN}/{other['id']}/transfer", json={"other_id": partner["id"]})
    assert linked.json()["transfer_type"] == "to_savings"


def test_find_transfers_in_older_data(client, accounts, monkeypatch):
    from app.routers.ledger import transactions as router

    monkeypatch.setattr(router, "match_transfers", lambda session, only=None: 0)
    add(client, accounts["checking"], -9_000)
    add(client, accounts["savings"], 9_000)
    monkeypatch.undo()
    assert client.post(MATCH).json() == {"matched": 1}
    assert client.post(MATCH).json() == {"matched": 0}


def test_matched_saving_counts_as_saved(client, accounts):
    add(client, accounts["checking"], -20_000, date="2026-03-02")
    add(client, accounts["retirement"], 20_000, date="2026-03-03")
    summary = client.get("/api/local/summary/monthly", params={"month": "2026-03"}).json()
    assert summary["saved_by_transfer_cents"] == 20_000
    assert summary["spending_cents"] == 0


def test_a_donation_is_left_alone(client, accounts, monkeypatch):
    from app.schemas.tax import donations as donation_schemas

    monkeypatch.setattr(donation_schemas, "_today", lambda: __import__("datetime").date(2030, 1, 1))
    gift = add(client, accounts["checking"], -4_000, description="ONLINE PAYMENT FAKE CHARITY")
    client.post("/api/local/donations", json={"date": "2026-03-02", "organization": "Fake",
                                                "kind": "cash", "amount_cents": 4_000,
                                                "transaction_id": gift["id"]})  # fmt: skip
    add(client, accounts["savings"], 4_000)
    assert get(client, gift)["kind"] == "normal"


@pytest.mark.parametrize(
    ("from_kind", "to_kind", "expected"),
    [
        (AccountKind.SAVINGS, AccountKind.CREDIT_CARD, TransferType.CARD_PAYMENT),
        (AccountKind.BROKERAGE, AccountKind.CHECKING, TransferType.FROM_INVESTMENTS),
        (AccountKind.RETIREMENT, AccountKind.CHECKING, TransferType.FROM_RETIREMENT),
        (AccountKind.HSA, AccountKind.CASH, TransferType.FROM_HSA),
        (AccountKind.CHECKING, AccountKind.CASH, TransferType.BETWEEN_ACCOUNTS),
    ],
)
def test_classify(from_kind, to_kind, expected):
    assert classify(from_kind, to_kind) == expected
