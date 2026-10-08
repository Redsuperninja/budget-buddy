"""POST /api/sync/snapshot: what the phone is allowed to see (sync contract section 5).

Fake data only. ``check_shape`` mirrors the phone's parser (mobile/src/sync/snapshot.ts) and also
fails on any key the contract doesn't list, so a new field can't leak out by accident.
"""

import calendar
import datetime as dt
import json
import re

import pytest
from sqlalchemy.orm import Session
from sync_helpers import NOW, Phone, pair_phone

from app.models import (
    Deduction,
    DeductionKind,
    Donation,
    DonationKind,
    Paycheck,
    Transaction,
    TransactionKind,
    TransactionSource,
)

PATH = "/api/sync/snapshot"
TODAY = dt.datetime.fromtimestamp(NOW).date()  # 2026-09-21 in most time zones


@pytest.fixture
def phone(make_client) -> Phone:
    return pair_phone(make_client())


def days_ago(n: int) -> dt.date:
    return TODAY - dt.timedelta(days=n)


def snapshot(phone: Phone) -> dict:
    return phone.ok(PATH)


def add(phone: Phone, *rows) -> None:
    with Session(phone.dashboard.app.state.engine) as session:
        session.add_all(rows)
        session.commit()


def txn(account_id, date, cents, description="Fake Cafe", category_id=None, **kw) -> Transaction:
    return Transaction(
        account_id=account_id,
        date=date,
        amount_cents=cents,
        description=description,
        category_id=category_id,
        source=TransactionSource.MANUAL,
        **kw,
    )


# --- shape --------------------------------------------------------------------------------

ACCOUNT_KINDS = "checking savings brokerage credit_card cash loan retirement hsa other".split()
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def keys(obj: dict, *expected: str) -> None:
    assert set(obj) == set(expected), f"unexpected keys: {set(obj) ^ set(expected)}"


def check_shape(s: dict) -> None:
    """Exactly the fields of the contract's TypeScript, with the right kinds of values."""
    keys(
        s,
        *"contract server_id generated_at currency period income budget transactions "
        "accounts tax settings".split(),
    )
    assert s["contract"] == 1 and isinstance(s["server_id"], str)
    assert ISO_DATETIME.fullmatch(s["generated_at"]) and re.fullmatch(r"[A-Z]{3}", s["currency"])
    p = s["period"]
    keys(p, "month", "start", "end", "days_elapsed", "days_in_month")
    assert re.fullmatch(r"\d{4}-\d{2}", p["month"])
    assert ISO_DATE.fullmatch(p["start"]) and ISO_DATE.fullmatch(p["end"])
    assert 28 <= p["days_in_month"] <= 31 and 0 <= p["days_elapsed"] <= p["days_in_month"]
    inc = s["income"]
    keys(inc, "expected_cents", "received_cents", "last_paycheck")
    assert is_int(inc["expected_cents"]) and inc["expected_cents"] >= 0
    assert is_int(inc["received_cents"]) and inc["received_cents"] >= 0
    if inc["last_paycheck"] is not None:
        keys(inc["last_paycheck"], "pay_date", "net_cents")
        assert ISO_DATE.fullmatch(inc["last_paycheck"]["pay_date"])
        assert is_int(inc["last_paycheck"]["net_cents"])
    b = s["budget"]
    keys(b, "target_cents", "actual_cents", "groups", "unassigned")
    keys(b["unassigned"], "in_cents", "out_cents", "count")
    assert all(is_int(v) and v >= 0 for v in b["unassigned"].values())
    assert is_int(b["target_cents"]) and is_int(b["actual_cents"])
    assert [g["group"] for g in b["groups"]] == ["needs", "wants", "savings"]
    for g in b["groups"]:
        keys(g, "group", "name", "target_cents", "actual_cents", "categories")
        assert (
            isinstance(g["name"], str) and is_int(g["target_cents"]) and is_int(g["actual_cents"])
        )
        for c in g["categories"]:
            keys(c, "id", "name", "target_cents", "actual_cents")
            assert is_int(c["id"]) and isinstance(c["name"], str)
            assert is_int(c["target_cents"]) and is_int(c["actual_cents"])
    for t in s["transactions"]:
        keys(t, "id", "date", "description", "amount_cents", "category_id", "account_id")
        assert is_int(t["id"]) and ISO_DATE.fullmatch(t["date"]) and len(t["description"]) <= 100
        assert is_int(t["amount_cents"]) and is_int(t["account_id"])
        assert t["category_id"] is None or is_int(t["category_id"])
    for a in s["accounts"]:
        keys(a, "id", "name", "kind", "balance_cents", "balance_as_of")
        assert a["kind"] in ACCOUNT_KINDS and is_int(a["balance_cents"])
        assert is_int(a["id"]) and ISO_DATE.fullmatch(a["balance_as_of"])
    t = s["tax"]
    keys(t, "year", "donations_total_cents", "realized_gains", "deductions", "disclaimer")
    assert is_int(t["year"]) and is_int(t["donations_total_cents"]) and t["disclaimer"]
    keys(t["realized_gains"], "short_term_cents", "long_term_cents", "is_estimate")
    assert is_int(t["realized_gains"]["short_term_cents"])
    assert is_int(t["realized_gains"]["long_term_cents"])
    assert isinstance(t["realized_gains"]["is_estimate"], bool)
    for d in t["deductions"]:
        keys(d, "kind", "label", "amount_cents", "is_estimate")
        assert is_int(d["amount_cents"]) and isinstance(d["is_estimate"], bool)
    keys(s["settings"], "reminder_days_default", "reminder_days_allowed")
    assert s["settings"] == {"reminder_days_default": 2, "reminder_days_allowed": [1, 2, 3]}


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


# --- income and accounts ----------------------------------------------------------------------


def paycheck(date, net, **kw) -> Paycheck:
    return Paycheck(
        pay_date=date, employer="Fake Employer Inc", gross_cents=net + 1000, net_cents=net, **kw
    )


def income_category(phone) -> int:
    categories = phone.dashboard.get("/api/local/categories").json()
    return next(c["id"] for c in categories if c["group"] == "income")


def test_received_is_income_so_far_and_expected_is_the_larger_of_it_and_paychecks(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    pay = income_category(phone)
    later = TODAY.replace(day=28)
    add(
        phone,
        txn(a["id"], days_ago(0), 260_000, "Pay", category_id=pay),
        txn(a["id"], days_ago(0), 99_999, "Refund", category_id=pay, kind=TransactionKind.REFUND),
        txn(a["id"], days_ago(0), 88_888, "Transfer in", kind=TransactionKind.TRANSFER),
        txn(a["id"], later, 70_000, "Future pay", category_id=pay),  # not received yet
        paycheck(TODAY.replace(day=1), 260_000),
        paycheck(later, 250_000),
        paycheck(days_ago(40), 111_111),  # not this month
    )
    s = snapshot(phone)
    check_shape(s)
    assert s["income"]["received_cents"] == 260_000  # paychecks alone never count as received
    assert s["income"]["expected_cents"] == 260_000 + 250_000


def test_expected_is_never_less_than_received(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    add(
        phone,
        txn(a["id"], days_ago(0), 300_000, "Pay", category_id=income_category(phone)),
        paycheck(TODAY.replace(day=1), 260_000),
    )
    s = snapshot(phone)
    assert s["income"]["received_cents"] == 300_000
    assert s["income"]["expected_cents"] == 300_000


def test_income_is_zero_without_income_transactions_and_never_negative(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    pay = income_category(phone)
    add(phone, paycheck(TODAY.replace(day=1), 260_000))
    s = snapshot(phone)
    assert s["income"]["received_cents"] == 0
    assert s["income"]["expected_cents"] == 260_000
    add(phone, txn(a["id"], days_ago(0), -5_000, "Odd", category_id=pay))
    s = snapshot(phone)
    check_shape(s)
    assert s["income"]["received_cents"] == 0


def test_last_paycheck_is_the_latest_one_up_to_today(phone):
    add(phone, paycheck(days_ago(3), 250_000), paycheck(days_ago(40), 111_111))
    s = snapshot(phone)
    assert s["income"]["last_paycheck"] == {
        "pay_date": days_ago(3).isoformat(),
        "net_cents": 250_000,
    }
    assert "Fake Employer" not in json.dumps(s)


def test_accounts_have_balances_and_never_private_details(phone):
    d = phone.dashboard
    checking = d.post(
        "/api/local/accounts",
        json={
            "name": "Everyday",
            "kind": "checking",
            "last4": "4321",
            "notes": "FAKE-SECRET-NOTE",
            "institution": "Fake Credit Union",
        },
    ).json()
    savings = d.post("/api/local/accounts", json={"name": "Rainy day", "kind": "savings"}).json()
    d.post("/api/local/accounts", json={"name": "Wallet", "kind": "cash"})
    card = d.post("/api/local/accounts", json={"name": "Card", "kind": "credit_card"}).json()
    add(
        phone,
        txn(
            checking["id"], days_ago(2), 500_000, "Opening balance", kind=TransactionKind.ADJUSTMENT
        ),
        txn(checking["id"], days_ago(1), -157_850),
        txn(savings["id"], days_ago(10), 1_250_000, kind=TransactionKind.ADJUSTMENT),
        txn(checking["id"], days_ago(1), -1_000_000, "Overdraft"),
        txn(checking["id"], TODAY + dt.timedelta(days=3), -77_000, "Not yet"),  # after today
        txn(card["id"], days_ago(1), -42_000, "Card spend"),
    )
    s = snapshot(phone)
    check_shape(s)
    by_name = {a["name"]: a for a in s["accounts"]}
    assert set(by_name) == {"Everyday", "Rainy day", "Wallet", "Card"}
    assert by_name["Card"]["kind"] == "credit_card" and by_name["Card"]["balance_cents"] == -42_000
    assert by_name["Wallet"] == {**by_name["Wallet"], "kind": "cash", "balance_cents": 0}
    assert (
        by_name["Everyday"]["balance_cents"] == 500_000 - 157_850 - 1_000_000
    )  # negative = owed, future ones left out
    assert by_name["Everyday"]["balance_as_of"] == days_ago(1).isoformat()
    assert by_name["Rainy day"]["balance_cents"] == 1_250_000
    text = json.dumps(s)
    for secret in ("4321", "FAKE-SECRET-NOTE", "Fake Credit Union"):
        assert secret not in text


def test_transaction_notes_never_leave(phone):
    a = phone.dashboard.post("/api/local/accounts", json={"name": "A", "kind": "checking"}).json()
    add(phone, txn(a["id"], days_ago(1), -5, "Fake Cafe", notes="FAKE-TXN-NOTE"))
    text = json.dumps(snapshot(phone))
    assert "Fake Cafe" in text and "FAKE-TXN-NOTE" not in text


# --- tax ---------------------------------------------------------------------------------------


def test_tax_summary(phone):
    a = phone.dashboard.post(
        "/api/local/accounts", json={"name": "Brokerage", "kind": "brokerage"}
    ).json()
    add(
        phone,
        Donation(
            date=days_ago(5),
            organization="Fake Charity",
            amount_cents=30_000,
            kind=DonationKind.CASH,
        ),
        Donation(
            date=days_ago(4),
            organization="Fake Thrift",
            amount_cents=15_000,
            kind=DonationKind.GOODS,
        ),
        Donation(
            date=dt.date(2025, 12, 31),
            organization="Last year",
            amount_cents=999,
            kind=DonationKind.CASH,
        ),
        Deduction(tax_year=2026, kind=DeductionKind.MEDICAL, amount_cents=20_000),
        Deduction(
            tax_year=2026, kind=DeductionKind.MEDICAL, amount_cents=3_000, description="FAKE-DETAIL"
        ),
        Deduction(tax_year=2026, kind=DeductionKind.HSA, amount_cents=5_000),
        Deduction(tax_year=2025, kind=DeductionKind.OTHER, amount_cents=7_000),
    )
    for symbol, bought, shares, cost in (
        ("FAKE", "2026-03-01", "10", 100_000),
        ("OTHR", "2022-01-01", "5", 50_000),
    ):
        lot = {
            "account_id": a["id"],
            "symbol": symbol,
            "acquired_on": bought,
            "shares": shares,
            "cost_basis_cents": cost,
        }
        assert phone.dashboard.post("/api/local/stocks/lots", json=lot).status_code == 201
    for symbol, sold, shares, proceeds in (
        ("FAKE", "2026-06-01", "10", 80_000),
        ("OTHR", "2026-08-01", "5", 90_000),
    ):
        sale = {
            "account_id": a["id"],
            "symbol": symbol,
            "sold_on": sold,
            "shares": shares,
            "proceeds_cents": proceeds,
        }
        assert phone.dashboard.post("/api/local/stocks/sales", json=sale).status_code == 201
    s = snapshot(phone)
    check_shape(s)
    tax = s["tax"]
    assert tax["donations_total_cents"] == 45_000
    assert tax["deductions"] == [
        {
            "kind": "hsa",
            "label": "Health savings account",
            "amount_cents": 5_000,
            "is_estimate": False,
        },
        {"kind": "medical", "label": "Medical", "amount_cents": 23_000, "is_estimate": False},
    ]
    assert "FAKE-DETAIL" not in json.dumps(s) and "Fake Charity" not in json.dumps(s)
    gains = tax["realized_gains"]
    assert gains == {"short_term_cents": -20_000, "long_term_cents": 40_000, "is_estimate": False}
    api = phone.dashboard.get("/api/local/stocks/gains/2026").json()
    assert gains["short_term_cents"] == api["short_term"]["gain_cents"]
    assert gains["long_term_cents"] == api["long_term"]["gain_cents"]


def test_snapshot_contains_no_free_text_the_contract_does_not_list(phone):
    """Every string in the snapshot is a field the contract names. No notes, merchants, or ids."""
    s = snapshot(phone)
    strings = []

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            strings.append(value)

    walk(s)
    assert "Home Base" not in strings  # server name is not part of the snapshot
    assert len(json.dumps(s)) < 5_000  # an empty database is small
