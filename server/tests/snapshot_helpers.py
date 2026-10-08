"""Helpers for the sync snapshot tests: seed rows into the Home Base and fetch a snapshot."""

import datetime as dt
import re

from fake_phone import NOW, SNAPSHOT, Phone
from sqlalchemy.orm import Session

from app.models import Transaction, TransactionSource

TODAY = dt.datetime.fromtimestamp(NOW).date()  # 2026-09-21 in most time zones


def days_ago(n: int) -> dt.date:
    return TODAY - dt.timedelta(days=n)


def snapshot(phone: Phone) -> dict:
    return phone.ok(SNAPSHOT)


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


# The shape the phone expects, checked key by key.
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
