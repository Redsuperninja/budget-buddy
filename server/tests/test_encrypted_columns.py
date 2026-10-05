"""Encrypted database columns, end to end: models, raw SQLite contents, migration 0003."""

import datetime as dt
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError

from app.crypto import DecryptionError, EncryptedString, EncryptionError, FieldCipher
from app.crypto.fields import alembic_compare_type
from app.db import (
    SessionLocal,
    alembic_config,
    create_db_engine,
    database_path,
    run_migrations,
    unencrypted_backups,
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

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))

ENCRYPTED = {
    ("accounts", "last4"),
    ("accounts", "notes"),
    ("transactions", "notes"),
    ("paychecks", "notes"),
    ("receipts", "image_path"),
    ("receipts", "notes"),
    ("donations", "notes"),
}


def _raw(data_dir, sql):
    conn = sqlite3.connect(database_path(data_dir))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


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
    last4, notes = _raw(data_dir, "SELECT last4, notes FROM accounts")[0]
    assert isinstance(last4, bytes) and last4[0] == 1
    assert isinstance(notes, bytes)
    # Not encrypted on purpose (needed for search and categorization), see ADR-0003.
    assert _raw(data_dir, "SELECT description FROM transactions") == [("Pharmacy",)]


def test_null_stays_null(app, data_dir):
    with SessionLocal(bind=app.state.engine) as session:
        session.add(Account(name="Cash", kind=AccountKind.CASH))
        session.commit()
    assert _raw(data_dir, "SELECT last4, notes FROM accounts") == [(None, None)]


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


# --- migration 0003 ---------------------------------------------------------------------------


def _migrate(engine, target, direction="upgrade"):
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, direction)(config, target)


def _insert_plaintext_rows(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO accounts (id, name, kind, last4, notes) "
                "VALUES (1, 'Everyday', 'checking', '4821', 'joint'), "
                "(2, 'Cash', 'cash', NULL, NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions (account_id, date, amount_cents, description, source, "
                "notes) VALUES (1, '2026-01-01', -500, 'Coffee', 'manual', 'with Alex')"
            )
        )
        # A transfer pair (rows 2 and 3) linking to each other, to check links survive.
        conn.execute(
            text(
                "INSERT INTO transactions (id, account_id, date, amount_cents, description, "
                "source, transfer_pair_id) VALUES (2, 1, '2026-01-02', -100, 'Out', 'manual', 3), "
                "(3, 1, '2026-01-02', 100, 'In', 'manual', 2)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO paychecks (pay_date, employer, gross_cents, net_cents, notes, "
                "account_id) VALUES ('2026-01-15', 'Acme', 100, 90, 'raise', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO receipts (date, merchant, total_cents, image_path, notes, "
                "transaction_id) VALUES ('2026-01-01', 'Cafe', 500, 'abc.jpg', 'lunch', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO donations (date, organization, amount_cents, kind, notes) "
                "VALUES ('2026-01-01', 'Library', 100, 'cash', 'book sale')"
            )
        )


def test_migration_0003_encrypts_existing_plaintext_and_downgrade_restores_it(tmp_path):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0002")
        _insert_plaintext_rows(engine)

        # Through 0003 to the newest migration: the models below match the newest tables, and
        # later migrations don't touch these columns.
        _migrate(engine, "head")
        raw_last4 = _raw(tmp_path, "SELECT last4 FROM accounts WHERE id = 1")[0][0]
        assert isinstance(raw_last4, bytes) and b"4821" not in raw_last4
        assert _raw(tmp_path, "SELECT last4, notes FROM accounts WHERE id = 2") == [(None, None)]
        with SessionLocal(bind=engine) as session:
            account = session.get(Account, 1)
            assert (account.last4, account.notes) == ("4821", "joint")
            assert session.get(Transaction, 1).notes == "with Alex"
            assert session.scalars(select(Paycheck)).one().notes == "raise"
            receipt = session.scalars(select(Receipt)).one()
            assert (receipt.image_path, receipt.notes) == ("abc.jpg", "lunch")
            assert session.scalars(select(Donation)).one().notes == "book sale"
            # Plain columns and amounts are untouched.
            assert session.get(Transaction, 1).amount_cents == -500
        # Links between rows are untouched (no table rebuild firing ON DELETE SET NULL).
        assert _raw(tmp_path, "SELECT id, transfer_pair_id FROM transactions ORDER BY id") == [
            (1, None),
            (2, 3),
            (3, 2),
        ]
        assert _raw(tmp_path, "SELECT transaction_id FROM receipts") == [(1,)]
        assert _raw(tmp_path, "SELECT account_id FROM paychecks") == [(1,)]

        _migrate(engine, "0002", "downgrade")
        assert _raw(tmp_path, "SELECT last4, notes FROM accounts ORDER BY id") == [
            ("4821", "joint"),
            (None, None),
        ]
        assert _raw(tmp_path, "SELECT notes FROM transactions WHERE id = 1") == [("with Alex",)]
        assert _raw(tmp_path, "SELECT image_path, notes FROM receipts") == [("abc.jpg", "lunch")]
        assert _raw(tmp_path, "SELECT notes FROM donations") == [("book sale",)]
        assert _raw(tmp_path, "SELECT notes FROM paychecks") == [("raise",)]
    finally:
        engine.dispose()


def test_migration_0003_needs_the_key_when_there_is_data(tmp_path):
    engine = create_db_engine(tmp_path)  # no cipher
    try:
        _migrate(engine, "0002")
        _insert_plaintext_rows(engine)
        with pytest.raises(EncryptionError):
            _migrate(engine, "0003")
        # Nothing was half-done.
        assert _raw(tmp_path, "SELECT version_num FROM alembic_version") == [("0002",)]
        assert _raw(tmp_path, "SELECT last4 FROM accounts WHERE id = 1") == [("4821",)]
    finally:
        engine.dispose()


def test_startup_upgrade_scrubs_plaintext_and_flags_old_backups(tmp_path, caplog):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0002")
        _insert_plaintext_rows(engine)
        run_migrations(engine)  # the normal start-up path: backup, upgrade, clean up
    finally:
        engine.dispose()

    raw = database_path(tmp_path).read_bytes()
    for secret in (b"4821", b"with Alex", b"book sale", b"lunch"):
        assert secret not in raw, secret  # not even in free pages, thanks to VACUUM
    backup = tmp_path / "budget.db.bak-0002"
    assert backup.is_file()  # backups are never deleted automatically...
    assert unencrypted_backups(database_path(tmp_path)) == [backup]
    assert "NOT encrypted" in caplog.text and backup.name in caplog.text  # ...but flagged


def test_models_match_migrations_so_autogenerate_proposes_nothing(tmp_path):
    """Autogenerate must not propose changing encrypted columns' types (that rebuilds tables)."""
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        run_migrations(engine)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"compare_type": alembic_compare_type})
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


# --- plain-text clean-up is retried until it works (security review M1) ----------------------


def _seed_many_plaintext_notes(engine, count=2000):
    with engine.begin() as conn:
        for i in range(count):
            conn.execute(
                text(
                    "INSERT INTO transactions (account_id, date, amount_cents, description, "
                    "source, notes) VALUES (1, '2026-01-01', -1, 'x', 'manual', :note)"
                ),
                {"note": f"SECRETNOTE-{i:05d} " + "y" * 60},
            )


def _plaintext_notes_on_disk(data_dir):
    import re

    blob = database_path(data_dir).read_bytes()
    wal = data_dir / "budget.db-wal"
    if wal.exists():
        blob += wal.read_bytes()
    return len(re.findall(rb"SECRETNOTE-\d{5}", blob))


def test_interrupted_cleanup_is_retried_on_next_start(tmp_path, monkeypatch):
    from app import db as db_module

    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0002")
        _insert_plaintext_rows(engine)
        _seed_many_plaintext_notes(engine)

        def power_cut(_engine):
            raise KeyboardInterrupt("power cut after migration 0003 committed")

        monkeypatch.setattr(db_module, "_vacuum_and_checkpoint", power_cut)
        with pytest.raises(KeyboardInterrupt):
            run_migrations(engine)
        marker = db_module.scrub_marker_path(database_path(tmp_path))
        assert marker.is_file()  # written before the migration ran
        head = ScriptDirectory.from_config(alembic_config()).get_current_head()
        assert _raw(tmp_path, "SELECT version_num FROM alembic_version") == [(head,)]

        monkeypatch.undo()
        run_migrations(engine)  # next start: already at head, but the marker says "clean up"
        assert not marker.exists()
    finally:
        engine.dispose()
    assert _plaintext_notes_on_disk(tmp_path) == 0


def test_cleanup_keeps_marker_when_checkpoint_is_busy(tmp_path, monkeypatch, caplog):
    from app import db as db_module

    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0002")
        _insert_plaintext_rows(engine)
        marker = db_module.scrub_marker_path(database_path(tmp_path))

        monkeypatch.setattr(db_module, "_vacuum_and_checkpoint", lambda _engine: False)
        run_migrations(engine)
        assert marker.is_file()
        assert "try again the next time it starts" in caplog.text

        def locked(_engine):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(db_module, "_vacuum_and_checkpoint", locked)
        run_migrations(engine)
        assert marker.is_file()

        monkeypatch.undo()
        run_migrations(engine)
        assert not marker.exists()
    finally:
        engine.dispose()


def test_cleanup_reports_failure_while_another_reader_holds_the_log(tmp_path, monkeypatch):
    """A reader on an old snapshot stops the TRUNCATE checkpoint; that must not count as done."""
    from app import db as db_module

    monkeypatch.setattr(db_module, "BUSY_TIMEOUT_MS", 0)  # don't wait 5 seconds for the reader
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        run_migrations(engine)
        assert db_module._vacuum_and_checkpoint(engine) is True
        reader = sqlite3.connect(database_path(tmp_path))
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT count(*) FROM categories").fetchone()  # holds a snapshot
            assert db_module._vacuum_and_checkpoint(engine) is False
        finally:
            reader.close()
        assert db_module._vacuum_and_checkpoint(engine) is True
    finally:
        engine.dispose()


def test_new_database_needs_no_cleanup(tmp_path):
    from app import db as db_module

    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        run_migrations(engine)
        assert not db_module.scrub_marker_path(database_path(tmp_path)).exists()
    finally:
        engine.dispose()


def test_secure_delete_is_on(tmp_path):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA secure_delete").scalar() == 1
    finally:
        engine.dispose()


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
