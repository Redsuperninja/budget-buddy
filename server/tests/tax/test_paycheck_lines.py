"""Paycheck lines (issue #13): extra stub lines, pay period, year-to-date. Fake data only."""

import pytest

URL = "/api/local/paychecks"

# gross 2,500.00 - federal 250.00 - Social Security 155.00 - Medicare 36.25 = 2,058.75 before lines
BASE = {
    "pay_date": "2026-01-15",
    "employer": "Fake Widgets Inc",
    "gross_cents": 250_000,
    "federal_tax_cents": 25_000,
    "social_security_cents": 15_500,
    "medicare_cents": 3_625,
}


def stub(lines=(), **overrides) -> dict:
    taken = sum(BASE[k] for k in ("federal_tax_cents", "social_security_cents", "medicare_cents"))
    net = BASE["gross_cents"] - taken
    for line in lines:
        net += {"reimbursement": 1}.get(line["kind"], 0) * line["amount_cents"]
        if line["kind"] in ("local_tax", "state_disability", "paid_family_leave", "health_fsa"):
            net -= line["amount_cents"]
    return BASE | {"net_cents": net, "lines": list(lines)} | overrides


def line(kind: str, cents: int) -> dict:
    return {"kind": kind, "amount_cents": cents}


def post(client, body, status=201):
    response = client.post(URL, json=body)
    assert response.status_code == status, response.text
    return response.json()


def test_lines_count_toward_take_home(client):
    lines = [line("local_tax", 2_500), line("state_disability", 1_000), line("reimbursement", 4_000)]
    # 205,875 - 2,500 - 1,000 + 4,000 = 206,375
    paycheck = post(client, stub(lines))
    assert paycheck["net_cents"] == 206_375
    assert [(x["kind"], x["amount_cents"]) for x in paycheck["lines"]] == [
        ("local_tax", 2_500),
        ("state_disability", 1_000),
        ("reimbursement", 4_000),
    ]


def test_flags_follow_the_kind_not_the_caller(client):
    lines = [line("health_fsa", 5_000), line("local_tax", 500), line("employer_hsa", 7_000)]
    paycheck = post(client, stub(lines))
    flags = {x["kind"]: (x["pre_tax_federal"], x["pre_tax_fica"]) for x in paycheck["lines"]}
    assert flags == {
        "health_fsa": (True, True),
        "local_tax": (False, False),
        "employer_hsa": (False, False),
    }


def test_informational_lines_never_change_net(client):
    lines = [line("employer_hsa", 7_000), line("imputed_income", 1_200)]
    paycheck = post(client, stub(lines))
    assert paycheck["net_cents"] == 205_875


def test_wrong_net_with_lines_is_refused(client):
    body = stub([line("local_tax", 2_500)], net_cents=205_875)  # forgot the local tax
    response = client.post(URL, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "net_mismatch"
    assert client.get(URL).json()["total"] == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "bonus", "amount_cents": 1},  # unknown kind
        {"kind": "local_tax", "amount_cents": -1},
        {"kind": "local_tax", "amount_cents": 1.5},
        {"kind": "retirement_roth", "amount_cents": 1},  # has its own column
    ],
)
def test_bad_lines_are_refused(client, bad):
    assert client.post(URL, json=stub() | {"lines": [bad]}).status_code == 422


def test_at_most_twenty_lines(client):
    lines = [line("employer_hsa", 1)] * 21
    assert client.post(URL, json=stub(lines)).status_code == 422


def test_patch_replaces_lines_and_rechecks_net(client):
    paycheck = post(client, stub([line("local_tax", 2_500)]))
    url = f"{URL}/{paycheck['id']}"
    # Leaving lines out keeps them.
    assert client.patch(url, json={"notes": "x"}).json()["lines"][0]["amount_cents"] == 2_500
    # Replacing the lines without fixing net is refused, and nothing changes.
    assert client.patch(url, json={"lines": []}).status_code == 422
    assert client.get(url).json()["lines"][0]["kind"] == "local_tax"
    # Replacing both together works.
    changed = client.patch(url, json={"lines": [], "net_cents": 205_875})
    assert changed.status_code == 200 and changed.json()["lines"] == []
    assert client.patch(url, json={"lines": None}).status_code == 422  # can't be cleared


def test_deleting_a_paycheck_deletes_its_lines(client, data_dir):
    import sqlite3

    from app.db import database_path

    def line_count() -> int:
        with sqlite3.connect(database_path(data_dir)) as conn:
            return conn.execute("SELECT count(*) FROM paycheck_lines").fetchone()[0]

    paycheck = post(client, stub([line("local_tax", 2_500)]))
    assert line_count() == 1
    assert client.delete(f"{URL}/{paycheck['id']}").status_code == 204
    assert line_count() == 0


def test_pay_period_and_year_to_date(client):
    good = {"period_start": "2026-01-01", "period_end": "2026-01-14", "ytd_gross_cents": 250_000}
    paycheck = post(client, stub(**good))
    assert paycheck["period_start"] == "2026-01-01" and paycheck["ytd_gross_cents"] == 250_000
    assert paycheck["ytd_medicare_cents"] is None


@pytest.mark.parametrize(
    ("extra", "code"),
    [
        ({"period_start": "2026-01-14", "period_end": "2026-01-01"}, "bad_pay_period"),
        ({"period_end": "2026-01-16"}, "bad_pay_period"),  # after the pay date
        ({"ytd_gross_cents": 249_999}, "ytd_below_paycheck"),
        ({"ytd_medicare_cents": 1}, "ytd_below_paycheck"),
    ],
)
def test_bad_period_or_year_to_date_is_refused(client, extra, code):
    response = client.post(URL, json=stub(**extra))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_old_paychecks_still_work_without_lines(client):
    paycheck = post(client, BASE | {"net_cents": 205_875})
    assert paycheck["lines"] == [] and paycheck["period_start"] is None
