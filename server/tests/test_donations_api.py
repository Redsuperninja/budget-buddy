"""Donations API and the paperwork rules for charitable gifts. Fake data only.

Worked examples use the 2026 tax data file: written acknowledgment at $250.00 or more, Form 8283
when the year's goods total is more than $500.00, appraisal for goods more than $5,000.00.
"""

import datetime as dt

import pytest

from app import tax_data
from app.models import DonationKind
from app.schemas import donations as donation_schemas
from app.services.donations import donation_proof, year_proof

URL = "/api/local/donations"
RULES_2025 = tax_data.load_tax_year(2025).charitable  # same thresholds, no non-itemizer rule
RULES_2026 = tax_data.load_tax_year(2026).charitable
FROZEN_TODAY = dt.date(2030, 1, 1)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    """Freeze the Home Base's date so example gifts in 2026-2028 are never "in the future"."""
    monkeypatch.setattr(donation_schemas, "_today", lambda: FROZEN_TODAY)


@pytest.fixture
def add_donation(client):
    def add(amount_cents: int, kind: str = "cash", date: str = "2026-03-10", **overrides) -> dict:
        body = {"date": date, "organization": "Fake Food Bank", "kind": kind}
        body |= {"amount_cents": amount_cents, **overrides}
        response = client.post(URL, json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return add


def make_receipt(client) -> int:
    from app.db import SessionLocal
    from app.models import Receipt

    with SessionLocal(bind=client.app.state.engine) as session:
        receipt = Receipt(date=dt.date(2026, 3, 10), merchant="Fake Charity", total_cents=2_500)
        session.add(receipt)
        session.commit()
        return receipt.id


def codes(items) -> list[str]:
    return [item.code if hasattr(item, "code") else item["code"] for item in items]


# --- CRUD ------------------------------------------------------------------------------------


def test_donation_crud(client, add_donation):
    receipt_id = make_receipt(client)
    created = add_donation(2_500, receipt_id=receipt_id, notes="fake note")
    assert created["tax_year"] == 2026
    assert (created["kind"], created["amount_cents"]) == ("cash", 2_500)
    assert created["receipt_id"] == receipt_id
    donation_id = created["id"]

    assert client.get(f"{URL}/{donation_id}").json()["notes"] == "fake note"

    response = client.patch(
        f"{URL}/{donation_id}",
        json={"amount": "300.00", "kind": "goods", "date": "2025-12-31", "receipt_id": None},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert (updated["amount_cents"], updated["kind"]) == (30_000, "goods")
    assert (updated["tax_year"], updated["receipt_id"]) == (2025, None)
    assert updated["organization"] == "Fake Food Bank"

    assert client.delete(f"{URL}/{donation_id}").status_code == 204
    assert client.get(f"{URL}/{donation_id}").status_code == 404
    assert client.get(f"{URL}/{donation_id}").json()["error"]["code"] == "not_found"


def test_amount_in_dollars(client):
    body = {"date": "2026-01-01", "organization": "Fake Shelter", "kind": "cash", "amount": "250"}
    response = client.post(URL, json=body)
    assert response.status_code == 201, response.text
    assert response.json()["amount_cents"] == 25_000


@pytest.mark.parametrize(
    "body",
    [
        {"amount_cents": 0},
        {"amount_cents": -1},
        {"amount": "0.00"},
        {"amount": "-5.00"},
        {"amount_cents": 25.0},  # floats are never money
        {"amount": "2.505"},  # fraction of a cent
        {"amount_cents": 100, "amount": "1.00"},
        {},  # no amount
        {"amount_cents": 100, "kind": "stock"},
        {"amount_cents": 100, "organization": "   "},
        {"amount_cents": 100, "date": "2026-02-30"},
        {"amount_cents": 100, "surprise": 1},
    ],
)
def test_donation_validation_errors(client, body):
    full = {"date": "2026-01-15", "organization": "Fake Charity", "kind": "cash", **body}
    response = client.post(URL, json=full)
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"]


def test_negative_amount_explains_refunds(client):
    body = {"date": "2026-01-15", "organization": "Fake", "kind": "cash", "amount_cents": -500}
    message = client.post(URL, json=body).json()["error"]["message"]
    assert "more than zero" in message and "refunded" in message


@pytest.mark.parametrize(
    "patch",
    [{"amount_cents": 0}, {"amount": "-1.00"}, {"organization": None}, {"kind": None}],
)
def test_bad_patch_is_rejected(client, add_donation, patch):
    donation_id = add_donation(1_000)["id"]
    assert client.patch(f"{URL}/{donation_id}", json=patch).status_code == 422
    assert client.get(f"{URL}/{donation_id}").json()["amount_cents"] == 1_000


def test_unknown_receipt_is_not_found(client, add_donation):
    body = {"date": "2026-01-15", "organization": "Fake", "kind": "cash", "amount_cents": 100}
    response = client.post(URL, json={**body, "receipt_id": 999})
    assert response.status_code == 404
    assert "receipt" in response.json()["error"]["message"]
    donation_id = add_donation(100)["id"]
    assert client.patch(f"{URL}/{donation_id}", json={"receipt_id": 999}).status_code == 404


def test_list_filters_by_tax_year_and_kind(client, add_donation):
    add_donation(100, date="2025-12-31")
    first = add_donation(200, date="2026-01-01")
    last = add_donation(300, kind="goods", date="2026-12-31")
    add_donation(400, date="2027-01-01")

    page = client.get(URL, params={"tax_year": 2026}).json()
    assert page["total"] == 2
    assert [d["id"] for d in page["items"]] == [last["id"], first["id"]]  # newest first
    goods = client.get(URL, params={"tax_year": 2026, "kind": "goods"}).json()
    assert [d["id"] for d in goods["items"]] == [last["id"]]
    assert client.get(URL, params={"limit": 1, "offset": 1}).json()["total"] == 4


def test_leap_day_counts_in_its_own_year(client, add_donation):
    assert add_donation(100, date="2028-02-29")["tax_year"] == 2028


@pytest.mark.parametrize(
    ("days_ahead", "ok"),
    [(0, True), (1, True), (2, False)],  # today, phone a time zone ahead, the day after that
)
def test_future_dates_are_rejected(client, days_ahead, ok):
    date = (FROZEN_TODAY + dt.timedelta(days=days_ahead)).isoformat()
    body = {"date": date, "organization": "Fake", "kind": "cash", "amount_cents": 100}
    response = client.post(URL, json=body)
    assert response.status_code == (201 if ok else 422), response.text
    if not ok:
        assert "A pledge counts once you pay it." in response.json()["error"]["message"]


def test_patch_cannot_move_a_gift_into_the_future(client, add_donation):
    donation_id = add_donation(100)["id"]
    future = (FROZEN_TODAY + dt.timedelta(days=2)).isoformat()
    response = client.patch(f"{URL}/{donation_id}", json={"date": future})
    assert response.status_code == 422
    assert "the day you actually gave it" in response.json()["error"]["message"]
    assert client.get(f"{URL}/{donation_id}").json()["date"] == "2026-03-10"


# --- Paperwork rules (table-driven, from the 2026 data file) ----------------------------------


@pytest.mark.parametrize(
    ("kind", "amount_cents", "expected"),
    [
        # Cash: a bank record is enough below $250.00; $250.00 or more needs the charity's letter.
        (DonationKind.CASH, 1, ["bank_record_or_receipt"]),
        (DonationKind.CASH, 24_999, ["bank_record_or_receipt"]),
        (DonationKind.CASH, 25_000, ["written_acknowledgment"]),  # exactly $250.00
        (DonationKind.CASH, 25_001, ["written_acknowledgment"]),
        # Cash never needs an appraisal, however large.
        (DonationKind.CASH, 500_000, ["written_acknowledgment"]),
        (DonationKind.CASH, 500_001, ["written_acknowledgment"]),
        # Goods: receipt below $250.00, acknowledgment from $250.00, appraisal above $5,000.00.
        (DonationKind.GOODS, 24_999, ["charity_receipt"]),
        (DonationKind.GOODS, 25_000, ["written_acknowledgment", "value_note"]),  # exactly $250
        (DonationKind.GOODS, 50_000, ["written_acknowledgment", "value_note"]),  # exactly $500
        (DonationKind.GOODS, 500_000, ["written_acknowledgment", "value_note"]),  # exactly $5,000
        (
            DonationKind.GOODS,
            500_001,
            ["written_acknowledgment", "value_note", "qualified_appraisal"],
        ),
    ],
)
def test_donation_proof(kind, amount_cents, expected):
    assert codes(donation_proof(kind, amount_cents, RULES_2026)) == expected


@pytest.mark.parametrize(
    ("goods_amounts_cents", "expected"),
    [
        ([], []),
        ([49_999], []),
        ([50_000], []),  # exactly $500.00: Form 8283 is only for more than $500
        ([25_000, 25_000], []),  # two gifts totalling exactly $500.00
        ([50_001], ["form_8283"]),
        ([25_000, 25_001], ["form_8283"]),  # each under $500, together over
        # Similar-items check: total over $5,000 but no single gift over it.
        ([500_000], ["form_8283"]),  # exactly $5,000.00: no check
        ([250_000, 250_000], ["form_8283"]),  # two gifts totalling exactly $5,000.00
        ([250_000, 250_001], ["form_8283", "check_similar_items"]),
        ([500_001], ["form_8283"]),  # that one gift already gets its own appraisal flag
        ([500_001, 100], ["form_8283"]),
    ],
)
def test_year_proof(goods_amounts_cents, expected):
    assert codes(year_proof(goods_amounts_cents, RULES_2025)) == expected


def test_non_itemizer_note_follows_the_data_file():
    assert codes(year_proof([], RULES_2025)) == []  # no such rule in 2025
    (note,) = year_proof([], RULES_2026)
    assert note.code == "non_itemizer_cash_only"
    assert note.message == (
        "If you don't itemize, only cash gifts count, up to $1,000.00 "
        "($2,000.00 if married filing jointly)."
    )


def test_messages_use_the_data_file_amounts():
    (ack,) = donation_proof(DonationKind.CASH, 25_000, RULES_2026)
    assert "$250.00 or more" in ack.message
    assert "if so, about what it was worth" in ack.message
    goods = donation_proof(DonationKind.GOODS, 500_001, RULES_2026)
    assert goods[1].message.startswith("Also keep your own note of what the items were worth")
    assert "more than $5,000.00" in goods[2].message
    form, similar = year_proof([250_000, 250_001], RULES_2025)
    assert "more than $500.00, so if you itemize, you'll likely need" in form.message
    assert similar.message == (
        "Your gifts of goods this year add up to more than $5,000.00. If several were similar "
        "items (like clothing or furniture), add their values together. If those add up to more "
        "than $5,000.00, you'll likely need a qualified appraisal and Section B of Form 8283."
    )


def test_thresholds_come_from_the_tax_data_not_the_code(client, add_donation, monkeypatch):
    """Change the numbers in a (fake) data file and the flags and wording follow."""
    real = tax_data.load_tax_year(2026)
    fake_rules = real.charitable.model_copy(
        update={
            "written_acknowledgment_threshold_cents": 10_000,
            "form_8283_noncash_threshold_cents": 20_000,
            "qualified_appraisal_threshold_cents": 30_000,
        }
    )
    fake = real.model_copy(update={"charitable": fake_rules})
    monkeypatch.setattr(tax_data, "load_tax_year", lambda year: fake)

    add_donation(10_000)
    add_donation(30_001, kind="goods")
    body = client.get(f"{URL}/summary/2026").json()
    first, second = body["donations"]
    assert codes(first["proof_needed"]) == ["written_acknowledgment"]
    assert "$100.00 or more" in first["proof_needed"][0]["message"]
    assert codes(second["proof_needed"]) == [
        "written_acknowledgment",
        "value_note",
        "qualified_appraisal",
    ]
    assert codes(body["year_proof_needed"]) == ["form_8283", "non_itemizer_cash_only"]
    assert body["thresholds"]["written_acknowledgment_cents"] == 10_000


# --- Yearly summary ---------------------------------------------------------------------------


def test_summary_worked_example(client, add_donation):
    """Four 2026 gifts. Each goods gift is under $500, but together they're over, so Form 8283."""
    receipt_id = make_receipt(client)
    add_donation(10_000, date="2026-01-01")  # $100.00 cash
    add_donation(25_000, date="2026-06-15", receipt_id=receipt_id)  # $250.00 cash
    add_donation(20_000, kind="goods", date="2026-09-01")  # $200.00 of goods
    add_donation(30_001, kind="goods", date="2026-12-31")  # $300.01 of goods
    add_donation(99_999, date="2025-12-31")  # other years are left out
    add_donation(99_999, date="2027-01-01")

    response = client.get(f"{URL}/summary/2026")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_estimate"] is True
    assert "isn't tax advice" in body["disclaimer"]
    assert "not what you can deduct" in body["disclaimer"]
    assert body["donation_count"] == 4
    assert body["cash_total_cents"] == 35_000
    assert body["goods_total_cents"] == 50_001
    assert body["total_cents"] == 85_001
    assert codes(body["year_proof_needed"]) == ["form_8283", "non_itemizer_cash_only"]
    assert [codes(d["proof_needed"]) for d in body["donations"]] == [
        ["bank_record_or_receipt"],
        ["written_acknowledgment"],
        ["charity_receipt"],
        ["written_acknowledgment", "value_note"],
    ]
    assert [d["has_receipt"] for d in body["donations"]] == [False, True, False, False]
    assert body["thresholds"] == {
        "written_acknowledgment_cents": 25_000,
        "form_8283_noncash_cents": 50_000,
        "qualified_appraisal_cents": 500_000,
    }


def test_summary_goods_exactly_500_needs_no_form_8283(client, add_donation):
    add_donation(25_000, kind="goods")
    add_donation(25_000, kind="goods")
    body = client.get(f"{URL}/summary/2026").json()
    assert body["goods_total_cents"] == 50_000
    assert codes(body["year_proof_needed"]) == ["non_itemizer_cash_only"]


def test_summary_for_empty_year(client):
    body = client.get(f"{URL}/summary/2025").json()
    assert (body["donation_count"], body["total_cents"]) == (0, 0)
    assert body["donations"] == [] and body["year_proof_needed"] == []


def test_summary_for_year_without_tax_data(client, add_donation):
    add_donation(100, date="2028-02-29")
    response = client.get(f"{URL}/summary/2028")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "no_tax_data"
    assert "2025, 2026" in error["message"]
    assert client.get(f"{URL}/summary/1999").status_code == 422


# --- Access and storage -----------------------------------------------------------------------


@pytest.mark.parametrize("host", ["192.168.1.20", "fe80::1"])
def test_donations_are_this_computer_only(make_client, host):
    lan = make_client(host)
    for method, path in [("get", URL), ("post", URL), ("get", f"{URL}/summary/2026")]:
        response = lan.request(method, path, json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "not_this_computer"


def test_donation_notes_are_encrypted_on_disk(client, add_donation, data_dir):
    import sqlite3

    created = add_donation(100, notes="FAKE-NOTE-xyz")
    connection = sqlite3.connect(data_dir / "budget.db")
    try:
        (notes,) = connection.execute(
            "SELECT notes FROM donations WHERE id = ?", (created["id"],)
        ).fetchone()
    finally:
        connection.close()
    assert isinstance(notes, bytes) and b"FAKE-NOTE" not in notes
