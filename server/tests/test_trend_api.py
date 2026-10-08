"""Month-by-month totals for the charts. Fake data only."""

import pytest
from test_categories_summary_api import cid

from app.services.trend import months_ending

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
