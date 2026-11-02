"""The tax summary narrowed to the chosen filing status (roadmap 25j). Only which numbers are shown
changes, never the numbers. Worked examples from the 2025 and 2026 data files. Fake data only."""

import pytest

SUMMARY = "/api/local/tax-summary"
PREFS = "/api/local/tax-preferences"

# Basic standard deduction in cents (app/tax_data/<year>.json, Rev. Proc. 2025-32).
ALL_2025 = {
    "single": 1_575_000,
    "married_filing_jointly": 3_150_000,
    "married_filing_separately": 1_575_000,
    "head_of_household": 2_362_500,
}
ALL_2026 = {
    "single": 1_610_000,
    "married_filing_jointly": 3_220_000,
    "married_filing_separately": 1_610_000,
    "head_of_household": 2_415_000,
}


def _summary(client, year: int) -> dict:
    response = client.get(f"{SUMMARY}/{year}")
    assert response.status_code == 200, response.text
    return response.json()


def _without_date(summary: dict) -> dict:
    return {k: v for k, v in summary.items() if k != "generated_on"}


@pytest.mark.parametrize(("year", "amounts"), [(2025, ALL_2025), (2026, ALL_2026)])
def test_not_set_shows_every_status_as_before(client, year, amounts):
    s = _summary(client, year)
    assert s["filing_status"] is None
    assert s["standard_deduction_cents"] == amounts


@pytest.mark.parametrize(
    ("year", "status", "cents"),
    [
        (2025, "single", 1_575_000),
        (2025, "married_filing_jointly", 3_150_000),
        (2025, "married_filing_separately", 1_575_000),
        (2025, "head_of_household", 2_362_500),
        (2026, "single", 1_610_000),
        (2026, "married_filing_jointly", 3_220_000),
        (2026, "married_filing_separately", 1_610_000),
        (2026, "head_of_household", 2_415_000),
    ],
)
def test_a_chosen_status_shows_only_its_amount(client, year, status, cents):
    assert client.put(PREFS, json={"filing_status": status}).status_code == 200
    s = _summary(client, year)
    assert s["filing_status"] == status
    assert s["standard_deduction_cents"] == {status: cents}


def test_choosing_a_status_changes_nothing_else(client, make_account):
    account = make_account()["id"]
    paycheck = {"pay_date": "2026-02-15", "employer": "FAKECO", "account_id": account}
    paycheck |= {"gross_cents": 500_000, "federal_tax_cents": 100_000, "net_cents": 400_000}
    assert client.post("/api/local/paychecks", json=paycheck).status_code == 201
    gift = {"date": "2026-03-01", "organization": "FAKECO Food Bank", "kind": "cash"}
    assert client.post("/api/local/donations", json={**gift, "amount": "100"}).status_code == 201
    before = _without_date(_summary(client, 2026))

    client.put(PREFS, json={"filing_status": "married_filing_jointly"})
    narrowed = _without_date(_summary(client, 2026))
    assert {k for k in before if before[k] != narrowed[k]} == {
        "filing_status",
        "standard_deduction_cents",
    }

    client.put(PREFS, json={"filing_status": None})
    assert _without_date(_summary(client, 2026)) == before


def test_a_year_without_tax_data_still_has_no_standard_deduction(client):
    client.put(PREFS, json={"filing_status": "single"})
    s = _summary(client, 2001)
    assert s["filing_status"] == "single"
    assert s["standard_deduction_cents"] is None


def test_the_csv_export_is_the_same_either_way(client):
    before = client.get(f"{SUMMARY}/2026/export.csv").content
    client.put(PREFS, json={"filing_status": "head_of_household"})
    assert client.get(f"{SUMMARY}/2026/export.csv").content == before
