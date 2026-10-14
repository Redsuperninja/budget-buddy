"""Accounts API, loopback-only access, and the shared error format. Fake data only."""

import datetime as dt

import pytest

from app.network import is_loopback_address

URL = "/api/local/accounts"


def test_account_crud(client, make_account):
    created = make_account(institution="Fake Bank", last4="1234", notes="test")
    assert created["balance_cents"] == 0
    assert created["transaction_count"] == 0
    account_id = created["id"]

    assert client.get(f"{URL}/{account_id}").json()["name"] == "Test Checking"
    assert [a["id"] for a in client.get(URL).json()] == [account_id]

    updated = client.patch(f"{URL}/{account_id}", json={"name": "Renamed", "notes": None})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["notes"] is None
    assert updated.json()["last4"] == "1234"  # untouched fields stay

    assert client.delete(f"{URL}/{account_id}").status_code == 204
    missing = client.get(f"{URL}/{account_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_balance_is_sum_of_transactions(client, add_txn, make_account):
    checking = make_account()["id"]
    other = make_account(name="Other", kind="savings")["id"]
    add_txn(checking, 100_000, kind="adjustment")  # starting balance
    add_txn(checking, -2_550)
    add_txn(checking, 1_000, kind="refund")
    add_txn(other, 7_00)

    account = client.get(f"{URL}/{checking}").json()
    assert account["balance_cents"] == 98_450
    assert account["transaction_count"] == 3
    balances = {a["id"]: a["balance_cents"] for a in client.get(URL).json()}
    assert balances == {checking: 98_450, other: 700}


# Credit card sign convention (docs/dev/architecture/ledger.md, "Signs and balances"): a
# negative card balance is money owed. Charges are negative; payments and refunds are positive.
CARD_EXAMPLE = [
    # (account, amount_cents, kind, transfer link key)
    ("checking", 200_000, "adjustment", None),  # opening balance $2,000.00
    ("checking", -30_000, "normal", "payment"),  # card payment out of checking
    ("card", -12_000, "normal", None),  # charge
    ("card", -25_000, "normal", None),  # charge
    ("card", 2_000, "refund", None),  # refund lowers what you owe
    ("card", 30_000, "normal", "payment"),  # the payment arriving on the card
]


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (CARD_EXAMPLE, {"checking": 170_000, "card": -5_000, "total": 165_000}),
        (
            CARD_EXAMPLE[:1] + CARD_EXAMPLE[2:4],
            {"checking": 200_000, "card": -37_000, "total": 163_000},
        ),
    ],
)
def test_credit_card_balance_is_negative_when_owed(client, add_txn, make_account, rows, expected):
    ids = {
        "checking": make_account(name="Checking", kind="checking")["id"],
        "card": make_account(name="Card", kind="credit_card")["id"],
    }
    links: dict[str, list[int]] = {}
    for account, amount, kind, link in rows:
        txn = add_txn(ids[account], amount, kind=kind)
        if link:
            links.setdefault(link, []).append(txn["id"])
    for first, second in links.values():
        linked = client.post(f"/api/local/transactions/{first}/transfer", json={"other_id": second})
        assert linked.status_code == 200, linked.text

    balances = {a["name"].lower(): a["balance_cents"] for a in client.get(URL).json()}
    assert balances == {"checking": expected["checking"], "card": expected["card"]}
    assert sum(balances.values()) == expected["total"]  # net worth is a plain sum


def test_delete_blocked_when_account_has_transactions(client, add_txn, make_account):
    account_id = make_account()["id"]
    add_txn(account_id, -500)
    response = client.delete(f"{URL}/{account_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_has_transactions"
    assert client.get(f"{URL}/{account_id}").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "checking"},
        {"name": "  ", "kind": "checking"},
        {"name": "X", "kind": "piggy_bank"},
        {"name": "X", "kind": "checking", "last4": "12345"},
        {"name": "X", "kind": "checking", "surprise": 1},
    ],
)
def test_account_validation_errors(client, body):
    response = client.post(URL, json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"].startswith("Please check ")


def test_account_name_cannot_be_cleared(client, make_account):
    account_id = make_account()["id"]
    response = client.patch(f"{URL}/{account_id}", json={"name": None})
    assert response.status_code == 422
    assert "name can't be empty" in response.json()["error"]["message"]


@pytest.mark.parametrize("host", ["192.168.1.20", "10.0.0.5", "fe80::1", "::ffff:192.168.1.20"])
def test_local_api_rejects_non_loopback_clients(make_client, host):
    lan = make_client(host)
    for method, path in [
        ("get", URL),
        ("post", URL),
        ("get", "/api/local/transactions"),
        ("delete", "/api/local/transactions/1"),
    ]:
        response = lan.request(method, path, json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_this_computer"


def test_local_api_ignores_forwarded_for_header(make_client):
    lan = make_client("192.168.1.20")
    response = lan.get(URL, headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403


def test_local_api_allows_ipv6_loopback(make_client):
    assert make_client("::1").get(URL).status_code == 200


@pytest.mark.parametrize(
    ("host", "expected"),
    [("127.0.0.1", True), ("127.5.5.5", True), ("::1", True), ("::ffff:127.0.0.1", True)]
    + [("192.168.1.2", False), ("::ffff:10.0.0.1", False), ("localhost", False), (None, False)],
)
def test_is_loopback_address(host, expected):
    assert is_loopback_address(host) is expected


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/local/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_account_number_and_notes_are_encrypted_on_disk(client, make_account, data_dir):
    """The API still works with encrypted columns (ADR-0003), and the file holds no plain text."""
    import sqlite3

    created = make_account(last4="9876", notes="FAKE-NOTE-xyz")
    assert client.get(f"{URL}/{created['id']}").json()["last4"] == "9876"
    connection = sqlite3.connect(data_dir / "budget.db")
    try:
        last4, notes = connection.execute(
            "SELECT last4, notes FROM accounts WHERE id = ?", (created["id"],)
        ).fetchone()
    finally:
        connection.close()
    assert isinstance(last4, bytes) and b"9876" not in last4
    assert isinstance(notes, bytes) and b"FAKE-NOTE" not in notes


def test_a_bill_dated_ahead_doesnt_lower_todays_balance(client, make_account, add_txn):
    account = make_account(name="Fake Checking", kind="checking")["id"]
    today = dt.date.today()
    add_txn(account, 100_000, date=today.isoformat(), description="Fake opening")
    add_txn(account, -2_500, date=today.isoformat(), description="Fake coffee today")
    add_txn(
        account, -40_000, date=(today + dt.timedelta(days=1)).isoformat(), description="Fake rent"
    )

    got = client.get(f"/api/local/accounts/{account}").json()
    assert (got["current_balance_cents"], got["balance_cents"]) == (97_500, 57_500)
    [listed] = client.get("/api/local/accounts").json()
    assert listed["current_balance_cents"] == 97_500
