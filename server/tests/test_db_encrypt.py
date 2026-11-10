"""Moving an existing plain database into SQLCipher (ADR-0014, requirement 5; roadmap 25l-3)."""

import logging
import sqlite3
from pathlib import Path

import pytest

from app import db_encrypt
from app.crypto import sqlcipher
from app.crypto.errors import DatabaseMoveError
from app.db import database_path
from app.db_encrypt import PENDING_MARKER, encrypt_existing_database, plain_backups
from app.main import create_app

pytestmark = pytest.mark.real_migrations

KEY = bytes(range(32))
SECRET = "Zephyr Coffee Roasters 4417"
HEADER = b"SQLite format 3\x00"


def make_plain(folder: Path, *, wal: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = database_path(folder)
    connection = sqlite3.connect(path)
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE note (body TEXT)")
    connection.execute("INSERT INTO note VALUES (?)", (SECRET,))
    connection.execute("PRAGMA user_version = 7")
    connection.commit()
    if wal:
        return path, connection
    connection.close()
    return path


def all_bytes(folder: Path) -> bytes:
    return b"".join(p.read_bytes() for p in sorted(folder.glob("budget.db*")) if p.is_file())


def test_a_plain_database_moves_with_its_rows_and_version(tmp_path):
    path = make_plain(tmp_path)
    assert encrypt_existing_database(path, KEY) is True
    data = all_bytes(tmp_path)
    assert not data.startswith(HEADER) and SECRET.encode() not in data
    with sqlcipher.connect(path, KEY) as connection:
        assert connection.execute("SELECT body FROM note").fetchall() == [(SECRET,)]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
    assert not (tmp_path / PENDING_MARKER).exists()
    assert not list(tmp_path.glob("*.encrypting"))


def test_nothing_changes_for_a_new_or_encrypted_database(tmp_path):
    path = database_path(tmp_path)
    tmp_path.mkdir(exist_ok=True)
    assert encrypt_existing_database(path, KEY) is False  # no file at all
    path.write_bytes(b"")
    assert encrypt_existing_database(path, KEY) is False  # empty new file
    path.unlink()
    plain = make_plain(tmp_path)
    encrypt_existing_database(plain, KEY)
    before = path.read_bytes()
    assert encrypt_existing_database(path, KEY) is False  # already encrypted
    assert path.read_bytes() == before


def test_rows_still_in_the_write_ahead_log_are_carried_over(tmp_path):
    live, connection = make_plain(tmp_path / "live", wal=True)
    assert (live.parent / "budget.db-wal").stat().st_size > 0
    folder = tmp_path / "crashed"  # what a crash leaves: the file and its log, no open process
    folder.mkdir()
    for item in live.parent.glob("budget.db*"):
        (folder / item.name).write_bytes(item.read_bytes())
    connection.close()
    path = folder / "budget.db"
    encrypt_existing_database(path, KEY)
    assert not list(folder.glob("budget.db-*"))  # plain -wal/-shm are gone
    with sqlcipher.connect(path, KEY) as opened:
        assert opened.execute("SELECT count(*) FROM note").fetchone()[0] == 1


def test_a_failed_check_leaves_the_plain_file_untouched(tmp_path, monkeypatch):
    path = make_plain(tmp_path)
    before = path.read_bytes()
    real_export = db_encrypt._export

    def lossy_export(plain, new, key):
        real_export(plain, new, key)
        with sqlcipher.connect(new, key) as copy:
            copy.execute("DELETE FROM note")
            copy.commit()

    monkeypatch.setattr(db_encrypt, "_export", lossy_export)
    with pytest.raises(DatabaseMoveError, match="safe and unchanged"):
        encrypt_existing_database(path, KEY)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.encrypting"))


def test_a_crash_after_the_export_resumes_from_the_marker(tmp_path, monkeypatch):
    path = make_plain(tmp_path)

    def crash(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr("app.db_encrypt._verify", crash)
    with pytest.raises(KeyboardInterrupt):
        encrypt_existing_database(path, KEY)
    assert (tmp_path / PENDING_MARKER).exists() and path.read_bytes().startswith(HEADER)
    monkeypatch.undo()
    assert encrypt_existing_database(path, KEY) is True
    assert not (tmp_path / PENDING_MARKER).exists()
    assert not path.read_bytes().startswith(HEADER)


def test_a_crash_after_the_swap_only_clears_the_marker(tmp_path):
    path = make_plain(tmp_path)
    encrypt_existing_database(path, KEY)
    (tmp_path / PENDING_MARKER).write_bytes(b"")
    assert encrypt_existing_database(path, KEY) is True
    assert not (tmp_path / PENDING_MARKER).exists()
    with sqlcipher.connect(path, KEY) as opened:
        assert opened.execute("SELECT count(*) FROM note").fetchone()[0] == 1


def test_older_plain_backups_are_flagged(tmp_path, caplog):
    path = make_plain(tmp_path)
    old = tmp_path / "budget.db.bak-0030"
    old.write_bytes(path.read_bytes())
    with caplog.at_level(logging.WARNING):
        encrypt_existing_database(path, KEY)
    assert "budget.db.bak-0030" in caplog.text and "NOT encrypted" in caplog.text
    assert plain_backups(path) == [old]


def test_the_app_moves_a_plain_database_at_start_and_its_upgrade_backup_is_encrypted(
    data_dir, monkeypatch
):
    from alembic import command

    from app.db_migrate import alembic_config

    engine = create_app().state.engine  # plain, then taken one revision back
    with engine.begin() as connection:
        config = alembic_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "0030")
    engine.dispose()
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    app = create_app()
    app.state.engine.dispose()
    data = all_bytes(data_dir)
    assert not data.startswith(HEADER) and b"CREATE TABLE" not in data
    backup = data_dir / "budget.db.bak-0030"
    assert backup.exists()
    assert not backup.read_bytes().startswith(HEADER)
    assert b"CREATE TABLE" not in backup.read_bytes()


def test_a_copy_that_still_has_the_database_open_stops_the_move(tmp_path):
    path, connection = make_plain(tmp_path, wal=True)
    try:
        with pytest.raises(DatabaseMoveError, match="safe and unchanged"):
            encrypt_existing_database(path, KEY)
    finally:
        connection.close()
    assert path.read_bytes().startswith(HEADER) and not list(tmp_path.glob("*.encrypting*"))
    with sqlite3.connect(path) as check:
        assert check.execute("SELECT count(*) FROM note").fetchone()[0] == 1
    check.close()
