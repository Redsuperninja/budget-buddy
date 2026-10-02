"""Accounts API, loopback-only access, and the shared error format. Fake data only."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
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
def test_local_api_rejects_non_loopback_clients(data_dir, host):
    lan = TestClient(create_app(), client=(host, 50000))
    for method, path in [
        ("get", URL),
        ("post", URL),
        ("get", "/api/local/transactions"),
        ("delete", "/api/local/transactions/1"),
    ]:
        response = lan.request(method, path, json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_this_computer"


def test_local_api_ignores_forwarded_for_header(data_dir):
    lan = TestClient(create_app(), client=("192.168.1.20", 50000))
    response = lan.get(URL, headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403


def test_local_api_allows_ipv6_loopback(data_dir):
    assert TestClient(create_app(), client=("::1", 50000)).get(URL).status_code == 200


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
