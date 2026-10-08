"""Setting an account's balance to match the bank, with one balance adjustment. Fake data only."""

import datetime as dt


def url(account_id: int) -> str:
    return f"/api/local/accounts/{account_id}/balance"


def balance(client, account_id: int) -> int:
    return client.get(f"/api/local/accounts/{account_id}").json()["balance_cents"]


def test_todays_bank_balance_fills_in_the_difference(client, checking, add_txn):
    add_txn(checking, -2_500, date="2026-03-01")
    add_txn(checking, 10_000, date="2026-03-02")
    today = dt.date.today().isoformat()
    result = client.post(url(checking), json={"date": today, "balance": "1234.56"}).json()
    assert (result["balance_cents"], result["adjustment_cents"]) == (123_456, 123_456 - 7_500)
    assert balance(client, checking) == 123_456
    made = client.get(f"/api/local/transactions/{result['transaction_id']}").json()
    assert (made["kind"], made["date"], made["category_id"]) == ("adjustment", today, None)
    assert made["description"] == f"Balance set to $1,234.56 on {today}"


def test_balance_at_the_start_of_the_year(client, checking, add_txn):
    add_txn(checking, -1_000, date="2026-01-05")  # this year's spending
    result = client.post(url(checking), json={"date": "2025-12-31", "balance_cents": 50_000})
    assert result.json()["adjustment_cents"] == 50_000
    # Everything since then follows from the transactions.
    assert balance(client, checking) == 49_000


def test_setting_it_again_only_adds_whats_left(client, checking):
    client.post(url(checking), json={"date": "2026-01-01", "balance": "100.00"})
    again = client.post(url(checking), json={"date": "2026-01-01", "balance": "100.00"}).json()
    assert (again["adjustment_cents"], again["transaction_id"]) == (0, None)
    third = client.post(url(checking), json={"date": "2026-01-01", "balance": "90.00"}).json()
    assert third["adjustment_cents"] == -1_000
    assert balance(client, checking) == 9_000


def test_a_card_balance_owed_is_negative(client, make_account):
    card = make_account(name="Fake Card", kind="credit_card")["id"]
    client.post(url(card), json={"date": "2026-01-01", "balance": "-250.00"})
    assert balance(client, card) == -25_000


def test_adjustments_are_not_income_or_spending(client, checking):
    client.post(url(checking), json={"date": "2026-01-15", "balance": "500.00"})
    summary = client.get("/api/local/summary/monthly", params={"month": "2026-01"}).json()
    assert summary["income_cents"] == 0 and summary["spending_cents"] == 0


def test_bad_input(client, checking):
    future = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    assert client.post(url(checking), json={"date": future, "balance": "1"}).status_code == 422
    assert client.post(url(checking), json={"date": "2026-01-01"}).status_code == 422
    both = {"date": "2026-01-01", "balance": "1", "balance_cents": 100}
    assert client.post(url(checking), json=both).status_code == 422
    assert client.post(url(999), json={"date": "2026-01-01", "balance": "1"}).status_code == 404
