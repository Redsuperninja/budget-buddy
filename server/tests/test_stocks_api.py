"""Stocks API: purchases (lots), sales with FIFO, gains summary, errors. Fake data only."""

import pytest

LOTS = "/api/local/stocks/lots"
SALES = "/api/local/stocks/sales"
GAINS = "/api/local/stocks/gains"
SH = 1_000_000


@pytest.fixture
def brokerage(make_account):
    return make_account(name="Fake Brokerage", kind="brokerage")["id"]


@pytest.fixture
def buy(client, brokerage):
    def buy(acquired_on, shares, cost, symbol="FAKE", **extra):
        body = {"account_id": brokerage, "symbol": symbol, "acquired_on": acquired_on}
        body |= {"shares": shares, "cost_basis": cost, **extra}
        response = client.post(LOTS, json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return buy


@pytest.fixture
def sell(client, brokerage):
    def sell(sold_on, shares, proceeds, symbol="FAKE", expect=201, **extra):
        body = {"account_id": brokerage, "symbol": symbol, "sold_on": sold_on}
        body |= {"shares": shares, "proceeds": proceeds, **extra}
        response = client.post(SALES, json=body)
        assert response.status_code == expect, response.text
        return response.json()

    return sell


def test_buy_and_sell_across_two_lots(client, buy, sell):
    # Worked example: 5 shares for $500.00 in Jan 2025, 5 for $750.00 in Jun 2025.
    # Sell 7 on 2026-03-01 for $1,050.00 (after fees).
    first = buy("2025-01-10", "5", "500.00", symbol=" fake ")
    second = buy("2025-06-01", "5", "750.00")
    assert first["symbol"] == "FAKE"
    assert (first["shares"], first["shares_micro"], first["cost_basis_cents"]) == (
        "5",
        5 * SH,
        50_000,
    )
    assert first["long_term_from"] == "2026-01-11"

    sale = sell("2026-03-01", "7", "1050.00")
    assert (sale["shares"], sale["proceeds_cents"]) == ("7", 105_000)
    assert sale["cost_basis_cents"] == 50_000 + 30_000
    assert sale["gain_cents"] == 25_000
    assert "estimate" in sale["note"] and "not tax advice" in sale["note"]
    assert [
        (p["lot_id"], p["shares"], p["proceeds_cents"], p["cost_basis_cents"], p["term"])
        for p in sale["lots"]
    ] == [
        (first["id"], "5", 75_000, 50_000, "long"),
        (second["id"], "2", 30_000, 30_000, "short"),
    ]

    lots = client.get(LOTS, params={"symbol": "fake"}).json()
    assert [(lot["id"], lot["remaining_shares"]) for lot in lots] == [
        (first["id"], "0"),
        (second["id"], "3"),
    ]

    summary = client.get(f"{GAINS}/2026").json()
    assert summary["short_term"] == {
        "proceeds_cents": 30_000,
        "cost_basis_cents": 30_000,
        "gain_cents": 0,
    }
    assert summary["long_term"] == {
        "proceeds_cents": 75_000,
        "cost_basis_cents": 50_000,
        "gain_cents": 25_000,
    }
    assert summary["total_gain_cents"] == 25_000
    assert summary["possible_wash_sale_count"] == 0
    assert [s["id"] for s in summary["sales"]] == [sale["id"]]
    assert "estimate" in summary["note"]

    empty = client.get(f"{GAINS}/2025").json()
    assert empty["total_gain_cents"] == 0 and empty["sales"] == []


def test_selling_more_than_you_own_is_a_plain_english_error(client, buy, sell):
    buy("2026-01-05", "5", "500.00")
    error = sell("2026-02-01", "5.000001", "600.00", expect=422)["error"]
    assert error["code"] == "not_enough_shares"
    assert error["message"].startswith("You're selling more shares of FAKE than you owned on")
    assert "2026-02-01" in error["message"]
    assert client.get(SALES).json() == []  # nothing saved
    assert client.get(LOTS).json()[0]["remaining_shares"] == "5"


def test_selling_before_buying_is_refused(buy, sell):
    buy("2026-03-01", "5", "500.00")
    assert sell("2026-02-28", "1", "100.00", expect=422)["error"]["code"] == "not_enough_shares"


def test_shares_in_another_account_dont_count(client, buy, sell, make_account):
    buy("2026-01-05", "5", "500.00")
    other = make_account(name="Other Brokerage", kind="brokerage")["id"]
    error = sell("2026-02-01", "1", "100.00", account_id=other, expect=422)["error"]
    assert "same account" in error["message"]


def test_backdated_sale_that_breaks_a_later_sale(client, buy, sell):
    buy("2026-01-05", "10", "1000.00")
    sell("2026-05-01", "8", "900.00")
    error = sell("2026-03-01", "3", "300.00", expect=422)["error"]
    assert error["code"] == "not_enough_shares"
    assert "later sale of FAKE on 2026-05-01" in error["message"]
    assert len(client.get(SALES).json()) == 1


def test_purchase_entered_late_is_sold_first(client, buy, sell):
    newer = buy("2025-09-01", "5", "600.00")
    sale = sell("2026-03-01", "5", "550.00")
    assert [p["lot_id"] for p in sale["lots"]] == [newer["id"]]
    assert sale["gain_cents"] == -5_000

    older = buy("2025-02-01", "5", "400.00")  # forgot this one, entered afterwards
    sale = client.get(f"{SALES}/{sale['id']}").json()
    assert [(p["lot_id"], p["term"]) for p in sale["lots"]] == [(older["id"], "long")]
    assert sale["gain_cents"] == 15_000
    assert client.get(f"{LOTS}/{newer['id']}").json()["remaining_shares"] == "5"


def test_deleting_a_purchase_a_sale_needs(client, buy, sell):
    lot = buy("2026-01-05", "5", "500.00")
    sale = sell("2026-02-01", "2", "300.00")
    response = client.delete(f"{LOTS}/{lot['id']}")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "purchase_in_use"
    assert "Delete that sale first" in error["message"]
    assert client.get(f"{SALES}/{sale['id']}").json()["lots"][0]["lot_id"] == lot["id"]

    assert client.delete(f"{SALES}/{sale['id']}").status_code == 204
    assert client.get(f"{SALES}/{sale['id']}").status_code == 404
    assert client.get(f"{LOTS}/{lot['id']}").json()["remaining_shares"] == "5"
    assert client.delete(f"{LOTS}/{lot['id']}").status_code == 204
    assert client.get(f"{LOTS}/{lot['id']}").status_code == 404


def test_deleting_a_spare_purchase_rematches(client, buy, sell):
    old = buy("2025-01-05", "5", "500.00")
    new = buy("2026-01-05", "5", "800.00")
    sale = sell("2026-02-01", "5", "700.00")
    assert sale["lots"][0]["lot_id"] == old["id"]
    # Without the old purchase the sale now uses the newer one.
    assert client.delete(f"{LOTS}/{old['id']}").status_code == 204
    sale = client.get(f"{SALES}/{sale['id']}").json()
    assert [(p["lot_id"], p["term"]) for p in sale["lots"]] == [(new["id"], "short")]
    assert sale["gain_cents"] == -10_000


def test_deleting_a_sale_lets_later_sales_use_older_shares(client, buy, sell):
    first_lot = buy("2025-01-05", "5", "500.00")
    second_lot = buy("2025-06-05", "5", "500.00")
    first = sell("2026-02-01", "5", "600.00")
    second = sell("2026-03-01", "5", "600.00")
    assert second["lots"][0]["lot_id"] == second_lot["id"]
    assert client.delete(f"{SALES}/{first['id']}").status_code == 204
    assert client.get(f"{SALES}/{second['id']}").json()["lots"][0]["lot_id"] == first_lot["id"]


def test_possible_wash_sale_is_flagged_not_adjusted(client, buy, sell):
    buy("2026-01-05", "10", "1000.00")
    sale = sell("2026-03-31", "10", "600.00")
    assert sale["possible_wash_sale"] is False
    buy("2026-04-20", "10", "650.00")  # bought back 20 days later
    sale = client.get(f"{SALES}/{sale['id']}").json()
    assert sale["possible_wash_sale"] is True
    assert sale["gain_cents"] == -40_000  # loss not adjusted
    summary = client.get(f"{GAINS}/2026").json()
    assert summary["possible_wash_sale_count"] == 1
    assert summary["short_term"]["gain_cents"] == -40_000
    assert "wash sale" in summary["note"]


def test_fractional_shares_and_cents_inputs(client, buy, sell):
    lot = buy("2026-01-02", None, None, shares_micro=500_000, cost_basis_cents=10_000)
    assert lot["shares"] == "0.5"
    sale = sell("2026-05-01", "0.123456", None, proceeds_cents=3_000)
    assert (sale["shares_micro"], sale["cost_basis_cents"], sale["gain_cents"]) == (
        123_456,
        2_469,
        531,
    )
    assert client.get(f"{LOTS}/{lot['id']}").json()["remaining_shares"] == "0.376544"


def test_list_sales_filters(client, buy, sell):
    buy("2024-01-05", "10", "1000.00")
    buy("2024-01-05", "10", "1000.00", symbol="OTHR")
    a = sell("2025-06-01", "1", "150.00")
    b = sell("2026-06-01", "1", "150.00")
    c = sell("2026-07-01", "1", "150.00", symbol="OTHR")
    assert [s["id"] for s in client.get(SALES).json()] == [c["id"], b["id"], a["id"]]
    assert [s["id"] for s in client.get(SALES, params={"tax_year": 2026}).json()] == [
        c["id"],
        b["id"],
    ]
    assert [s["id"] for s in client.get(SALES, params={"symbol": "othr"}).json()] == [c["id"]]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"shares": 1.5}, "shares"),  # a JSON number, not text
        ({"shares": None, "shares_micro": 1.5}, "shares_micro"),
        ({"shares": None, "shares_micro": "1500000"}, "shares_micro"),
        ({"shares": "1.0000001"}, "shares"),
        ({"shares": "-1"}, "shares"),
        ({"shares": "1,000"}, "shares"),
        ({"shares": "0"}, None),
        ({"shares": "1", "shares_micro": SH}, None),  # both
        ({"shares": None}, None),  # neither
        ({"cost_basis": "-1.00"}, None),
        ({"cost_basis": None, "cost_basis_cents": -1}, "cost_basis_cents"),
        ({"cost_basis": None, "cost_basis_cents": 10.5}, "cost_basis_cents"),
        ({"cost_basis": "1.001"}, "cost_basis"),
        ({"cost_basis": None}, None),
        ({"symbol": "BAD SYMBOL"}, "symbol"),
        ({"symbol": ""}, "symbol"),
        ({"symbol": "WAYTOOLONGSYMBOL1"}, "symbol"),
        ({"acquired_on": "2026-02-30"}, "acquired_on"),
        ({"price": "1.00"}, "price"),  # unknown field
    ],
)
def test_bad_purchase_input(client, body, field):
    base = {"symbol": "FAKE", "acquired_on": "2026-01-02", "shares": "1", "cost_basis": "10.00"}
    response = client.post(LOTS, json={**base, **body})
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["fields"][0]["field"] == field
    assert "Traceback" not in error["message"]


def test_zero_cost_and_zero_proceeds_are_allowed(buy, sell):
    buy("2026-01-02", "1", "0")  # e.g. shares received for free
    sale = sell("2026-02-02", "1", "0")
    assert sale["gain_cents"] == 0


def test_brk_b_style_symbol(buy):
    assert buy("2026-01-02", "1", "1.00", symbol="brk.b")["symbol"] == "BRK.B"


def test_retirement_and_hsa_accounts_are_refused(client, make_account):
    for kind in ("retirement", "hsa"):
        account = make_account(name=f"Fake {kind}", kind=kind)["id"]
        body = {"account_id": account, "symbol": "FAKE", "acquired_on": "2026-01-02"}
        response = client.post(LOTS, json={**body, "shares": "1", "cost_basis": "1.00"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "tax_free_account"


def test_no_account_is_fine_and_separate(client, buy, sell):
    body = {"symbol": "FAKE", "acquired_on": "2026-01-02", "shares": "1", "cost_basis": "1.00"}
    assert client.post(LOTS, json=body).json()["account_id"] is None
    sale = sell("2026-02-02", "1", "2.00", account_id=None)
    assert sale["account_id"] is None and sale["gain_cents"] == 100


def test_unknown_things(client):
    assert client.get(f"{LOTS}/999").json()["error"]["code"] == "not_found"
    assert client.get(f"{SALES}/999").json()["error"]["message"].startswith("That stock sale")
    assert client.delete(f"{LOTS}/999").status_code == 404
    body = {"account_id": 999, "symbol": "FAKE", "acquired_on": "2026-01-02"}
    response = client.post(LOTS, json={**body, "shares": "1", "cost_basis": "1.00"})
    assert response.status_code == 404
    assert client.get(f"{GAINS}/1999").status_code == 422
    assert client.get(f"{GAINS}/2101").status_code == 422


def test_account_with_stocks_cant_be_deleted(client, brokerage, buy):
    lot = buy("2026-01-02", "1", "1.00")
    response = client.delete(f"/api/local/accounts/{brokerage}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_has_stocks"
    client.delete(f"{LOTS}/{lot['id']}")
    assert client.delete(f"/api/local/accounts/{brokerage}").status_code == 204


def test_home_network_cannot_reach_stocks(make_client):
    lan = make_client(peer="192.168.1.20")
    assert lan.get(LOTS).status_code == 403
    assert lan.get(f"{GAINS}/2026").status_code == 403


@pytest.mark.parametrize("kind", ["retirement", "hsa"])
def test_account_with_stocks_cant_become_tax_free(client, brokerage, buy, kind):
    lot = buy("2026-01-02", "1", "1.00")
    url = f"/api/local/accounts/{brokerage}"
    response = client.patch(url, json={"kind": kind})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "account_has_stocks"
    assert "retirement account or HSA" in error["message"]
    assert client.get(url).json()["kind"] == "brokerage"
    # Other edits are fine, and so is the change once the stocks are gone.
    assert client.patch(url, json={"kind": "other"}).status_code == 200
    client.delete(f"{LOTS}/{lot['id']}")
    assert client.patch(url, json={"kind": kind}).json()["kind"] == kind


def test_wash_sale_limits_are_explained(client, make_account):
    account = make_account(name="Fake IRA", kind="retirement")["id"]
    body = {"account_id": account, "symbol": "FAKE", "acquired_on": "2026-01-02"}
    response = client.post(LOTS, json={**body, "shares": "1", "cost_basis": "1.00"})
    assert "a spouse buying it" in response.json()["error"]["message"]
    assert "We don't check those purchases." in client.get(f"{GAINS}/2026").json()["note"]
