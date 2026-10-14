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
