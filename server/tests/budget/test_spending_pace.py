"""Spending pace for the Home chart: spent by each day of the month, against the budget. Fake data
only."""

import datetime as dt

from test_categories_summary_api import cid

from app.services.budget import spending_pace

PACE = "/api/local/summary/pace"


def test_each_day_adds_up_like_the_summary(client, make_account, add_txn):
    checking = make_account()["id"]
    add_txn(checking, -5_000, date="2026-02-02", category_id=cid(client, "Groceries"))
    add_txn(checking, -2_000, date="2026-02-04", category_id=cid(client, "Shopping"))
    add_txn(checking, 500, date="2026-02-04", category_id=cid(client, "Shopping"), kind="refund")
    pay = cid(client, "Paycheck")
    add_txn(checking, 300_000, date="2026-02-03", category_id=pay)  # income, not spending
    pace = client.get(PACE, params={"month": "2026-02"}).json()
    assert (pace["month"], pace["days_in_month"]) == ("2026-02", 28)
    spent = [d["spent_cents"] for d in pace["days"]]
    assert spent[:5] == [0, 5_000, 5_000, 6_500, 6_500]
    assert len(spent) == 28 and spent[-1] == 6_500
    summary = client.get("/api/local/summary/monthly", params={"month": "2026-02"}).json()
    assert pace["budget_cents"] == summary["spending_budget_cents"]


def test_days_stop_at_today(client, monkeypatch):
    monkeypatch.setattr(spending_pace, "_today", lambda: dt.date(2026, 10, 9))
    days = client.get(PACE, params={"month": "2026-10"}).json()["days"]
    assert (len(days), days[-1]["date"]) == (9, "2026-10-09")
    assert client.get(PACE, params={"month": "2026-10"}).json()["complete"] is False
    assert client.get(PACE, params={"month": "2026-09"}).json()["complete"] is True
    assert client.get(PACE, params={"month": "2026-11"}).json()["days"] == []


def test_a_bad_month_is_refused(client):
    assert client.get(PACE, params={"month": "soon"}).status_code == 422


def pinned_ledger(client, make_account, add_txn):
    """Jan: income, transfers and saving only. Feb: spending, a refund, a reimbursement, and things
    that aren't spending. Mar: spent on the 1st, rent and pay dated later in the month."""
    checking = make_account()["id"]
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    food, pay, rent = (
        cid(client, "Groceries"),
        cid(client, "Paycheck"),
        cid(client, "Rent/Mortgage"),
    )
    client.patch(f"/api/local/categories/{food}", json={"budget_percent_bp": 1_000})
    client.patch(f"/api/local/categories/{rent}", json={"budget_cents": 150_000})
    add_txn(checking, 250_000, date="2026-01-02", category_id=pay)
    link(
        client,
        add_txn(checking, -50_000, date="2026-01-05"),
        add_txn(savings, 50_000, date="2026-01-05"),
    )
    add_txn(checking, -7_500, date="2026-01-06", category_id=cid(client, "Transfer"))
    add_txn(checking, -10_000, date="2026-01-07", category_id=cid(client, "Emergency Fund"))
    add_txn(checking, -4_321, date="2026-02-01", category_id=food)
    add_txn(checking, -1_250, date="2026-02-01", category_id=cid(client, "Dining Out"))
    add_txn(checking, 800, date="2026-02-03", category_id=food, kind="refund")
    add_txn(checking, -999, date="2026-02-05")  # uncategorized: unassigned, not spending
    add_txn(checking, 300, date="2026-02-06", category_id=pay, kind="refund")  # unassigned
    add_txn(ira, 130, date="2026-02-08", description="FAKECO CASH DIV")  # kept inside the IRA
    add_txn(ira, -130, date="2026-02-08", description="FAKE DEPOSIT SWEEP", category_id=food)
    add_txn(checking, 1_000, date="2026-02-10", category_id=cid(client, "Shopping"))  # paid back
    out = add_txn(checking, -7_000, date="2026-02-12", category_id=food)  # a transfer: not spent
    link(client, out, add_txn(savings, 7_000, date="2026-02-12"))
    add_txn(checking, 300_000, date="2026-02-15", category_id=pay)
    add_txn(checking, -150_000, date="2026-02-28", category_id=rent)
    add_txn(checking, -2_000, date="2026-03-01", category_id=food)
    add_txn(checking, -150_000, date="2026-03-15", category_id=rent)
    add_txn(checking, 200_000, date="2026-03-20", category_id=pay)


def link(client, out, into):
    url = f"/api/local/transactions/{out['id']}/transfer"
    assert client.post(url, json={"other_id": into["id"]}).is_success


def runs(steps: dict[int, int], days: int) -> list[int]:
    """Spent by each day, from the days it changes on."""
    out, now = [], 0
    for day in range(1, days + 1):
        now = steps.get(day, now)
        out.append(now)
    return out


def pace_on(client, monkeypatch, today, month):
    monkeypatch.setattr(spending_pace, "_today", lambda: today)
    pace = client.get(PACE, params={"month": month}).json()
    return pace, [d["spent_cents"] for d in pace["days"]]


def test_pinned_month_with_no_spending(client, make_account, add_txn, monkeypatch):
    pinned_ledger(client, make_account, add_txn)
    pace, spent = pace_on(client, monkeypatch, dt.date(2026, 3, 1), "2026-01")
    assert spent == [0] * 31 and pace["days"][-1]["date"] == "2026-01-31"
    assert (pace["budget_cents"], pace["complete"]) == (25_000 + 150_000, True)


def test_pinned_today_is_the_last_day(client, make_account, add_txn, monkeypatch):
    pinned_ledger(client, make_account, add_txn)
    pace, spent = pace_on(client, monkeypatch, dt.date(2026, 2, 28), "2026-02")
    assert spent == runs({1: 5_571, 3: 4_771, 10: 3_771, 28: 153_771}, 28)
    assert (pace["budget_cents"], pace["complete"], pace["days_in_month"]) == (180_000, False, 28)


def test_pinned_today_is_the_first(client, make_account, add_txn, monkeypatch):
    """Rent and pay dated later this month: not spent yet, but the pay already sets the budget."""
    pinned_ledger(client, make_account, add_txn)
    pace, spent = pace_on(client, monkeypatch, dt.date(2026, 3, 1), "2026-03")
    assert (spent, pace["days"][0]["date"]) == ([2_000], "2026-03-01")
    assert (pace["budget_cents"], pace["complete"]) == (20_000 + 150_000, False)
