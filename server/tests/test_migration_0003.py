"""Migration 0003 (encrypting existing plain-text columns) and the plain-text clean-up."""

import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from crypto_helpers import KEY, raw_rows
from sqlalchemy import select, text

from app.crypto import EncryptionError, FieldCipher
from app.crypto.fields import alembic_compare_type
from app.db import (
    SessionLocal,
    alembic_config,
    create_db_engine,
    database_path,
    run_migrations,
    unencrypted_backups,
)
from app.models import (
    Account,
    Base,
    Donation,
    Paycheck,
    Receipt,
    Transaction,
)


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
        raw_last4 = raw_rows(tmp_path, "SELECT last4 FROM accounts WHERE id = 1")[0][0]
        assert isinstance(raw_last4, bytes) and b"4821" not in raw_last4
        assert raw_rows(tmp_path, "SELECT last4, notes FROM accounts WHERE id = 2") == [
            (None, None)
        ]
        with SessionLocal(bind=engine) as session:
            account = session.get(Account, 1)
            assert (account.last4, account.notes) == ("4821", "joint")
            assert session.get(Transaction, 1).notes == "with Alex"
            assert session.scalar(select(Paycheck.notes)) == "raise"  # 0003: no 0004 columns yet
            receipt = session.scalars(select(Receipt)).one()
            assert (receipt.image_path, receipt.notes) == ("abc.jpg", "lunch")
            assert session.scalars(select(Donation)).one().notes == "book sale"
            # Plain columns and amounts are untouched.
            assert session.get(Transaction, 1).amount_cents == -500
        # Links between rows are untouched (no table rebuild firing ON DELETE SET NULL).
        assert raw_rows(tmp_path, "SELECT id, transfer_pair_id FROM transactions ORDER BY id") == [
            (1, None),
            (2, 3),
            (3, 2),
        ]
        assert raw_rows(tmp_path, "SELECT transaction_id FROM receipts") == [(1,)]
        assert raw_rows(tmp_path, "SELECT account_id FROM paychecks") == [(1,)]

        _migrate(engine, "0002", "downgrade")
        assert raw_rows(tmp_path, "SELECT last4, notes FROM accounts ORDER BY id") == [
            ("4821", "joint"),
            (None, None),
        ]
        notes = raw_rows(tmp_path, "SELECT notes FROM transactions WHERE id = 1")
        assert notes == [("with Alex",)]
        assert raw_rows(tmp_path, "SELECT image_path, notes FROM receipts") == [
            ("abc.jpg", "lunch")
        ]
        assert raw_rows(tmp_path, "SELECT notes FROM donations") == [("book sale",)]
        assert raw_rows(tmp_path, "SELECT notes FROM paychecks") == [("raise",)]
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
        assert raw_rows(tmp_path, "SELECT version_num FROM alembic_version") == [("0002",)]
        assert raw_rows(tmp_path, "SELECT last4 FROM accounts WHERE id = 1") == [("4821",)]
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
        assert raw_rows(tmp_path, "SELECT version_num FROM alembic_version") == [(head,)]

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
