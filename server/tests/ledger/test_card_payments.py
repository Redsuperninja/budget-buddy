"""Credit card payments go in "Payments", on both sides, linked or not. Fake data only."""

import pytest

from app.services.ledger import transfer_matching, transfers
from app.services.ledger.transfer_categories import transfer_category_id

TXN = "/api/local/transactions"
CARD_SIDE = "PAYMENT THANK YOU"
BANK_SIDE = "FAKEBANK CREDIT CRD AUTOPAY"


@pytest.fixture
def checking(make_account) -> int:
    return make_account(name="Fake Checking", kind="checking")["id"]


@pytest.fixture
def card(make_account) -> int:
    return make_account(name="Fakebank Rewards", kind="credit_card")["id"]


def category_of(client, txn) -> dict | None:
    category_id = client.get(f"{TXN}/{txn['id']}").json()["category_id"]
    if category_id is None:
        return None
    return next(c for c in client.get("/api/local/categories").json() if c["id"] == category_id)


def needs_a_category(client) -> list[str]:
    items = client.get(TXN, params={"uncategorized": "true"}).json()["items"]
    return [t["description"] for t in items]


def test_a_linked_card_payment_goes_in_payments_on_both_sides(client, checking, card, add_txn):
    out = add_txn(checking, -30_000, date="2026-10-01", description=BANK_SIDE)
    into = add_txn(card, 30_000, date="2026-10-03", description=CARD_SIDE)
    for side in (out, into):
        got = client.get(f"{TXN}/{side['id']}").json()
        assert got["kind"] == "transfer"
        assert (category_of(client, side)["name"], category_of(client, side)["group"]) == (
            "Payments",
            "transfer",
        )


def test_each_side_on_its_own_goes_in_payments(client, checking, card, add_txn):
    into = add_txn(card, 30_000, date="2026-10-03", description=CARD_SIDE)
    out = add_txn(checking, -12_345, date="2026-10-20", description=BANK_SIDE)  # no other side
    assert category_of(client, into)["name"] == "Payments"
    assert category_of(client, out)["name"] == "Payments"
    assert needs_a_category(client) == []
    month = client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()
    assert (month["spending_cents"], month["income_cents"], month["unassigned_count"]) == (0, 0, 0)


def test_without_a_card_account_the_bank_side_still_counts(client, checking, add_txn):
    out = add_txn(checking, -12_345, date="2026-10-20", description=BANK_SIDE)
    assert category_of(client, out) is None
    assert needs_a_category(client) == [BANK_SIDE]


@pytest.mark.parametrize(
    ("where", "cents", "description"),
    [
        ("card", 2_000, "FAKESHOP REFUND"),  # money back on the card, not a payment
        ("card", 2_000, "FAKESHOP"),  # no payment words
        ("checking", -5_000, "ONLINE TRANSFER TO SAVINGS"),  # names no card
        ("checking", -5_000, "FAKE UTILITY AUTOPAY"),  # a bill, names no card
        ("checking", 5_000, "FAKEBANK CREDIT CRD AUTOPAY"),  # money in, not a payment out
        # Debit-card purchases say "card" and "payment" too: real spending.
        ("checking", -1_599, "RECURRING PAYMENT AUTHORIZED ON 09/30 FAKEFLIX.COM CARD 1234"),
        ("checking", -2_500, "DEBIT CARD PAYMENT FAKE PHARMACY"),
        ("hsa", -2_500, "DEBIT CARD PAYMENT FAKE PHARMACY"),
        ("checking", -900, "POS PURCHASE CARD 1234 FAKE CAFE ACH"),
        # Lenders that also issue cards: a loan payment or a move to savings.
        ("checking", -20_000, "DISCOVER STUDENT LOANS PAYMENT"),
        ("checking", -20_000, "CAPITAL ONE AUTO LOAN PMT"),
        ("checking", -20_000, "DISCOVER BANK ACH TRANSFER"),
        ("checking", -20_000, "FAKEBANK DISCOVER PERSONAL LOANS ACH PMT"),
        ("checking", -20_000, "FAKEBANK SYNCHRONY BANK ACH TRANSFER"),
        ("card", 4_000, "FAKESHOP PAYMENT ADJ"),  # a merchant's credit, not your payment
        ("card", 4_000, "ACH CREDIT MERCHANT"),
        ("checking", -1_200, "CREDIT CARD INTEREST PAYMENT"),  # interest
        ("loan", 20_000, "PAYMENT THANK YOU"),  # a loan's own lines
        ("card", -4_000, "RETURNED PAYMENT FEE"),  # a real charge
    ],
)
def test_other_lines_are_left_alone(
    client, checking, card, make_account, add_txn, where, cents, description
):
    hsa = make_account(name="Fake HSA", kind="hsa")["id"]
    loan = make_account(name="Fake Loan", kind="loan")["id"]
    account = {"card": card, "checking": checking, "hsa": hsa, "loan": loan}[where]
    txn = add_txn(account, cents, date="2026-10-05", description=description)
    assert category_of(client, txn) is None


def test_your_category_is_respected(client, checking, card, add_txn):
    wants = next(c for c in client.get("/api/local/categories").json() if c["group"] == "wants")
    out = add_txn(checking, -12_345, description=BANK_SIDE, category_id=wants["id"])
    assert category_of(client, out)["id"] == wants["id"]


def test_older_linked_card_payments_move_to_payments(client, checking, card, add_txn, monkeypatch):
    # Linked before this change: in "Transfer", and nothing filed under "Payments".
    monkeypatch.setattr(
        transfers, "pair_category", lambda s, a, b, known=None: transfer_category_id(s)
    )
    monkeypatch.setattr(transfer_matching, "file_card_payments", lambda *_: 0)
    out = add_txn(checking, -30_000, date="2026-10-01", description=BANK_SIDE)
    add_txn(card, 30_000, date="2026-10-02", description=CARD_SIDE)
    assert category_of(client, out)["name"] == "Transfer"
    monkeypatch.undo()

    client.post("/api/local/transactions/match-again")
    assert category_of(client, out)["name"] == "Payments"


def test_a_payments_category_of_your_own_elsewhere_is_never_used(client, checking, card, add_txn):
    made = client.post("/api/local/categories", json={"name": "payments", "group": "needs"})
    assert made.status_code == 201, made.text
    out = add_txn(checking, -30_000, date="2026-10-01", description=BANK_SIDE)
    add_txn(card, 30_000, date="2026-10-02", description=CARD_SIDE)
    got = category_of(client, out)
    assert (got["name"], got["group"]) == ("Transfer", "transfer"), (got, made.json())


def test_unlinking_puts_the_category_back(client, checking, card, add_txn):
    out = add_txn(checking, -30_000, date="2026-10-01", description=BANK_SIDE)
    add_txn(card, 30_000, date="2026-10-02", description=CARD_SIDE)
    assert client.delete(f"{TXN}/{out['id']}/transfer").status_code == 200
    assert category_of(client, out)["name"] == "Payments"  # its category from before the link


def test_a_payment_from_savings_goes_in_payments(client, card, make_account, add_txn):
    make_account(name="American Express Gold", kind="credit_card")
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    out = add_txn(savings, -5_000, date="2026-10-05", description="AMEX EPAYMENT ACH PMT")
    assert category_of(client, out)["name"] == "Payments"


def test_a_returned_payment_is_filed_with_the_payments(client, checking, card, add_txn):
    back = add_txn(
        checking, 30_000, date="2026-10-09", description="FAKEBANK CREDIT CARD PAYMENT RETURNED"
    )
    undone = add_txn(card, -30_000, date="2026-10-09", description="PAYMENT RETURNED")
    assert category_of(client, back)["name"] == "Payments"
    assert category_of(client, undone)["name"] == "Payments"
    month = client.get("/api/local/summary/monthly", params={"month": "2026-10"}).json()
    assert (month["income_cents"], month["spending_cents"], month["unassigned_count"]) == (0, 0, 0)


def test_a_pair_you_unlinked_is_left_alone(client, checking, card, add_txn):
    out = add_txn(checking, -30_000, date="2026-10-01", description="TRANSFER TO FAKE CARD")
    add_txn(card, 30_000, date="2026-10-02", description=CARD_SIDE)
    client.delete(f"{TXN}/{out['id']}/transfer")
    client.post("/api/local/transactions/match-again")
    assert category_of(client, out) is None  # not a card-worded line, and you unlinked it


def test_a_payment_to_a_card_you_havent_added_still_counts(client, checking, card, add_txn):
    out = add_txn(checking, -12_000, date="2026-10-05", description="AMEX EPAYMENT ACH PMT")
    assert category_of(client, out) is None  # only Fakebank's card is in Budget Buddy


def test_a_line_you_take_out_of_payments_stays_out(client, checking, card, add_txn):
    out = add_txn(checking, -12_345, date="2026-10-20", description=BANK_SIDE)
    assert category_of(client, out)["name"] == "Payments"
    client.patch(f"{TXN}/{out['id']}", json={"category_id": None})
    client.post("/api/local/transactions/match-again")
    assert category_of(client, out) is None
    assert needs_a_category(client) == [BANK_SIDE]


def test_other_transfers_never_land_in_payments(client, checking, card, make_account, add_txn):
    add_txn(checking, -12_345, date="2026-10-20", description=BANK_SIDE)  # makes "Payments"
    [transfer] = [c for c in client.get("/api/local/categories").json() if c["name"] == "Transfer"]
    renamed = client.patch(f"/api/local/categories/{transfer['id']}", json={"name": "Moves"})
    assert renamed.status_code == 200, renamed.text
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    out = add_txn(checking, -5_000, date="2026-10-21", description="ONLINE TRANSFER TO SAVINGS")
    add_txn(savings, 5_000, date="2026-10-21", description="ONLINE TRANSFER FROM CHECKING")
    assert client.get(f"{TXN}/{out['id']}").json()["kind"] == "transfer"
    assert category_of(client, out)["name"] == "Moves"  # the transfer group's other one
