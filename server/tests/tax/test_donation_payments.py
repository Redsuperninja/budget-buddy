"""Sorting a transaction into charity: linking a donation to its payment. Fake data only."""

import datetime as dt

import pytest
from alembic import command
from sqlalchemy import text

from app.db import alembic_config, create_db_engine
from app.schemas.tax import donations as donation_schemas
from app.services.tax import donations as donation_service
from app.services.tax.donation_payments import part_gift_proof

URL = "/api/local/donations"
TXN_URL = "/api/local/transactions"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(donation_schemas, "_today", lambda: dt.date(2030, 1, 1))


@pytest.fixture
def payment(add_txn, checking) -> dict:
    """A $40.00 card payment to a fake charity."""
    return add_txn(checking, -4_000, description="FAKE FOOD BANK")


def gift(payment_id: int | None, amount_cents: int = 4_000, kind: str = "cash") -> dict:
    return {
        "date": "2026-01-15",
        "organization": "Fake Food Bank",
        "kind": kind,
        "amount_cents": amount_cents,
        "transaction_id": payment_id,
    }


def error_code(response) -> str:
    return response.json()["error"]["code"]


def test_sort_a_payment_into_charity(client, payment):
    created = client.post(URL, json=gift(payment["id"]))
    assert created.status_code == 201, created.text
    assert created.json()["transaction_id"] == payment["id"]

    listed = client.get(TXN_URL).json()["items"]
    assert [t["donation_id"] for t in listed] == [created.json()["id"]]
    assert client.get(f"{TXN_URL}/{payment['id']}").json()["donation_id"] == created.json()["id"]


def test_a_gift_can_be_part_of_a_payment(client, payment):
    # A $40 fundraiser dinner where $25 is the gift.
    assert client.post(URL, json=gift(payment["id"], 2_500)).status_code == 201


def test_gift_bigger_than_payment_is_refused(client, payment):
    response = client.post(URL, json=gift(payment["id"], 4_001))
    assert response.status_code == 422
    assert error_code(response) == "invalid_payment"


def test_goods_cant_come_from_a_payment(client, payment):
    response = client.post(URL, json=gift(payment["id"], kind="goods"))
    assert response.status_code == 422
    assert "cash" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "overrides",
    [{"amount_cents": 4_000}, {"amount_cents": 4_000, "kind": "refund"}, {"kind": "adjustment"}],
)
def test_only_money_paid_out_can_be_a_gift(client, add_txn, checking, overrides):
    body = {"amount_cents": -4_000, **overrides}
    txn = add_txn(checking, body.pop("amount_cents"), **body)
    response = client.post(URL, json=gift(txn["id"]))
    assert response.status_code == 422
    assert error_code(response) == "invalid_payment"


def test_one_payment_backs_one_gift(client, payment):
    first = client.post(URL, json=gift(payment["id"], 1_000)).json()
    response = client.post(URL, json=gift(payment["id"], 1_000))
    assert response.status_code == 409
    assert error_code(response) == "already_linked"
    # Editing the gift that already holds the link is fine.
    assert client.patch(f"{URL}/{first['id']}", json={"amount_cents": 2_000}).status_code == 200


def test_two_saves_at_once_get_a_friendly_409(client, payment, monkeypatch):
    client.post(URL, json=gift(payment["id"], 1_000))
    # The second save passed the check before the first was saved; the unique index catches it.
    monkeypatch.setattr(donation_service, "check_payment", lambda *args, **kwargs: None)
    response = client.post(URL, json=gift(payment["id"], 1_000))
    assert response.status_code == 409
    assert error_code(response) == "already_linked"


@pytest.mark.parametrize(
    ("payment_cents", "gift_cents", "expected"),
    [
        (10_000, 6_000, ["quid_pro_quo_statement"]),  # $100 gala ticket, $60 gift
        (7_500, 4_000, ["quid_pro_quo_statement"]),  # got something back, whatever the size
        (4_000, 4_000, []),  # the whole payment was the gift
        (None, 4_000, []),  # typed in, not from a payment
    ],
)
def test_part_gift_proof(payment_cents, gift_cents, expected):
    assert [p.code for p in part_gift_proof(gift_cents, payment_cents)] == expected


def test_summary_asks_for_the_statement_on_a_part_gift(client, add_txn, checking):
    gala = add_txn(checking, -30_000, description="FAKE SHELTER GALA")
    client.post(URL, json=gift(gala["id"], 25_000))
    (row,) = client.get(f"{URL}/summary/2026").json()["donations"]
    codes = [p["code"] for p in row["proof_needed"]]
    # $250 gift part: written acknowledgment, plus the statement of what came back.
    assert codes == ["written_acknowledgment", "quid_pro_quo_statement"]
    assert "$300.00" in row["proof_needed"][1]["message"]


def test_unknown_payment_is_not_found(client):
    assert client.post(URL, json=gift(99_999)).status_code == 404


def test_patch_checks_the_final_values(client, payment):
    created = client.post(URL, json=gift(None, 5_000)).json()
    # $50 gift can't be linked to a $40 payment...
    linked = client.patch(f"{URL}/{created['id']}", json={"transaction_id": payment["id"]})
    assert linked.status_code == 422
    # ...unless the amount comes down in the same edit.
    both = {"transaction_id": payment["id"], "amount_cents": 4_000}
    assert client.patch(f"{URL}/{created['id']}", json=both).status_code == 200
    goods = client.patch(f"{URL}/{created['id']}", json={"kind": "goods"})
    assert goods.status_code == 422
    unlinked = client.patch(f"{URL}/{created['id']}", json={"transaction_id": None})
    assert unlinked.json()["transaction_id"] is None


def test_linked_payment_keeps_its_amount_and_type(client, payment):
    client.post(URL, json=gift(payment["id"]))
    for change in ({"amount_cents": -100}, {"kind": "refund", "amount_cents": 100}):
        response = client.patch(f"{TXN_URL}/{payment['id']}", json=change)
        assert response.status_code == 409
        assert error_code(response) == "linked_to_donation"
    # Other changes, like the description, are fine.
    fixed = client.patch(f"{TXN_URL}/{payment['id']}", json={"description": "Food bank"})
    assert fixed.status_code == 200


def test_linked_payment_cant_become_a_transfer(client, payment, make_account, add_txn):
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    into = add_txn(savings, 4_000)
    client.post(URL, json=gift(payment["id"]))
    response = client.post(f"{TXN_URL}/{payment['id']}/transfer", json={"other_id": into["id"]})
    assert response.status_code == 409
    assert error_code(response) == "linked_to_donation"


def test_deleting_the_payment_keeps_the_gift(client, payment):
    created = client.post(URL, json=gift(payment["id"])).json()
    assert client.delete(f"{TXN_URL}/{payment['id']}").status_code == 204
    kept = client.get(f"{URL}/{created['id']}").json()
    assert kept["transaction_id"] is None
    assert kept["amount_cents"] == 4_000


def test_migration_0012_round_trip_keeps_gifts(tmp_path):
    engine = create_db_engine(tmp_path)
    config = alembic_config()

    def migrate(direction, target):
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            getattr(command, direction)(config, target)

    # Stand-in ciphertext: the rebuild must copy the encrypted notes bytes exactly.
    notes = b"\x01fake-ciphertext\x00\xff"
    insert = (
        "INSERT INTO donations (id, date, organization, amount_cents, kind, notes) "
        "VALUES (1, '2026-01-15', 'Fake Food Bank', 4000, 'cash', :notes)"
    )
    read = "SELECT amount_cents, transaction_id, notes FROM donations"
    try:
        migrate("upgrade", "0011")
        with engine.begin() as conn:
            conn.execute(text(insert), {"notes": notes})
        migrate("upgrade", "0012")
        with engine.connect() as conn:
            row = conn.execute(text(read)).one()
        assert tuple(row) == (4000, None, notes)
        migrate("downgrade", "0011")
        with engine.connect() as conn:
            columns = [r[1] for r in conn.execute(text("PRAGMA table_info(donations)"))]
            kept = conn.execute(text("SELECT notes FROM donations")).scalar()
        assert "transaction_id" not in columns
        assert kept == notes
    finally:
        engine.dispose()
