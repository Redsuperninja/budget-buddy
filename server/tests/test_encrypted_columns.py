"""Encrypted database columns, end to end: models and raw SQLite contents."""

import datetime as dt

import pytest
from crypto_helpers import OTHER_KEY, raw_rows
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError

from app.crypto import DecryptionError, EncryptedString, EncryptionError, FieldCipher
from app.db import (
    SessionLocal,
    create_db_engine,
    database_path,
)
from app.main import create_app
from app.models import (
    Account,
    AccountKind,
    Base,
    Donation,
    DonationKind,
    Paycheck,
    Receipt,
    Transaction,
    TransactionSource,
)

ENCRYPTED = {
    ("accounts", "last4"),
    ("accounts", "notes"),
    ("transactions", "notes"),
    ("paychecks", "notes"),
    ("receipts", "image_path"),
    ("receipts", "notes"),
    ("donations", "notes"),
    ("devices", "sync_key"),
    ("pairing_sessions", "pair_sk"),
}


@pytest.fixture
def app(data_dir):
    app = create_app()
    yield app
    app.state.engine.dispose()


def test_encrypted_columns_are_exactly_the_planned_ones():
    found = set()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, EncryptedString):
                # The AAD label must match where the column really is.
                assert column.type.context == f"{table.name}.{column.name}"
                found.add((table.name, column.name))
    assert found == ENCRYPTED


def test_round_trip_and_raw_database_holds_no_plaintext(app, data_dir):
    with SessionLocal(bind=app.state.engine) as session:
        account = Account(
            name="Everyday", kind=AccountKind.CHECKING, last4="4821", notes="joint with Sam"
        )
        session.add(account)
        session.flush()
        txn = Transaction(
            account_id=account.id,
            date=dt.date(2026, 9, 1),
            amount_cents=-1299,
            description="Pharmacy",
            source=TransactionSource.MANUAL,
            notes="prescription refill",
        )
        session.add(txn)
        session.flush()
        session.add_all(
            [
                Paycheck(
                    pay_date=dt.date(2026, 9, 15),
                    employer="Acme",
                    gross_cents=100,
                    net_cents=90,
                    notes="bonus month",
                ),
                Receipt(
                    date=dt.date(2026, 9, 1),
                    merchant="Pharmacy",
                    total_cents=1299,
                    image_path="0123456789abcdef0123456789abcdef",
                    notes="for taxes",
                ),
                Donation(
                    date=dt.date(2026, 9, 2),
                    organization="Food Bank",
                    amount_cents=500,
                    kind=DonationKind.CASH,
                    notes="in memory of Grandma",
                ),
            ]
        )
        session.commit()

    with SessionLocal(bind=app.state.engine) as session:
        assert session.scalars(select(Account)).one().last4 == "4821"
        assert session.scalars(select(Account)).one().notes == "joint with Sam"
        assert session.scalars(select(Transaction)).one().notes == "prescription refill"
        assert session.scalars(select(Paycheck)).one().notes == "bonus month"
        receipt = session.scalars(select(Receipt)).one()
        assert receipt.image_path == "0123456789abcdef0123456789abcdef"
        assert receipt.notes == "for taxes"
        assert session.scalars(select(Donation)).one().notes == "in memory of Grandma"

    app.state.engine.dispose()  # flush everything out of the WAL file into budget.db
    raw = database_path(data_dir).read_bytes()
    for secret in (
        b"4821",
        b"joint with Sam",
        b"prescription",
        b"bonus month",
        b"0123456789abcdef",
        b"for taxes",
        b"Grandma",
    ):
        assert secret not in raw, secret
    last4, notes = raw_rows(data_dir, "SELECT last4, notes FROM accounts")[0]
    assert isinstance(last4, bytes) and last4[0] == 1
    assert isinstance(notes, bytes)
    # Not encrypted on purpose (needed for search and categorization), see ADR-0003.
    assert raw_rows(data_dir, "SELECT description FROM transactions") == [("Pharmacy",)]


def test_null_stays_null(app, data_dir):
    with SessionLocal(bind=app.state.engine) as session:
        session.add(Account(name="Cash", kind=AccountKind.CASH))
        session.commit()
    assert raw_rows(data_dir, "SELECT last4, notes FROM accounts") == [(None, None)]


def test_value_moved_to_another_column_fails(app):
    engine = app.state.engine
    with SessionLocal(bind=engine) as session:
        session.add(Account(name="A", kind=AccountKind.CHECKING, last4="1111", notes="n"))
        session.commit()
    with engine.begin() as conn:
        conn.execute(text("UPDATE accounts SET notes = last4"))
    with SessionLocal(bind=engine) as session, pytest.raises(DecryptionError):
        session.scalars(select(Account)).one()


def test_tampered_value_fails(app):
    engine = app.state.engine
    with SessionLocal(bind=engine) as session:
        session.add(Account(name="A", kind=AccountKind.CHECKING, last4="1111"))
        session.commit()
    with engine.begin() as conn:
        blob = bytearray(conn.execute(text("SELECT last4 FROM accounts")).scalar())
        blob[-1] ^= 0x01
        conn.execute(text("UPDATE accounts SET last4 = :b"), {"b": bytes(blob)})
    with SessionLocal(bind=engine) as session, pytest.raises(DecryptionError):
        session.scalars(select(Account)).one()


def test_wrong_key_cannot_read(app, data_dir):
    with SessionLocal(bind=app.state.engine) as session:
        session.add(Account(name="A", kind=AccountKind.CHECKING, last4="1111"))
        session.commit()
    other = create_db_engine(data_dir, field_cipher=FieldCipher(OTHER_KEY))
    try:
        with SessionLocal(bind=other) as session, pytest.raises(DecryptionError):
            session.scalars(select(Account)).one()
    finally:
        other.dispose()


def test_engine_without_key_refuses_encrypted_columns(app, data_dir):
    keyless = create_db_engine(data_dir)
    try:
        with SessionLocal(bind=keyless) as session:
            session.add(Account(name="A", kind=AccountKind.CHECKING, last4="1111"))
            # SQLAlchemy wraps errors raised while preparing a statement.
            with pytest.raises(StatementError, match="without its encryption key") as info:
                session.commit()
            assert isinstance(info.value.orig, EncryptionError)
    finally:
        keyless.dispose()


def test_app_restart_reads_existing_data(data_dir):
    first = create_app()
    with SessionLocal(bind=first.state.engine) as session:
        session.add(Account(name="A", kind=AccountKind.CHECKING, notes="still here"))
        session.commit()
    first.state.engine.dispose()
    second = create_app()
    try:
        with SessionLocal(bind=second.state.engine) as session:
            assert session.scalars(select(Account)).one().notes == "still here"
    finally:
        second.state.engine.dispose()


def test_value_swapped_between_rows_of_one_column_still_decrypts(app):
    """Documents the accepted limitation in ADR-0003 (security review L4).

    Values are bound to ``table.column``, not to their row, so swapping two rows' ciphertexts in
    the same column decrypts, with the values swapped. If this ever starts failing, row binding
    was added: update ADR-0003 and the ``fields.py`` docstring.
    """
    engine = app.state.engine
    with SessionLocal(bind=engine) as session:
        session.add_all(
            [
                Account(id=1, name="A", kind=AccountKind.CHECKING, last4="1111"),
                Account(id=2, name="B", kind=AccountKind.CHECKING, last4="2222"),
            ]
        )
        session.commit()
    with engine.begin() as conn:
        first, second = conn.execute(text("SELECT last4 FROM accounts ORDER BY id")).scalars()
        conn.execute(text("UPDATE accounts SET last4 = :v WHERE id = 1"), {"v": second})
        conn.execute(text("UPDATE accounts SET last4 = :v WHERE id = 2"), {"v": first})
    with SessionLocal(bind=engine) as session:
        rows = session.scalars(select(Account).order_by(Account.id)).all()
        assert [a.last4 for a in rows] == ["2222", "1111"]
