"""Holdings by account with typed-in prices, and retirement contributions against the limits.

Fake data only. Limits used: 2026 tax data (401(k) $24,500, IRA $7,500, HSA $4,400 / $8,750).
"""

import pytest

LOTS = "/api/local/stocks/lots"
SALES = "/api/local/stocks/sales"
HOLDINGS = "/api/local/stocks/holdings"
PRICES = "/api/local/stocks/prices"
RETIREMENT = "/api/local/retirement"


@pytest.fixture
def ira(make_account) -> int:
    return make_account(name="Fake IRA", kind="retirement")["id"]


@pytest.fixture
def brokerage(make_account) -> int:
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


def buy(client, account_id, symbol, shares, cost, on="2025-01-02"):
    body = {"account_id": account_id, "symbol": symbol, "acquired_on": on}
    response = client.post(LOTS, json=body | {"shares": shares, "cost_basis": cost})
    assert response.status_code == 201, response.text


def test_holdings_by_account_with_prices(client, brokerage, ira):
    buy(client, brokerage, "FAKE", "3", "100.00")  # $33.33... a share
    buy(client, ira, "FAKE", "1.5", "60.00")
    sale = {"account_id": brokerage, "symbol": "FAKE", "sold_on": "2026-02-02"}
    client.post(SALES, json=sale | {"shares": "1", "proceeds": "40.00"})
    # Before any price: costs only.
    before = client.get(HOLDINGS).json()
    assert before["value_cents"] is None
    assert "typed in" in before["note"]
    assert (
        client.post(
            PRICES, json={"symbol": "fake", "price": "41.335", "as_of": "2026-10-08"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            PRICES, json={"symbol": "fake", "price": "41.33", "as_of": "2026-10-08"}
        ).status_code
        == 204
    )
    after = client.get(HOLDINGS).json()
    taxed, untaxed = after["accounts"]
    assert (taxed["account_name"], taxed["taxed"], untaxed["taxed"]) == (
        "Fake Brokerage",
        True,
        False,
    )
    (held,) = taxed["holdings"]
    # 2 of 3 shares left: cost 100.00 - 33.33 (one share, rounded half up) = 66.67.
    assert (held["shares"], held["cost_basis_cents"]) == ("2", 6_667)
    assert (held["value_cents"], held["unrealized_gain_cents"]) == (8_266, 1_599)
    (ira_held,) = untaxed["holdings"]
    assert ira_held["value_cents"] == 6_200  # 1.5 x 41.33 = 61.995, rounded half up
    assert after["value_cents"] == 8_266 + 6_200
    assert after["cost_basis_cents"] == 6_667 + 6_000


def test_sold_out_shares_are_not_held(client, brokerage):
    buy(client, brokerage, "FAKE", "1", "10.00")
    client.post(SALES, json={"account_id": brokerage, "symbol": "FAKE", "sold_on": "2026-02-02",
                             "shares": "1", "proceeds": "12.00"})  # fmt: skip
    assert client.get(HOLDINGS).json()["accounts"] == []


def test_a_new_price_replaces_the_old_one(client):
    buy(client, None, "FAKE", "1", "10.00")
    for price in ("11.00", "12.50"):
        client.post(PRICES, json={"symbol": "FAKE", "price": price, "as_of": "2026-10-08"})
    (group,) = client.get(HOLDINGS).json()["accounts"]
    assert group["account_name"] == "Not in an account"
    assert group["holdings"][0]["price_cents"] == 1_250


def test_retirement_contributions_against_limits(client):
    stub = {
        "pay_date": "2026-01-15", "employer": "Fake Widgets Inc", "gross_cents": 250_000,
        "retirement_cents": 15_000, "roth_retirement_cents": 5_000, "hsa_cents": 5_000,
        "net_cents": 225_000,
    }  # fmt: skip
    for pay_date in ("2026-01-15", "2026-02-15"):
        assert (
            client.post("/api/local/paychecks", json=stub | {"pay_date": pay_date}).status_code
            == 201
        )
    client.post("/api/local/paychecks", json=stub | {"pay_date": "2025-12-15"})  # other year
    for kind, amount in (("ira", "7600.00"), ("hsa", "100.00")):
        client.post(
            "/api/local/deductions", json={"tax_year": 2026, "kind": kind, "amount": amount}
        )
    body = client.get(f"{RETIREMENT}/2026").json()
    assert body["is_estimate"] and "not tax advice" in body["note"]
    k401, ira, hsa_self, hsa_family = body["limits"]
    assert (k401["contributed_cents"], k401["limit_cents"], k401["left_cents"]) == (
        40_000,
        2_450_000,
        2_410_000,
    )
    assert k401["catch_up_cents"] == [800_000, 1_125_000]
    assert k401["catch_up_ages"] == ["age 50 or older", "ages 60 to 63"]
    assert "457(b)" in k401["note"] and "each person" in body["note"]
    assert (ira["contributed_cents"], ira["over_cents"], ira["left_cents"]) == (760_000, 10_000, 0)
    assert hsa_self["contributed_cents"] == 10_000 + 10_000
    assert (hsa_self["limit_cents"], hsa_family["limit_cents"]) == (440_000, 875_000)


def test_retirement_needs_tax_data_for_the_year(client):
    response = client.get(f"{RETIREMENT}/2001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_tax_data"
