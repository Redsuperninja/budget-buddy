"""Nothing outside the split route touches a split transaction (ADR-0017, roadmap 10f-3).
Fake data only."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_splits import URL, cats, checking, part, put, two_parts  # noqa: F401

from app.models import Donation, Transaction
from app.services.tax.repeat_gifts import repeat_gifts

RULES = "/api/local/category-rules"


def split(client, add_txn, account, cats, amount=-10_000, **extra) -> int:  # noqa: F811
    txn = add_txn(account, amount, **extra)
    parts = two_parts(cats, amount) if amount < 0 else [
        part(cats["Interest"], amount - 30), part(cats["Other Income"], 30)]  # fmt: skip
    assert put(client, txn["id"], parts).status_code == 200
    return txn["id"]


def unchanged(client, txn_id) -> None:
    got = client.get(f"{URL}/{txn_id}").json()
    assert (got["category_id"], got["kind"], got["transfer_pair_id"]) == (None, "normal", None)
    assert len(got["splits"]) >= 2


def refused(response) -> None:
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "split_transaction"
    assert "split" in error["message"].lower()


def test_rules_do_not_sort_a_split(client, add_txn, checking, cats):  # noqa: F811
    txn = split(client, add_txn, checking, cats, description="FAKE GROCERY MART")
    rule = {"pattern": "fake grocery", "category_id": cats["Dining Out"]}
    assert client.post(RULES, json=rule).status_code == 201
    assert client.post(f"{RULES}/apply").json() == {"categorized": 0}
    unchanged(client, txn)


def test_a_split_is_not_waiting_for_a_category(client, add_txn, checking, cats):  # noqa: F811
    txn = split(client, add_txn, checking, cats)
    plain = add_txn(checking, -500)
    items = client.get(URL, params={"uncategorized": "true"}).json()["items"]
    assert [t["id"] for t in items] == [plain["id"]]
    assert txn not in [t["id"] for t in items]


def test_automatic_transfer_matching_skips_a_split(client, add_txn, make_account, checking, cats):  # noqa: F811
    out = split(client, add_txn, checking, cats, description="ONLINE TRANSFER TO SAVINGS")
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    other = add_txn(savings, 10_000, description="ONLINE TRANSFER FROM CHECKING")
    twin = add_txn(checking, -7_500, description="ONLINE TRANSFER TO SAVINGS")
    twin_in = add_txn(savings, 7_500, description="ONLINE TRANSFER FROM CHECKING")
    matched = client.post(f"{URL}/match-transfers").json()["matched"]
    assert matched <= 1
    assert client.post(f"{URL}/match-again").status_code == 200
    unchanged(client, out)
    assert client.get(f"{URL}/{other['id']}").json()["transfer_pair_id"] is None
    paired = [client.get(f"{URL}/{i['id']}").json() for i in (twin, twin_in)]
    assert [p["transfer_pair_id"] for p in paired] == [twin_in["id"], twin["id"]]


def test_manual_transfer_link_is_refused_either_way(client, add_txn, make_account, checking, cats):  # noqa: F811
    out = split(client, add_txn, checking, cats)
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    other = add_txn(savings, 10_000)
    refused(client.post(f"{URL}/{out}/transfer", json={"other_id": other["id"]}))
    refused(client.post(f"{URL}/{other['id']}/transfer", json={"other_id": out}))
    unchanged(client, out)
    assert client.get(f"{URL}/{other['id']}").json()["transfer_pair_id"] is None


def test_card_payment_filing_skips_a_split(client, add_txn, make_account, checking, cats):  # noqa: F811
    out = split(client, add_txn, checking, cats, description="FAKEBANK CREDIT CRD AUTOPAY")
    card = make_account(name="Fakebank Rewards", kind="credit_card")["id"]
    add_txn(card, 10_000, description="PAYMENT THANK YOU")
    twin = add_txn(checking, -7_500, description="FAKEBANK CREDIT CRD AUTOPAY")
    add_txn(card, 7_500, description="PAYMENT THANK YOU")
    assert client.post(f"{URL}/match-again").status_code == 200
    unchanged(client, out)
    assert client.get(f"{URL}/{twin['id']}").json()["transfer_pair_id"] is not None


def test_dividend_finder_skips_a_split(client, add_txn, make_account, cats):  # noqa: F811
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    txn = split(client, add_txn, ira, cats, amount=130, description="FAKE PAYMENT")
    assert client.patch(f"{URL}/{txn}", json={"description": "FAKECO CASH DIV"}).status_code == 200
    twin = add_txn(ira, 130, description="FAKE PAYMENT")
    renamed = client.patch(f"{URL}/{twin['id']}", json={"description": "OTHERCO CASH DIV"})
    assert renamed.status_code == 200
    found = client.post("/api/local/dividends/find")
    assert found.status_code == 200, found.text
    assert found.json()["found"] == 1
    listed = client.get("/api/local/dividends/2026").json()["dividends"]
    assert [d["transaction_id"] for d in listed] == [twin["id"]]
    unchanged(client, txn)


def test_charity_is_refused_and_the_split_stays(client, add_txn, checking, cats):  # noqa: F811
    txn = split(client, add_txn, checking, cats, amount=-4_000)
    gift = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": txn}  # fmt: skip
    refused(client.post("/api/local/donations", json=gift))
    refused(client.post(f"{URL}/{txn}/personal-gift"))
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(Donation.id)).all() == []
    unchanged(client, txn)


def test_repeat_gifts_skip_a_split(client, add_txn, checking, cats):  # noqa: F811
    paid = add_txn(checking, -4_000, description="FAKE FOOD BANK 0115")
    gift = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": paid["id"]}  # fmt: skip
    assert client.post("/api/local/donations", json=gift).status_code == 201
    txn = split(client, add_txn, checking, cats, amount=-4_000)
    client.patch(f"{URL}/{txn}", json={"description": "FAKE FOOD BANK 0215"})
    twin = add_txn(checking, -4_000, description="FAKE PAYMENT")["id"]
    client.patch(f"{URL}/{twin}", json={"description": "FAKE FOOD BANK 0215"})
    with Session(client.app.state.engine) as session:
        assert repeat_gifts(session, {txn, twin}).filed <= 1
        session.commit()
        assert session.scalar(select(Transaction.category_id).where(Transaction.id == txn)) is None
        assert session.scalar(select(Transaction.category_id).where(Transaction.id == twin))
        filed_to = session.scalars(select(Donation.transaction_id)).all()
        assert txn not in filed_to
        assert twin in filed_to


def test_a_stock_trade_is_refused_on_a_split(client, add_txn, make_account, cats):  # noqa: F811
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    txn = split(client, add_txn, brokerage, cats)
    lot = {"symbol": "FAKE", "acquired_on": "2026-01-15", "shares": "2",
           "cost_basis_cents": 10_000, "transaction_id": txn}  # fmt: skip
    refused(client.post("/api/local/stocks/lots", json=lot))
    unchanged(client, txn)


def test_a_paycheck_cannot_link_a_split_deposit(client, add_txn, checking, cats):  # noqa: F811
    txn = split(client, add_txn, checking, cats, amount=250_000, description="FAKECO PAYROLL")
    stub = {"pay_date": "2026-01-15", "employer": "FakeCo", "gross_cents": 300_000,
            "federal_tax_cents": 50_000, "net_cents": 250_000}  # fmt: skip
    made = client.post("/api/local/paychecks", json=stub | {"deposit_transaction_id": txn})
    refused(made)
    paycheck = client.post("/api/local/paychecks", json=stub).json()
    refused(client.post(f"/api/local/paychecks/{paycheck['id']}/deposit",
                        json={"transaction_id": txn}))  # fmt: skip
    waiting = client.get("/api/local/paychecks/deposits", params={"year": 2026}).json()
    assert txn not in [d["transaction_id"] for d in waiting]
    unchanged(client, txn)


def test_the_edit_route_still_refuses_a_category(client, add_txn, checking, cats):  # noqa: F811
    txn = split(client, add_txn, checking, cats)
    refused(client.patch(f"{URL}/{txn}", json={"category_id": cats["Groceries"]}))


TRADE = "FAKECO UNSOLICITED WE ARE ACTING AS PRINCIPAL COMMISSION FIELD IS A COMMISSION EQUIVALENT"
SWEEP = "FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL"
TRADES = "/api/local/stocks/bank-trades"
SWEEPS = "/api/local/stocks/sweeps"


def test_the_bank_trade_finder_skips_a_split(client, add_txn, make_account, cats):  # noqa: F811
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    txn = split(client, add_txn, brokerage, cats, description="BUY FAKE")
    client.patch(f"{URL}/{txn}", json={"description": TRADE})
    plain = add_txn(brokerage, -6_000, description=TRADE)
    assert client.post(f"{TRADES}/find").status_code == 200
    listed = client.get(TRADES).json()["items"]
    assert [t["transaction_id"] for t in listed] == [plain["id"]]
    unchanged(client, txn)


def test_a_split_sweep_is_not_free_and_cannot_be_linked(client, add_txn, make_account, cats):  # noqa: F811
    brokerage = make_account(name="Fake Brokerage", kind="brokerage")["id"]
    sweep = split(client, add_txn, brokerage, cats, amount=7_000, description=SWEEP)
    free = add_txn(brokerage, 5_000, description=SWEEP)
    trade = add_txn(brokerage, -7_000, description=TRADE)
    assert client.post(f"{TRADES}/find").status_code == 200
    (found,) = client.get(TRADES).json()["items"]
    assert found["transaction_id"] == trade["id"]
    assert found["sweep_transaction_id"] is None  # the split sweep was not taken
    lines = [s["transaction_id"] for s in client.get(SWEEPS).json()["unlinked"]]
    assert lines == [free["id"]]
    link = {"kind": "trade", "record_id": found["id"]}
    refused = client.post(f"{SWEEPS}/{sweep}/link", json=link)
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "not_free"
    unchanged(client, sweep)
