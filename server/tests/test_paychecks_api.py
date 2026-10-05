"""Paychecks API: CRUD, the adds-up rule, deposit links, year-to-date summary. Fake data only."""

import logging
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import text

from app.crypto import FieldCipher
from app.db import alembic_config, create_db_engine
from app.services.paychecks import max_social_security_tax

URL = "/api/local/paychecks"
TXN_URL = "/api/local/transactions"

# A worked example (fake numbers):
#   gross 2,500.00 - federal 250.00 - state 100.00 - Social Security 155.00 - Medicare 36.25
#   - 401(k) 150.00 - HSA 50.00 - health insurance 80.00 - Roth 401(k) 50.00 - union dues 10.00
#   = net 1,618.75
STUB = {
    "pay_date": "2026-01-15",
    "employer": "Fake Widgets Inc",
    "gross_cents": 250_000,
    "federal_tax_cents": 25_000,
    "state_tax_cents": 10_000,
    "social_security_cents": 15_500,
    "medicare_cents": 3_625,
    "retirement_cents": 15_000,
    "hsa_cents": 5_000,
    "health_insurance_cents": 8_000,
    "roth_retirement_cents": 5_000,
    "other_deductions_cents": 1_000,
    "net_cents": 161_875,
}
AMOUNTS = [k for k in STUB if k.endswith("_cents")]


@pytest.fixture
def add_paycheck(client):
    def add(**overrides) -> dict:
        response = client.post(URL, json=STUB | overrides)
        assert response.status_code == 201, response.text
        return response.json()

    return add


def simple_stub(employer: str, gross: int, ss: int, pay_date="2026-03-01") -> dict:
    """Gross, Social Security, and the matching net. Nothing else."""
    return {
        "pay_date": pay_date,
        "employer": employer,
        "gross_cents": gross,
        "social_security_cents": ss,
        "net_cents": gross - ss,
    }


# --- CRUD -------------------------------------------------------------------------------------


def test_paycheck_crud(client, add_paycheck, make_account):
    account = make_account()["id"]
    created = add_paycheck(account_id=account, notes="fake note")
    assert {k: created[k] for k in STUB} == STUB
    assert created["notes"] == "fake note"
    assert created["deposit_transaction_id"] is None
    paycheck_id = created["id"]

    assert client.get(f"{URL}/{paycheck_id}").json()["net_cents"] == 161_875

    # Moving 10.00 from union dues to the Roth line still adds up.
    patch = {"other_deductions_cents": 0, "roth_retirement_cents": 6_000, "employer": " Acme "}
    response = client.patch(f"{URL}/{paycheck_id}", json=patch)
    assert response.status_code == 200, response.text
    assert response.json()["employer"] == "Acme"
    assert response.json()["roth_retirement_cents"] == 6_000

    listed = client.get(URL, params={"year": 2026}).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == paycheck_id
    assert client.get(URL, params={"year": 2025}).json()["total"] == 0

    assert client.delete(f"{URL}/{paycheck_id}").status_code == 204
    assert client.get(f"{URL}/{paycheck_id}").status_code == 404


def test_lines_default_to_zero(client):
    body = {"pay_date": "2026-01-15", "employer": "Fake", "gross_cents": 1_000, "net_cents": 1_000}
    response = client.post(URL, json=body)
    assert response.status_code == 201
    assert all(response.json()[k] == 0 for k in AMOUNTS if k not in ("gross_cents", "net_cents"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"gross_cents": -1},
        {"hsa_cents": -500},
        {"gross_cents": 2500.0},  # floats are never money
        {"net_cents": "161875"},
        {"net_cents": None},
        {"employer": "   "},
        {"employer": "x" * 201},
        {"pay_date": "01/15/2026"},
        {"bonus_cents": 5},  # unknown fields are rejected, not ignored
    ],
)
def test_bad_input_is_rejected(client, overrides):
    response = client.post(URL, json=STUB | overrides)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_account_is_404(client):
    assert client.post(URL, json=STUB | {"account_id": 999}).status_code == 404


# --- gross - taxes - deductions = net ----------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "expected_net", "difference", "wording"),
    [
        ({"net_cents": 161_975}, 161_875, 100, "$1.00 more"),
        ({"net_cents": 161_874}, 161_875, -1, "$0.01 less"),
        # Forgot the HSA line: the stub's net is 50.00 lower than the lines entered say.
        ({"hsa_cents": 0}, 166_875, -5_000, "$50.00 less"),
        # More taken out than earned.
        ({"gross_cents": 100_000}, 11_875, 150_000, "$1,500.00 more"),
    ],
)
def test_mismatch_names_the_difference(client, overrides, expected_net, difference, wording):
    response = client.post(URL, json=STUB | overrides)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "net_mismatch"
    assert error["expected_net_cents"] == expected_net
    assert error["difference_cents"] == difference
    assert wording in error["message"]


def test_patch_checks_the_final_numbers(client, add_paycheck):
    paycheck_id = add_paycheck()["id"]
    response = client.patch(f"{URL}/{paycheck_id}", json={"gross_cents": 260_000})
    assert response.status_code == 422
    assert response.json()["error"]["difference_cents"] == -10_000
    response = client.patch(
        f"{URL}/{paycheck_id}", json={"gross_cents": 260_000, "net_cents": 171_875}
    )
    assert response.status_code == 200
    response = client.patch(f"{URL}/{paycheck_id}", json={"net_cents": None})
    assert response.status_code == 422


# --- linking the bank deposit -----------------------------------------------------------------


@pytest.fixture
def deposit(make_account, add_txn):
    checking = make_account()["id"]
    return add_txn(checking, STUB["net_cents"], description="Fake payroll deposit")


def test_link_deposit(client, add_paycheck, deposit):
    paycheck_id = add_paycheck()["id"]
    response = client.post(f"{URL}/{paycheck_id}/deposit", json={"transaction_id": deposit["id"]})
    assert response.status_code == 200, response.text
    linked = response.json()
    assert linked["deposit_transaction_id"] == deposit["id"]
    assert linked["account_id"] == deposit["account_id"]
    # Linking again is a no-op.
    again = client.post(f"{URL}/{paycheck_id}/deposit", json={"transaction_id": deposit["id"]})
    assert again.status_code == 200

    # One deposit backs one paycheck.
    other = add_paycheck()["id"]
    response = client.post(f"{URL}/{other}/deposit", json={"transaction_id": deposit["id"]})
    assert (response.status_code, response.json()["error"]["code"]) == (409, "already_linked")

    response = client.delete(f"{URL}/{paycheck_id}/deposit")
    assert response.json()["deposit_transaction_id"] is None
    assert client.delete(f"{URL}/{paycheck_id}/deposit").status_code == 409


@pytest.mark.parametrize(
    ("account_kind", "amount", "kind"),
    [
        ("checking", STUB["net_cents"] + 1, "normal"),  # not the net pay
        ("checking", -STUB["net_cents"], "normal"),  # money going out
        ("checking", STUB["net_cents"], "adjustment"),  # e.g. an opening balance
        ("credit_card", STUB["net_cents"], "normal"),
    ],
)
def test_link_rejects_wrong_deposit(
    client, add_paycheck, make_account, add_txn, account_kind, amount, kind
):
    account = make_account(kind=account_kind)["id"]
    txn = add_txn(account, amount, kind=kind)
    paycheck_id = add_paycheck()["id"]
    response = client.post(f"{URL}/{paycheck_id}/deposit", json={"transaction_id": txn["id"]})
    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_deposit")


def test_savings_deposit_can_be_linked(client, add_paycheck, make_account, add_txn):
    savings = make_account(kind="savings")["id"]
    txn = add_txn(savings, STUB["net_cents"])
    paycheck_id = add_paycheck()["id"]
    response = client.post(f"{URL}/{paycheck_id}/deposit", json={"transaction_id": txn["id"]})
    assert response.status_code == 200


def test_linked_pair_stays_consistent(client, add_paycheck, deposit, make_account):
    paycheck_id = add_paycheck()["id"]
    client.post(f"{URL}/{paycheck_id}/deposit", json={"transaction_id": deposit["id"]})

    # The paycheck's net pay and account must keep matching the deposit...
    patch = {"net_cents": 161_775, "other_deductions_cents": 1_100}
    assert client.patch(f"{URL}/{paycheck_id}", json=patch).status_code == 409
    assert client.patch(f"{URL}/{paycheck_id}", json={"account_id": None}).status_code == 409
    # ...but other edits are fine.
    assert client.patch(f"{URL}/{paycheck_id}", json={"employer": "Fake Co"}).status_code == 200

    # The deposit can't change amount, account, or kind, or become half of a transfer.
    txn_url = f"{TXN_URL}/{deposit['id']}"
    for patch in ({"amount_cents": 1}, {"kind": "refund"}):
        response = client.patch(txn_url, json=patch)
        assert (response.status_code, response.json()["error"]["code"]) == (
            409,
            "linked_to_paycheck",
        )
    assert client.patch(txn_url, json={"description": "Payroll"}).status_code == 200
    savings = make_account(kind="savings")["id"]
    out = client.post(
        TXN_URL,
        json={"account_id": savings, "date": "2026-01-15", "description": "x", "amount_cents": -1},
    ).json()
    response = client.post(f"{txn_url}/transfer", json={"other_id": out["id"]})
    assert response.status_code == 409


def test_deleting_either_side_keeps_the_other(client, add_paycheck, deposit):
    first = add_paycheck()["id"]
    client.post(f"{URL}/{first}/deposit", json={"transaction_id": deposit["id"]})
    assert client.delete(f"{URL}/{first}").status_code == 204
    assert client.get(f"{TXN_URL}/{deposit['id']}").status_code == 200

    second = add_paycheck()["id"]
    client.post(f"{URL}/{second}/deposit", json={"transaction_id": deposit["id"]})
    assert client.delete(f"{TXN_URL}/{deposit['id']}").status_code == 204
    assert client.get(f"{URL}/{second}").json()["deposit_transaction_id"] is None


# --- year-to-date summary ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wage_base", "rate", "expected"),
    [
        (17_610_000, Decimal("0.062"), 1_091_820),  # 2025: 176,100.00 x 6.2% = 10,918.20
        (18_450_000, Decimal("0.062"), 1_143_900),  # 2026: 184,500.00 x 6.2% = 11,439.00
        (5, Decimal("0.1"), 1),  # half a cent rounds up
        (4, Decimal("0.1"), 0),
    ],
)
def test_max_social_security_tax(wage_base, rate, expected):
    assert max_social_security_tax(wage_base, rate) == expected


def test_summary_totals(client, add_paycheck):
    add_paycheck()
    add_paycheck(pay_date="2026-01-31", employer="FAKE  widgets inc")  # same employer
    add_paycheck(pay_date="2025-12-31")  # paid last year: not counted
    summary = client.get(f"{URL}/summary", params={"year": 2026}).json()
    assert summary["paycheck_count"] == 2
    assert summary["totals"] == {k: 2 * STUB[k] for k in AMOUNTS}
    assert summary["taxes_withheld_cents"] == 2 * (25_000 + 10_000 + 15_500 + 3_625)
    assert summary["pre_tax_deductions_cents"] == 2 * (15_000 + 5_000 + 8_000)
    assert summary["after_tax_deductions_cents"] == 2 * (5_000 + 1_000)
    assert summary["social_security_by_employer"] == {"Fake Widgets Inc": 31_000}
    check = summary["social_security_check"]
    assert check["max_tax_cents"] == 1_143_900
    assert check["rate"] == "0.062"
    assert (check["withheld_cents"], check["over_max_cents"]) == (31_000, 0)
    assert "within" in check["message"]


@pytest.mark.parametrize(
    ("year", "paychecks", "over", "wording"),
    [
        # 2026 maximum is 11,439.00. Exactly at it is fine.
        (2026, [("Job A", 1_143_900)], 0, "within"),
        # Two jobs, each under the maximum, together 100.00 over: claim it on the tax return.
        (2026, [("Job A", 800_000), ("Job B", 353_900)], 10_000, "Together"),
        # One employer alone went over: that employer has to fix it.
        (2026, [("Job A", 1_143_901)], 1, "One employer"),
        (2025, [("Job A", 600_000), ("Job B", 491_821)], 1, "Together"),  # 2025 max 10,918.20
    ],
)
def test_social_security_cap(client, year, paychecks, over, wording):
    for employer, ss in paychecks:
        stub = simple_stub(employer, 20_000_000, ss, pay_date=f"{year}-06-01")
        assert client.post(URL, json=stub).status_code == 201
    check = client.get(f"{URL}/summary", params={"year": year}).json()["social_security_check"]
    assert check["over_max_cents"] == over
    assert wording in check["message"]
    if over:
        assert "each person" in check["message"]


def test_summary_for_year_without_tax_data(client):
    client.post(URL, json=simple_stub("Job A", 100_000, 6_200, pay_date="2024-06-01"))
    summary = client.get(f"{URL}/summary", params={"year": 2024}).json()
    assert summary["paycheck_count"] == 1
    assert summary["social_security_check"] is None
    assert "2024" in summary["message"]


def test_summary_rejects_silly_years(client):
    assert client.get(f"{URL}/summary", params={"year": 1999}).status_code == 422


def test_nothing_personal_is_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    stub = STUB | {"employer": "Zyxwv Fake Employer", "notes": "fake secret"}
    paycheck_id = client.post(URL, json=stub).json()["id"]
    client.post(URL, json=stub | {"net_cents": 1})
    client.patch(f"{URL}/{paycheck_id}", json={"gross_cents": 1})
    client.get(f"{URL}/summary", params={"year": 2026})
    for secret in ("Zyxwv", "fake secret", "161875", "1,618.75", "2,500.00"):
        assert secret not in caplog.text


# --- migration 0004 ---------------------------------------------------------------------------


def test_migration_0004_keeps_existing_paychecks(tmp_path):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(b"k" * 32))
    config = alembic_config()

    def migrate(direction, target):
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            getattr(command, direction)(config, target)

    def rows(sql):
        with engine.connect() as conn:
            return conn.execute(text(sql)).all()

    try:
        migrate("upgrade", "0004")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO accounts (id, name, kind) VALUES (1, 'A', 'checking')"))
            conn.execute(
                text(
                    "INSERT INTO paychecks (id, pay_date, employer, account_id, gross_cents, "
                    "net_cents) VALUES (7, '2026-01-15', 'Fake', 1, 100, 100)"
                )
            )
        migrate("upgrade", "0005")
        assert rows(
            "SELECT id, account_id, gross_cents, health_insurance_cents, roth_retirement_cents, "
            "deposit_transaction_id FROM paychecks"
        ) == [(7, 1, 100, 0, 0, None)]
        with pytest.raises(Exception, match="CHECK constraint"):
            with engine.begin() as conn:
                conn.execute(text("UPDATE paychecks SET roth_retirement_cents = -1"))

        migrate("downgrade", "0004")
        assert rows("SELECT id, account_id, gross_cents, net_cents FROM paychecks") == [
            (7, 1, 100, 100)
        ]
    finally:
        engine.dispose()
