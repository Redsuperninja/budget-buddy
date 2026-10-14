"""Month-by-month totals for the charts. Fake data only."""

import datetime as dt

import pytest
from test_categories_summary_api import cid

from app.services.budget.trend import months_ending

TREND = "/api/local/summary/trend"


def test_months_ending_crosses_years():
    assert months_ending(2026, 2, 3) == [(2025, 12), (2026, 1), (2026, 2)]
    assert months_ending(2026, 2, 1) == [(2026, 2)]


def test_trend_matches_each_monthly_summary(client, make_account, add_txn):
    checking = make_account()["id"]
    add_txn(checking, 300_000, date="2026-01-05", category_id=cid(client, "Paycheck"))
    add_txn(checking, -50_000, date="2026-01-06", category_id=cid(client, "Groceries"))
    add_txn(checking, -20_000, date="2026-03-02", category_id=cid(client, "Emergency Fund"))
    add_txn(checking, 1_000, date="2026-03-03", category_id=cid(client, "Shopping"), kind="refund")

    trend = client.get(TREND, params={"end": "2026-03", "months": 3}).json()["months"]
    assert [m["month"] for m in trend] == ["2026-01", "2026-02", "2026-03"]
    assert trend[0] == {
        "month": "2026-01",
        "income_cents": 300_000,
        "spending_cents": 50_000,
        "saved_cents": 0,
        "net_worth_cents": 250_000,
    }
    assert trend[1]["spending_cents"] == 0
    assert (trend[2]["spending_cents"], trend[2]["saved_cents"]) == (-1_000, 20_000)
    for month in trend:
        summary = client.get("/api/local/summary/monthly", params={"month": month["month"]}).json()
        assert month["income_cents"] == summary["income_cents"]


def test_twelve_months_by_default(client):
    assert len(client.get(TREND, params={"end": "2026-10"}).json()["months"]) == 12


@pytest.mark.parametrize(
    "params",
    [
        {"end": "2026-13"},
        {"end": ""},
        {"end": "2026-01", "months": 0},
        {"end": "2026-01", "months": 25},
    ],
)
def test_bad_requests(client, params):
    assert client.get(TREND, params=params).status_code == 422


def test_net_worth_at_each_months_end(client, make_account, add_txn):
    checking = make_account()["id"]
    card = make_account(name="Fake Card", kind="credit_card")["id"]
    add_txn(checking, 100_000, date="2026-01-31", kind="adjustment")  # opening balance counts
    add_txn(card, -30_000, date="2026-02-10")
    add_txn(checking, -5_000, date="2026-04-01")  # after the last month
    trend = client.get(TREND, params={"end": "2026-03", "months": 3}).json()["months"]
    assert [m["net_worth_cents"] for m in trend] == [100_000, 70_000, 70_000]


def test_this_months_net_worth_stops_at_today(client, make_account, add_txn):
    checking = make_account()["id"]
    today = dt.date.today()
    add_txn(checking, 100_000, date=today.isoformat(), kind="adjustment")
    later = today + dt.timedelta(days=1)
    add_txn(checking, -40_000, date=later.isoformat(), description="Fake rent")
    month = f"{today.year}-{today.month:02d}"
    [this] = client.get(TREND, params={"end": month, "months": 1}).json()["months"]
    assert this["net_worth_cents"] == 100_000  # like Home's balances: the rent isn't paid yet
