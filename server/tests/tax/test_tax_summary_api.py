"""Yearly tax summary and its CSV export (roadmap #13). Fake data only."""

import csv
import io

import pytest

SUMMARY = "/api/local/tax-summary"


@pytest.fixture
def year_of_records(client, make_account):
    checking = make_account()["id"]
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    paycheck = {
        "pay_date": "2026-02-15",
        "employer": "Fake Employer",
        "account_id": checking,
        "gross_cents": 500_000,
        "federal_tax_cents": 50_000,
        "social_security_cents": 31_000,
        "medicare_cents": 7_250,
        "retirement_cents": 25_000,
        "net_cents": 386_750,
    }
    assert client.post("/api/local/paychecks", json=paycheck).status_code == 201
    for gift in (
        {"date": "2026-03-01", "organization": "Fake Food Bank", "kind": "cash", "amount": "100"},
        {"date": "2026-04-01", "organization": "=HYPERLINK(1)", "kind": "goods", "amount": "40"},
        {"date": "2025-12-31", "organization": "Last Year", "kind": "cash", "amount": "999"},
    ):
        assert client.post("/api/local/donations", json=gift).status_code == 201
    stocks = "/api/local/stocks"
    lot = {"account_id": brokerage, "symbol": "FAKE", "acquired_on": "2024-01-02"}
    assert client.post(
        f"{stocks}/lots", json={**lot, "shares": "10", "cost_basis": "1000"}
    ).is_success
    sale = {"account_id": brokerage, "symbol": "FAKE", "sold_on": "2026-06-01"}
    assert client.post(
        f"{stocks}/sales", json={**sale, "shares": "4", "proceeds": "600"}
    ).is_success
    for deduction in (
        {"kind": "medical", "amount": "300", "date": "2026-05-05", "description": "+Clinic"},
        {"kind": "medical", "amount": "50"},
        {"kind": "ira", "amount": "2000"},
    ):
        body = {"tax_year": 2026, **deduction}
        assert client.post("/api/local/deductions", json=body).status_code == 201


def lines(items):
    return {line["label"]: line["amount_cents"] for line in items}


def test_summary_totals(client, year_of_records):
    s = client.get(f"{SUMMARY}/2026").json()
    assert s["paycheck_count"] == 1
    pay = lines(s["pay"])
    assert pay["Gross pay"] == 500_000
    assert pay["Federal income tax withheld"] == 50_000
    assert pay["Pre-tax retirement (401(k), 403(b), 457)"] == 25_000
    assert pay["State income tax withheld"] == 0
    assert s["donation_count"] == 2
    assert lines(s["donations"]) == {
        "Cash gifts": 10_000,
        "Goods (value when given)": 4_000,
        "All gifts": 14_000,
    }
    assert s["stock_sale_count"] == 1
    assert lines(s["stocks"])["Long-term gain or loss"] == 20_000  # 600 - 4/10 of 1000
    assert lines(s["stocks"])["Short-term gain or loss"] == 0
    by_kind = {d["kind"]: d for d in s["deductions"]}
    assert (by_kind["medical"]["amount_cents"], by_kind["medical"]["count"]) == (35_000, 2)
    assert by_kind["medical"]["where"] == "itemized"
    assert by_kind["ira"]["where"] == "adjustment"
    assert s["standard_deduction_cents"]["single"] > 0
    assert "not tax advice" in s["disclaimer"]


def test_year_without_tax_data_still_works(client):
    s = client.get(f"{SUMMARY}/2019").json()
    assert s["standard_deduction_cents"] is None
    assert s["deductions"] == []
    assert lines(s["donations"])["All gifts"] == 0


def test_export_csv(client, year_of_records):
    response = client.get(f"{SUMMARY}/2026/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="budget-buddy-taxes-2026.csv"' in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["Section", "Item", "Date", "Amount ($)", "Notes"]
    by_item = {r[1]: r for r in rows[1:]}
    assert by_item["Gross pay"][3] == "5000.00"
    assert by_item["Fake Food Bank (cash)"][2:4] == ["2026-03-01", "100.00"]
    assert "'=HYPERLINK(1) (goods)" in by_item  # formulas are defused
    assert "Last Year (cash)" not in by_item
    stock = next(r for r in rows if r[0] == "Stock sale gain or loss")
    assert stock[2:4] == ["2026-06-01", "200.00"]
    assert stock[4].startswith("long term")
    assert by_item["Medical: +Clinic"][3] == "300.00"  # only a formula at the start is risky
    assert "itemize" in by_item["Medical"][4]
    assert "Traditional IRA only" in by_item["IRA contributions"][4]
    assert rows[-1][0] == "Note"


@pytest.mark.parametrize("year", ["1999", "2101", "abc"])
def test_year_is_checked(client, year):
    assert client.get(f"{SUMMARY}/{year}").status_code == 422
    assert client.get(f"{SUMMARY}/{year}/export.csv").status_code == 422
