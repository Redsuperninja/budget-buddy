"""Transaction splits (ADR-0017, roadmap 10f-1): storage, rules, route, locks. Fake data only."""

import pytest
from crypto_helpers import raw_rows
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Transaction, TransactionSplit

URL = "/api/local/transactions"
CATS = "/api/local/categories"


@pytest.fixture
def checking(make_account):
    return make_account()["id"]


@pytest.fixture
def cats(client):
    with Session(client.app.state.engine) as session:
        return {c.name: c.id for c in session.scalars(select(Category))}


def part(category_id, cents, note=None):
    return {"category_id": category_id, "amount_cents": cents, "note": note}


def put(client, txn_id, parts):
    return client.put(f"{URL}/{txn_id}/splits", json={"splits": parts})


def two_parts(cats, total=-10_000):
    first = total // 4 * 3 if total % 4 == 0 else total - 1
    return [part(cats["Groceries"], first), part(cats["Shopping"], total - first)]


def split_txn(client, add_txn, checking, cats, **extra):
    txn = add_txn(checking, -10_000, category_id=cats["Dining Out"], **extra)
    assert put(client, txn["id"], two_parts(cats)).status_code == 200
    return txn["id"]


def test_split_shows_parts_and_clears_the_category(client, add_txn, checking, cats):
    txn = add_txn(checking, -10_000, category_id=cats["Dining Out"])
    assert txn["splits"] == []
    parts = [part(cats["Groceries"], -7_500, "food"), part(cats["Shopping"], -2_500)]
    response = put(client, txn["id"], parts)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["splits"] == parts
    assert (body["category_id"], body["category_source"], body["sorted_by_rule_id"]) == (
        None,
        None,
        None,
    )
    assert client.get(f"{URL}/{txn['id']}").json()["splits"] == parts
    listed = client.get(URL).json()["items"][0]
    assert listed["splits"] == parts


def test_replace_swaps_the_whole_list_and_undo_clears_it(client, add_txn, checking, cats):
    txn_id = split_txn(client, add_txn, checking, cats)
    again = [
        part(cats["Utilities"], -4_000),
        part(cats["Travel"], -3_000),
        part(cats["Groceries"], -3_000),
    ]
    assert put(client, txn_id, again).json()["splits"] == again
    undone = put(client, txn_id, [])
    assert undone.status_code == 200
    assert undone.json()["splits"] == [] and undone.json()["category_id"] is None
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(TransactionSplit)).all() == []
    assert put(client, txn_id, []).status_code == 200  # undoing an unsplit one is harmless


def test_refund_and_income_can_be_split_with_positive_parts(client, add_txn, checking, cats):
    refund = add_txn(checking, 5_000, kind="refund")
    parts = [part(cats["Groceries"], 3_000), part(cats["Shopping"], 2_000)]
    assert put(client, refund["id"], parts).status_code == 200


@pytest.mark.parametrize(
    "amounts",
    [
        [-10_000],  # one part
        [-5_000, -4_999],  # too little
        [-5_000, -5_001],  # too much
        [-10_000, 0, 0],  # zero parts
        [10_000, -20_000],  # wrong sign
        [-1] * 21,  # too many
    ],
)
def test_bad_parts_are_refused(client, add_txn, checking, cats, amounts):
    txn = add_txn(checking, -10_000, category_id=cats["Dining Out"])
    response = put(client, txn["id"], [part(cats["Groceries"], a) for a in amounts])
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_split"
    after = client.get(f"{URL}/{txn['id']}").json()
    assert after["splits"] == [] and after["category_id"] == cats["Dining Out"]  # nothing changed


def test_twenty_parts_is_the_most_allowed(client, add_txn, checking, cats):
    txn = add_txn(checking, -2_000)
    assert put(client, txn["id"], [part(cats["Groceries"], -100)] * 20).status_code == 200


def test_unknown_category_and_unknown_transaction_are_404(client, add_txn, checking, cats):
    txn = add_txn(checking, -10_000)
    assert (
        put(client, txn["id"], [part(cats["Groceries"], -5_000), part(99_999, -5_000)]).status_code
        == 404
    )
    assert put(client, 99_999, two_parts(cats)).status_code == 404


def test_an_adjustment_cannot_be_split(client, add_txn, checking, cats):
    adjustment = add_txn(checking, -10_000, kind="adjustment")
    assert put(client, adjustment["id"], two_parts(cats)).status_code == 409


def test_a_transfer_cannot_be_split(client, add_txn, make_account, checking, cats):
    into = add_txn(make_account(name="Savings", kind="savings")["id"], 10_000)
    out = add_txn(checking, -10_000)
    link = client.post(f"{URL}/{out['id']}/transfer", json={"other_id": into["id"]})
    assert link.status_code == 200, link.text
    for side in (out, into):
        assert (
            put(
                client, side["id"], two_parts(cats, 10_000 * (1 if side is into else -1))
            ).status_code
            == 409
        )


def test_a_donation_cannot_be_split(client, add_txn, checking, cats):
    paid = add_txn(checking, -4_000, description="FAKE FOOD BANK")
    gift = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": paid["id"]}  # fmt: skip
    assert client.post("/api/local/donations", json=gift).status_code == 201
    assert put(client, paid["id"], two_parts(cats, -4_000)).status_code == 409


def test_a_pay_deposit_cannot_be_split(client, add_txn, checking, cats):
    pay = add_txn(checking, 250_000, date="2026-03-13", description="FAKECO INC PAYROLL PPD ID: 1")
    stub = {"pay_date": "2026-03-13", "employer": "FakeCo", "gross_cents": 300_000}
    stub |= {"federal_tax_cents": 50_000, "net_cents": 250_000, "deposit_transaction_id": pay["id"]}
    assert client.post("/api/local/paychecks", json=stub).status_code == 201
    assert put(client, pay["id"], two_parts(cats, 250_000)).status_code == 409


def test_a_stock_trade_cannot_be_split(client, add_txn, make_account, cats):
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    paid = add_txn(brokerage, -20_000, date="2026-03-02", description="YOU BOUGHT FAKE")
    lot = {"symbol": "FAKE", "acquired_on": "2026-03-02", "shares": "2", "cost_basis_cents": 20_000,
           "transaction_id": paid["id"]}  # fmt: skip
    assert client.post("/api/local/stocks/lots", json=lot).status_code == 201
    assert put(client, paid["id"], two_parts(cats, -20_000)).status_code == 409


def test_a_dividend_cannot_be_split(client, add_txn, make_account, cats):
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    dividend = add_txn(ira, 130, date="2026-09-08", description="FAKECO CASH DIV")
    assert client.get("/api/local/dividends/2026").json()["dividends"]
    assert (
        put(
            client, dividend["id"], [part(cats["Interest"], 100), part(cats["Other Income"], 30)]
        ).status_code
        == 409
    )


def test_category_or_amount_of_a_split_is_locked(client, add_txn, checking, cats):
    txn_id = split_txn(client, add_txn, checking, cats)
    for change in (
        {"category_id": cats["Groceries"]},
        {"amount_cents": -9_000},
        {"amount": "90.00"},
    ):
        response = client.patch(f"{URL}/{txn_id}", json=change)
        assert response.status_code == 409, change
        assert response.json()["error"]["code"] == "split_transaction"
        assert "split" in response.json()["error"]["message"]
    # Values it already has, and other fields, are fine.
    assert (
        client.patch(
            f"{URL}/{txn_id}", json={"category_id": None, "amount_cents": -10_000}
        ).status_code
        == 200
    )
    assert (
        client.patch(f"{URL}/{txn_id}", json={"description": "Renamed", "notes": "n"}).status_code
        == 200
    )
    after = client.get(f"{URL}/{txn_id}").json()
    assert (
        after["amount_cents"] == -10_000
        and after["category_id"] is None
        and len(after["splits"]) == 2
    )
    # After undoing the split, they can be edited again.
    put(client, txn_id, [])
    assert (
        client.patch(
            f"{URL}/{txn_id}", json={"category_id": cats["Groceries"], "amount_cents": -9_000}
        ).status_code
        == 200
    )


def test_sum_rule_holds_on_every_write_path(client, add_txn, checking, cats):
    """Parts always add up: the only ways to change a split's amount are refused or go through
    replace, which checks the sum."""
    txn_id = split_txn(client, add_txn, checking, cats)
    assert client.patch(f"{URL}/{txn_id}", json={"amount_cents": -10_001}).status_code == 409
    assert client.patch(f"{URL}/{txn_id}", json={"kind": "refund"}).status_code == 409
    assert (
        put(
            client, txn_id, [part(cats["Groceries"], -9_998), part(cats["Shopping"], -1)]
        ).status_code
        == 422
    )
    with Session(client.app.state.engine) as session:
        txn = session.get(Transaction, txn_id)
        assert sum(p.amount_cents for p in txn.splits) == txn.amount_cents == -10_000


def test_category_used_by_a_part_cannot_be_deleted(client, add_txn, checking, cats):
    split_txn(client, add_txn, checking, cats)
    assert client.delete(f"{CATS}/{cats['Shopping']}").status_code == 409
    assert client.delete(f"{CATS}/{cats['Utilities']}").status_code == 204


def test_deleting_the_transaction_deletes_its_parts(client, add_txn, checking, cats):
    txn_id = split_txn(client, add_txn, checking, cats)
    assert client.delete(f"{URL}/{txn_id}").status_code == 204
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(TransactionSplit)).all() == []
    assert client.delete(f"{CATS}/{cats['Shopping']}").status_code == 204  # no longer in use


def test_note_is_encrypted_at_rest(client, add_txn, checking, cats, data_dir):
    txn = add_txn(checking, -10_000)
    secret = "fake-secret-note-for-gift"
    parts = [part(cats["Groceries"], -7_500, secret), part(cats["Shopping"], -2_500)]
    assert put(client, txn["id"], parts).status_code == 200
    client.app.state.engine.dispose()
    rows = raw_rows(data_dir, "SELECT note FROM transaction_splits ORDER BY id")
    assert isinstance(rows[0][0], bytes) and secret.encode() not in rows[0][0]
    assert rows[1][0] is None
    assert client.get(f"{URL}/{txn['id']}").json()["splits"][0]["note"] == secret


@pytest.mark.parametrize("peer", ["192.168.1.50", "10.0.0.7"])
def test_splitting_is_this_computer_only(make_client, peer):
    body = {"splits": []}
    assert make_client(peer=peer).put(f"{URL}/1/splits", json=body).status_code == 403
    evil = make_client(headers={"Origin": "http://evil.example"})
    assert evil.put(f"{URL}/1/splits", json=body).status_code == 403
