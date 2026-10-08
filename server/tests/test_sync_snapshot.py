"""POST /api/sync/snapshot: what the phone is allowed to see (sync contract section 5).

Fake data only. ``check_shape`` mirrors the phone's parser (mobile/src/sync/snapshot.ts) and also
fails on any key the contract doesn't list, so a new field can't leak out by accident.
"""

import calendar
import datetime as dt

from snapshot_helpers import TODAY, add, check_shape, days_ago, snapshot, txn

from app.models import (
    TransactionKind,
)


def test_empty_database_still_gives_a_valid_snapshot(phone):
    s = snapshot(phone)
    check_shape(s)
    assert s["transactions"] == [] and s["accounts"] == []
    assert s["income"] == {"expected_cents": 0, "received_cents": 0, "last_paycheck": None}
    assert all(g["actual_cents"] == 0 for g in s["budget"]["groups"])
    assert s["tax"]["donations_total_cents"] == 0 and s["tax"]["deductions"] == []
    assert s["tax"]["realized_gains"] == {
        "short_term_cents": 0,
        "long_term_cents": 0,
        "is_estimate": False,
    }


def test_period_and_timestamps(phone):
    s = snapshot(phone)
    last = calendar.monthrange(TODAY.year, TODAY.month)[1]
    assert s["period"] == {
        "month": TODAY.strftime("%Y-%m"),
        "start": TODAY.replace(day=1).isoformat(),
        "end": TODAY.replace(day=last).isoformat(),
        "days_elapsed": TODAY.day,
        "days_in_month": last,
    }
    assert s["generated_at"] == "2026-09-21T14:13:20Z"
    assert s["currency"] == "USD" and s["tax"]["year"] == 2026


# --- budget and transactions ------------------------------------------------------------------


def test_budget_breakdown_for_the_month(phone):
    d = phone.dashboard
    categories = {c["name"]: c for c in d.get("/api/local/categories").json()}
    groceries = next(c for c in categories.values() if c["group"] == "needs")
    eating = next(c for c in categories.values() if c["group"] == "wants")
    assert (
        d.patch(
            f"/api/local/categories/{groceries['id']}", json={"budget_cents": 60_000}
        ).status_code
        == 200
    )
    account = d.post("/api/local/accounts", json={"name": "Everyday", "kind": "checking"}).json()
    add(
        phone,
        txn(account["id"], days_ago(2), -8_000, category_id=groceries["id"]),
        txn(account["id"], days_ago(1), -3_245, category_id=eating["id"]),
        txn(
            account["id"], days_ago(1), 1_000, category_id=eating["id"], kind=TransactionKind.REFUND
        ),
        txn(account["id"], days_ago(40), -9_999, category_id=groceries["id"]),  # last month
    )
    s = snapshot(phone)
    check_shape(s)
    needs, wants, savings = s["budget"]["groups"]
    assert needs["actual_cents"] == 8_000 and needs["target_cents"] >= 60_000
    mine = next(c for c in needs["categories"] if c["id"] == groceries["id"])
    assert mine == {
        "id": groceries["id"],
        "name": groceries["name"],
        "target_cents": 60_000,
        "actual_cents": 8_000,
    }
    assert wants["actual_cents"] == 2_245  # the refund is netted off
    assert savings["actual_cents"] == 0 and (needs["name"], wants["name"]) == ("Needs", "Wants")
    assert s["budget"]["target_cents"] == sum(g["target_cents"] for g in s["budget"]["groups"])
    assert s["budget"]["actual_cents"] == 8_000 + 2_245


def test_transactions_are_the_last_60_days_newest_first(phone):
    account = phone.dashboard.post(
        "/api/local/accounts", json={"name": "Everyday", "kind": "checking"}
    ).json()
    a = account["id"]
    add(
        phone,
        txn(a, days_ago(59), -100, "Oldest in range"),
        txn(a, days_ago(60), -200, "Too old"),
        txn(a, TODAY, -300, "Today"),
        txn(a, TODAY + dt.timedelta(days=1), -400, "Tomorrow"),
        txn(a, days_ago(5), 500, "Refund", kind=TransactionKind.REFUND),
        txn(a, TODAY, -600, "x" * 300),
    )
    s = snapshot(phone)
    check_shape(s)
    descriptions = [t["description"] for t in s["transactions"]]
    assert descriptions == ["x" * 100, "Today", "Refund", "Oldest in range"]
    assert [t["amount_cents"] for t in s["transactions"]] == [-600, -300, 500, -100]
    assert s["transactions"][0]["date"] == TODAY.isoformat()


def test_at_most_500_transactions(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    add(phone, *[txn(a["id"], days_ago(i % 30), -1, f"n{i}") for i in range(520)])
    s = snapshot(phone)
    assert len(s["transactions"]) == 500
    dates = [t["date"] for t in s["transactions"]]
    assert dates == sorted(dates, reverse=True)


def test_unassigned_money_is_reported_separately(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    add(
        phone,
        txn(a["id"], days_ago(1), -4_000, "No category"),
        txn(a["id"], days_ago(1), 1_500, "Refund", kind=TransactionKind.REFUND),
    )
    s = snapshot(phone)
    check_shape(s)
    assert s["budget"]["unassigned"] == {"in_cents": 1_500, "out_cents": 4_000, "count": 2}
    assert all(g["actual_cents"] == 0 for g in s["budget"]["groups"])
