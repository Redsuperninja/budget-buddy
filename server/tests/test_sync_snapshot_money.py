"""POST /api/sync/snapshot: income, accounts and tax (sync contract section 5). Fake data only."""

import datetime as dt
import json

from snapshot_helpers import TODAY, add, check_shape, days_ago, snapshot, txn

from app.models import (
    Deduction,
    DeductionKind,
    Donation,
    DonationKind,
    Paycheck,
    TransactionKind,
)

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
