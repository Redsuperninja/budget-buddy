"""Dividends found in transactions, filed under "Dividends", with their deposit sweeps. Fake data
shaped like a bank's IRA export."""

import pytest
from csv_helpers import ok, send

TXN = "/api/local/transactions"
DIV = "/api/local/dividends"

IRA_CSV = (
    "Date,Description,Amount\r\n"
    "09/08/2026,FAKECO INC COMMON STOCK CASH DIV ON 1 SHS REC 08/25/26 PAY 09/08/26,1.30\r\n"
    "09/08/2026,FAKE IRA DEPOSIT SWEEP FAKE BANK NA INTRA-DAY DEPOSIT,-1.30\r\n"
    "09/10/2026,FAKE FUND ORDINARY DIVIDEND,2.00\r\n"
    "09/15/2026,FAKE IRA DEPOSIT SWEEP FAKE BANK NA INTRA-DAY DEPOSIT,-2.00\r\n"
    "09/12/2026,INDIVIDUAL CONTRIBUTION,50.00\r\n"
)


@pytest.fixture
def ira(make_account):
    return make_account(name="Fake IRA", kind="retirement")["id"]


def by_description(client, **params) -> dict:
    items = client.get(TXN, params={"limit": 500, **params}).json()["items"]
    return {t["description"][:20]: t for t in items}


def category_name(client, category_id):
    names = {c["id"]: c["name"] for c in client.get("/api/local/categories").json()}
    return names.get(category_id)


def test_import_files_dividends_and_links_their_sweeps(client, ira):
    result = ok(send(client, ira, IRA_CSV, "commit"))
    # The second sweep is 5 days after its dividend: too late to be its sweep.
    assert (result["dividends_found"], result["dividend_sweeps_linked"]) == (2, 1)

    rows = by_description(client)
    first = rows["FAKECO INC COMMON ST"]
    assert category_name(client, first["category_id"]) == "Dividends"
    assert category_name(client, rows["INDIVIDUAL CONTRIBUT"]["category_id"]) is None

    year = client.get(f"{DIV}/2026").json()
    assert [
        (d["payer"], d["paid_on"], d["amount_cents"], d["taxed"]) for d in year["dividends"]
    ] == [
        ("FAKECO INC", "2026-09-08", 130, False),
        ("FAKE FUND", "2026-09-10", 200, False),
    ]
    assert year["dividends"][0]["sweep_transaction_id"] == rows["FAKE IRA DEPOSIT SWE"]["id"]
    assert year["dividends"][1]["sweep_transaction_id"] is None
    assert (year["total_cents"], year["taxed_cents"]) == (330, 0)  # inside an IRA: not taxed
    assert "1099-DIV" in year["note"]

    hidden = by_description(client, hide_dividends=True)
    # The linked sweep is hidden with its dividend; the unlinked one still shows.
    assert sorted(t["amount_cents"] for t in hidden.values()) == [-200, 5_000]


def test_find_looks_through_older_transactions_once(client, ira, add_txn):
    add_txn(ira, 130, date="2026-09-08", description="FAKECO CASH DIV")
    add_txn(ira, -130, date="2026-09-09", description="FAKE DEPOSIT SWEEP")
    # Adding by hand finds them straight away, so there's nothing left to find.
    assert client.post(f"{DIV}/find").json() == {"found": 0, "sweeps_linked": 0}
    assert client.get(f"{DIV}/2026").json()["dividends"][0]["sweep_transaction_id"] is not None


def test_a_brokerage_dividend_is_taxed(client, make_account, add_txn):
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    add_txn(brokerage, 1_000, date="2026-03-01", description="Fake Fund Qualified Dividend")
    year = client.get(f"{DIV}/2026").json()
    assert (year["total_cents"], year["taxed_cents"]) == (1_000, 1_000)
    assert year["dividends"][0]["payer"] == "Fake Fund"


def test_your_own_category_is_kept(client, ira, add_txn, make_account):
    other_income = next(
        c["id"] for c in client.get("/api/local/categories").json() if c["name"] == "Other Income"
    )
    paid = add_txn(ira, 130, description="FAKECO CASH DIV", category_id=other_income)
    assert client.get(f"{TXN}/{paid['id']}").json()["category_id"] == other_income
    assert len(client.get(f"{DIV}/{paid['date'][:4]}").json()["dividends"]) == 1


def test_not_a_dividend_is_remembered(client, ira, add_txn):
    paid = add_txn(ira, 130, date="2026-09-08", description="FAKECO CASH DIV")
    add_txn(ira, -130, date="2026-09-08", description="FAKE DEPOSIT SWEEP")
    dividend = client.get(f"{DIV}/2026").json()["dividends"][0]

    assert client.post(f"{DIV}/{dividend['id']}/dismiss").status_code == 204
    assert client.get(f"{DIV}/2026").json()["dividends"] == []
    assert client.get(f"{TXN}/{paid['id']}").json()["category_id"] is None
    assert len(by_description(client, hide_dividends=True)) == 2  # both show again
    assert client.post(f"{DIV}/find").json() == {"found": 0, "sweeps_linked": 0}
    assert client.post(f"{DIV}/{dividend['id']}/dismiss").status_code == 404


def test_money_out_and_transfers_are_never_dividends(client, ira, add_txn):
    add_txn(ira, -130, description="FAKECO CASH DIV REVERSAL")
    add_txn(ira, 130, description="Fake interest", kind="refund")
    assert client.post(f"{DIV}/find").json()["found"] == 0


def test_deleting_the_payment_deletes_the_dividend(client, ira, add_txn):
    paid = add_txn(ira, 130, date="2026-09-08", description="FAKECO CASH DIV")
    assert client.delete(f"{TXN}/{paid['id']}").status_code == 204
    assert client.get(f"{DIV}/2026").json()["dividends"] == []
