import datetime as dt
import os
import stat
import sys
from typing import Annotated

import pytest
from fastapi import Depends
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal, create_db_engine, database_path, get_session, run_migrations
from app.main import create_app
from app.models import (
    Account,
    AccountKind,
    Base,
    Category,
    CategoryGroup,
    Deduction,
    DeductionKind,
    Device,
    Donation,
    DonationKind,
    Paycheck,
    Receipt,
    StockLot,
    StockSale,
    StockSaleOrder,
    Transaction,
    TransactionKind,
    TransactionSource,
)

EXPECTED_TABLES = {
    "accounts",
    "budget_plan",
    "categories",
    "category_rules",
    "transactions",
    "csv_import_mappings",
    "paychecks",
    "receipts",
    "donations",
    "stock_lots",
    "stock_sales",
    "stock_sale_orders",
    "deductions",
    "devices",
    "pairing_sessions",
    "pairing_nonces",
    "seen_nonces",
}


@pytest.fixture
def engine(data_dir):
    app = create_app()
    yield app.state.engine
    app.state.engine.dispose()


@pytest.fixture
def session(engine):
    with SessionLocal(bind=engine) as session:
        yield session


def test_startup_creates_database_with_all_tables(data_dir, engine):
    assert database_path(data_dir).is_file()
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables


def test_models_match_migrations(engine):
    """Every model table is created by the migrations (catches a forgotten migration)."""
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            db_columns = {c["name"] for c in inspect(conn).get_columns(table.name)}
            assert db_columns == set(table.columns.keys()), table.name


def test_migrations_are_idempotent(data_dir, engine):
    run_migrations(engine)  # second run on the same database is a no-op
    create_app()  # and so is starting the app again
    with SessionLocal(bind=engine) as session:
        assert session.scalar(select(func.count()).select_from(Category)) == 18


def test_default_categories_seeded(session):
    rows = session.execute(select(Category.name, Category.group)).all()
    by_group: dict[CategoryGroup, set[str]] = {}
    for name, group in rows:
        by_group.setdefault(group, set()).add(name)
    assert by_group == {
        CategoryGroup.NEEDS: {
            "Rent/Mortgage",
            "Utilities",
            "Groceries",
            "Transportation",
            "Insurance",
            "Healthcare",
        },
        CategoryGroup.WANTS: {"Dining Out", "Entertainment", "Shopping", "Subscriptions", "Travel"},
        CategoryGroup.SAVINGS: {"Emergency Fund", "Retirement", "Investments"},
        CategoryGroup.INCOME: {"Paycheck", "Interest", "Other Income"},
        CategoryGroup.TRANSFER: {"Transfer"},
    }
    assert all(c.budget_cents == 0 for c in session.scalars(select(Category)))


def test_sqlite_pragmas(engine):
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_database_file_is_private_on_posix(data_dir, engine):
    assert stat.S_IMODE(database_path(data_dir).stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_existing_database_file_is_tightened_on_posix(tmp_path):
    path = database_path(tmp_path)
    path.touch()
    os.chmod(path, 0o644)
    create_db_engine(tmp_path).dispose()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_existing_wal_sidecars_are_tightened_on_posix(tmp_path):
    path = database_path(tmp_path)
    path.touch()
    sidecars = [tmp_path / "budget.db-wal", tmp_path / "budget.db-shm"]
    for sidecar in sidecars:
        sidecar.touch()
        os.chmod(sidecar, 0o644)
    create_db_engine(tmp_path).dispose()
    for sidecar in sidecars:
        assert stat.S_IMODE(sidecar.stat().st_mode) == 0o600, sidecar.name


@pytest.mark.parametrize(
    "folder",
    [
        "with%20percent",
        pytest.param(
            "with?question",
            marks=pytest.mark.skipif(sys.platform == "win32", reason="? not allowed on Windows"),
        ),
    ],
)
def test_data_folder_with_url_special_characters(tmp_path, folder):
    data_dir = tmp_path / folder
    data_dir.mkdir()
    engine = create_db_engine(data_dir)
    try:
        run_migrations(engine)
        assert engine.url.database == str(database_path(data_dir))
        assert "categories" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
    assert database_path(data_dir).is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == [folder]  # nothing created elsewhere


def test_round_trip_every_table(session):
    groceries = session.scalars(select(Category).where(Category.name == "Groceries")).one()
    checking = Account(name="Everyday", kind=AccountKind.CHECKING, institution="Local CU")
    brokerage = Account(name="Investing", kind=AccountKind.BROKERAGE)
    session.add_all([checking, brokerage])
    session.flush()

    txn = Transaction(
        account_id=checking.id,
        date=dt.date(2026, 9, 30),
        amount_cents=-4321,
        description="Grocery store",
        category_id=groceries.id,
        source=TransactionSource.MANUAL,
    )
    session.add(txn)
    session.flush()
    receipt = Receipt(
        date=dt.date(2026, 9, 30),
        merchant="Grocery store",
        total_cents=4321,
        category_id=groceries.id,
        transaction_id=txn.id,
    )
    session.add(receipt)
    session.flush()
    lot = StockLot(
        account_id=brokerage.id,
        symbol="VTI",
        shares_micro=1_500_000,
        acquired_on=dt.date(2024, 1, 2),
        cost_basis_cents=35012,
    )
    order = StockSaleOrder(
        account_id=brokerage.id,
        symbol="VTI",
        sold_on=dt.date(2026, 3, 1),
        shares_micro=500_000,
        proceeds_cents=14000,
    )
    session.add_all([lot, order])
    session.flush()
    session.add_all(
        [
            Paycheck(
                pay_date=dt.date(2026, 9, 15),
                employer="Acme",
                account_id=checking.id,
                gross_cents=250000,
                federal_tax_cents=25000,
                social_security_cents=15500,
                medicare_cents=3625,
                net_cents=205875,
            ),
            Donation(
                date=dt.date(2026, 5, 1),
                organization="Food Bank",
                amount_cents=5000,
                kind=DonationKind.CASH,
                receipt_id=receipt.id,
            ),
            StockSale(
                order_id=order.id,
                lot_id=lot.id,
                sold_on=dt.date(2026, 3, 1),
                shares_micro=500_000,
                proceeds_cents=14000,
            ),
            Deduction(
                tax_year=2026, kind=DeductionKind.MEDICAL, amount_cents=12000, receipt_id=receipt.id
            ),
            Device(name="My phone", token_hash="ab" * 32),
        ]
    )
    session.commit()
    session.expire_all()

    got_txn = session.get(Transaction, txn.id)
    assert got_txn.date == dt.date(2026, 9, 30)
    assert got_txn.amount_cents == -4321
    assert got_txn.source is TransactionSource.MANUAL
    assert got_txn.created_at is not None and got_txn.updated_at is not None
    assert session.get(Account, checking.id).kind is AccountKind.CHECKING
    assert session.get(Receipt, receipt.id).tax_deductible is False
    paycheck = session.scalars(select(Paycheck)).one()
    assert (paycheck.gross_cents, paycheck.state_tax_cents, paycheck.net_cents) == (
        250000,
        0,
        205875,
    )
    assert session.scalars(select(Donation)).one().kind is DonationKind.CASH
    assert session.scalars(select(StockSale)).one().lot_id == lot.id
    assert session.scalars(select(Deduction)).one().kind is DeductionKind.MEDICAL
    device = session.scalars(select(Device)).one()
    assert device.revoked is False and device.paired_at is not None


def test_foreign_keys_are_enforced(session):
    session.add(
        Transaction(
            account_id=9999,
            date=dt.date(2026, 1, 1),
            amount_cents=100,
            description="No such account",
            source=TransactionSource.CSV,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_category_unlinks_transactions(session):
    account = Account(name="Everyday", kind=AccountKind.CHECKING)
    category = Category(name="Pets", group=CategoryGroup.WANTS)
    session.add_all([account, category])
    session.flush()
    txn = Transaction(
        account_id=account.id,
        date=dt.date(2026, 1, 1),
        amount_cents=-100,
        description="Vet",
        category_id=category.id,
        source=TransactionSource.MANUAL,
    )
    session.add(txn)
    session.commit()
    session.delete(category)
    session.commit()
    session.expire_all()
    assert session.get(Transaction, txn.id).category_id is None


def test_invalid_enum_value_rejected_by_database(engine):
    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(text("INSERT INTO accounts (name, kind) VALUES ('X', 'crypto')"))


def test_get_session_dependency(client):
    @client.app.get("/_test/categories")
    def count_categories(session: Annotated[Session, Depends(get_session)]) -> dict[str, int]:
        return {"count": len(session.scalars(select(Category)).all())}

    assert client.get("/_test/categories").json() == {"count": 18}


def _account(session, kind=AccountKind.CHECKING):
    account = Account(name="Acct", kind=kind)
    session.add(account)
    session.flush()
    return account


def test_all_account_kinds_accepted(session):
    for kind in AccountKind:
        _account(session, kind)
    session.commit()
    assert {a.kind for a in session.scalars(select(Account))} == set(AccountKind)


def test_transfer_pair_round_trip_and_unlink(session):
    checking = _account(session)
    savings = _account(session, AccountKind.SAVINGS)
    out = Transaction(
        account_id=checking.id,
        date=dt.date(2026, 2, 1),
        amount_cents=-10000,
        description="To savings",
        source=TransactionSource.MANUAL,
        kind=TransactionKind.TRANSFER,
    )
    session.add(out)
    session.flush()
    back = Transaction(
        account_id=savings.id,
        date=dt.date(2026, 2, 1),
        amount_cents=10000,
        description="From checking",
        source=TransactionSource.MANUAL,
        kind=TransactionKind.TRANSFER,
        transfer_pair_id=out.id,
    )
    session.add(back)
    session.flush()
    out.transfer_pair_id = back.id
    session.commit()
    session.expire_all()
    assert session.get(Transaction, out.id).transfer_pair_id == back.id
    assert session.get(Transaction, back.id).kind is TransactionKind.TRANSFER

    session.delete(session.get(Transaction, back.id))
    session.commit()
    session.expire_all()
    assert session.get(Transaction, out.id).transfer_pair_id is None


def test_transaction_kind_defaults_to_normal(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts (name, kind) VALUES ('A', 'checking')"))
        conn.execute(
            text(
                "INSERT INTO transactions (account_id, date, amount_cents, description, source) "
                "VALUES (1, '2026-01-01', -5, 'x', 'manual')"
            )
        )
        assert conn.execute(text("SELECT kind FROM transactions")).scalar() == "normal"
    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(text("UPDATE transactions SET kind = 'gift'"))


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO stock_lots (symbol, shares_micro, acquired_on, cost_basis_cents) "
        "VALUES ('VTI', 0, '2026-01-01', 100)",
        "INSERT INTO stock_lots (symbol, shares_micro, acquired_on, cost_basis_cents) "
        "VALUES ('VTI', 1, '2026-01-01', -1)",
        "INSERT INTO paychecks (pay_date, employer, gross_cents, net_cents) "
        "VALUES ('2026-01-01', 'Acme', -1, 0)",
        "INSERT INTO paychecks (pay_date, employer, gross_cents, net_cents, medicare_cents) "
        "VALUES ('2026-01-01', 'Acme', 100, 90, -10)",
        "INSERT INTO paychecks (pay_date, employer, gross_cents, net_cents) "
        "VALUES ('2026-01-01', 'Acme', 100, -1)",
        "INSERT INTO donations (date, organization, amount_cents, kind) "
        "VALUES ('2026-01-01', 'Org', -1, 'cash')",
        "INSERT INTO deductions (tax_year, kind, amount_cents) VALUES (2026, 'medical', -1)",
        "INSERT INTO deductions (tax_year, kind, amount_cents) VALUES (1999, 'medical', 1)",
        "INSERT INTO deductions (tax_year, kind, amount_cents) VALUES (2101, 'medical', 1)",
    ],
)
def test_check_constraints(engine, sql):
    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(text(sql))


def test_stock_sale_shares_must_be_positive(session):
    lot = StockLot(
        symbol="VTI", shares_micro=1, acquired_on=dt.date(2026, 1, 1), cost_basis_cents=1
    )
    order = StockSaleOrder(
        symbol="VTI", sold_on=dt.date(2026, 2, 1), shares_micro=1, proceeds_cents=0
    )
    session.add_all([lot, order])
    session.flush()
    session.add(
        StockSale(
            order_id=order.id,
            lot_id=lot.id,
            sold_on=dt.date(2026, 2, 1),
            shares_micro=0,
            proceeds_cents=0,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_transactions_stay_signed(session):
    account = _account(session)
    session.add(
        Transaction(
            account_id=account.id,
            date=dt.date(2026, 1, 1),
            amount_cents=-123,
            description="Coffee",
            source=TransactionSource.MANUAL,
        )
    )
    session.commit()
    assert session.scalars(select(Transaction.amount_cents)).one() == -123
