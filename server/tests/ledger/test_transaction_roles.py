"""The shared "what is this transaction used as" conditions (services/ledger/transaction_roles.py).
Fake data only."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_bank_trades import TRADE_LINE

from app.models import BankTrade, Dividend, Transaction
from app.services.ledger import transaction_roles as roles

EVERY_ROLE = [
    roles.paycheck_deposits(),
    roles.donations(),
    roles.stock_trades(),
    roles.bank_trades(),
    roles.bank_trades(include_dismissed=True),
    roles.bank_trade_sweeps(),
    roles.dividends(),
    roles.dividends(include_dismissed=True),
    roles.dividend_sweeps(),
    *roles.cash_inside_account(),
    *roles.dividends_kept_inside(),
]


def test_every_role_works_in_one_query(client, add_txn, checking):
    """SQLite can't nest one UNION in another: all roles together must still run."""
    plain = add_txn(checking, -1_000, description="FAKE GROCER")
    paid = add_txn(checking, -4_000, description="FAKE FOOD BANK")
    gift = {"date": "2026-01-15", "organization": "Fake Food Bank", "kind": "cash",
            "amount_cents": 4_000, "transaction_id": paid["id"]}  # fmt: skip
    assert client.post("/api/local/donations", json=gift).status_code == 201

    with Session(client.app.state.engine) as session:
        left = session.scalars(select(Transaction.id).where(*roles.none_of(*EVERY_ROLE)))
        assert set(left) == {plain["id"]}


def test_dismissing_frees_the_sweep(client, make_account, add_txn):
    """The roles count every linked sweep as shown: only true while dismissing frees it."""
    ira = make_account(name="Fake IRA", kind="retirement")["id"]
    add_txn(ira, 130, date="2026-09-08", description="FAKECO CASH DIV")
    add_txn(ira, -130, date="2026-09-08", description="FAKE DEPOSIT SWEEP")
    add_txn(ira, -50_000, date="2026-10-01", description=TRADE_LINE)
    add_txn(ira, 50_000, date="2026-10-02", description="FAKE DEPOSIT SWEEP INTRA-DAY WITHDRWAL")
    [dividend] = client.get("/api/local/dividends/2026").json()["dividends"]
    [trade] = client.get("/api/local/stocks/bank-trades").json()["items"]
    assert dividend["sweep_transaction_id"] and trade["sweep_transaction_id"]

    assert client.post(f"/api/local/dividends/{dividend['id']}/dismiss").status_code == 204
    assert client.post(f"/api/local/stocks/bank-trades/{trade['id']}/dismiss").status_code == 204
    with Session(client.app.state.engine) as session:
        for model in (Dividend, BankTrade):
            assert session.scalars(select(model.sweep_transaction_id)).all() == [None]
