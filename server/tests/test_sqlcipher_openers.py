"""Whole-database encryption, step 2 (ADR-0014, M2/M3): every plain-sqlite3 opener takes the key."""

import sqlite3

import pytest
from sqlalchemy import text

from app.crypto import database_has_rows, sqlcipher
from app.crypto.errors import (
    DatabaseBusyError,
    DatabaseCorruptError,
    UnencryptedDatabaseError,
    WrongKeyError,
)
from app.crypto.fields import FieldCipher
from app.crypto.key_check import encrypted_samples, key_opens_database
from app.crypto.keys import PURPOSE_DB_FIELDS, PURPOSE_DB_FILE, derive_key
from app.db import (
    copy_database,
    create_db_engine,
    database_path,
    database_revision,
    open_read_only,
)

pytestmark = pytest.mark.real_migrations

MASTER = bytes(range(32))
OTHER_MASTER = bytes(range(1, 33))
KEY = derive_key(MASTER, PURPOSE_DB_FILE)
OTHER_KEY = derive_key(OTHER_MASTER, PURPOSE_DB_FILE)
MARKER = "Zephyr Coffee Roasters 4417"
SQLITE_HEADER = b"SQLite format 3\x00"


def make_database(folder, *, key=KEY, revision="0030", rows=True):
    engine = create_db_engine(folder, database_key=key)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num TEXT)"))
        connection.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})
        connection.execute(text("CREATE TABLE note (body TEXT)"))
        if rows:
            connection.execute(text("INSERT INTO note VALUES (:b)"), {"b": MARKER})
    return engine


def test_open_read_only_reads_with_the_key(tmp_path):
    make_database(tmp_path).dispose()
    with open_read_only(database_path(tmp_path), KEY) as connection:
        assert connection.execute("SELECT body FROM note").fetchone()[0] == MARKER


def test_open_read_only_cannot_write(tmp_path):
    make_database(tmp_path).dispose()
    with open_read_only(database_path(tmp_path), KEY) as connection:
        with pytest.raises(Exception, match="readonly"):
            connection.execute("INSERT INTO note VALUES ('x')")


def test_open_read_only_with_the_wrong_key_is_a_wrong_key(tmp_path):
    make_database(tmp_path).dispose()
    with pytest.raises(WrongKeyError):
        with open_read_only(database_path(tmp_path), OTHER_KEY):
            pass


def make_plain_database(folder):
    engine = create_db_engine(folder)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
    engine.dispose()


def test_open_read_only_on_a_plain_file_says_not_encrypted_yet(tmp_path):
    make_plain_database(tmp_path)
    with pytest.raises(UnencryptedDatabaseError):
        with open_read_only(database_path(tmp_path), KEY):
            pass


def test_database_revision_with_the_key(tmp_path):
    make_database(tmp_path).dispose()
    assert database_revision(database_path(tmp_path), KEY) == "0030"


def test_database_revision_is_none_only_when_the_table_is_missing(tmp_path):
    engine = create_db_engine(tmp_path, database_key=KEY)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
    engine.dispose()
    assert database_revision(database_path(tmp_path), KEY) is None


def test_database_revision_with_the_wrong_key_is_not_no_revision(tmp_path):
    make_database(tmp_path).dispose()
    with pytest.raises(WrongKeyError):
        database_revision(database_path(tmp_path), OTHER_KEY)


def test_database_revision_of_a_plain_garbage_file_is_not_no_revision(tmp_path):
    path = tmp_path / "x.db"
    path.write_bytes(b"not a database " * 100)
    with pytest.raises(sqlite3.DatabaseError):
        database_revision(path)


def test_database_has_rows_with_the_key(tmp_path):
    make_database(tmp_path).dispose()
    assert database_has_rows(tmp_path, database_key=KEY) is True
    assert database_has_rows(tmp_path, ignore=frozenset({"note"}), database_key=KEY) is False


def test_database_has_rows_does_not_guess_with_the_wrong_key(tmp_path):
    make_database(tmp_path).dispose()
    with pytest.raises(WrongKeyError):
        database_has_rows(tmp_path, database_key=OTHER_KEY)


def test_database_has_rows_without_a_key_still_counts_an_encrypted_file_as_data(tmp_path):
    make_database(tmp_path, rows=False).dispose()
    assert database_has_rows(tmp_path) is True  # unreadable: never treated as empty


def test_database_has_rows_reports_a_damaged_file_not_has_rows(tmp_path):
    make_database(tmp_path).dispose()
    path = database_path(tmp_path)
    data = bytearray(path.read_bytes())
    for offset in range(4096 * 2, len(data), 97):  # keep page 1 so the key still opens it
        data[offset] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises((DatabaseCorruptError, WrongKeyError)):
        database_has_rows(tmp_path, database_key=KEY)


def test_a_locked_file_is_busy_not_a_wrong_key(tmp_path):
    make_database(tmp_path).dispose()
    holder = sqlcipher.connect(database_path(tmp_path), KEY)
    try:
        holder.execute("PRAGMA locking_mode = EXCLUSIVE")
        holder.execute("BEGIN EXCLUSIVE")
        with pytest.raises(DatabaseBusyError):
            with open_read_only(database_path(tmp_path), KEY):
                pass
    finally:
        holder.close()


def test_key_check_samples_encrypted_values_with_the_key(tmp_path):
    cipher = FieldCipher(derive_key(MASTER, PURPOSE_DB_FIELDS))
    engine = create_db_engine(tmp_path, database_key=KEY)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, last4 BLOB)"))
        connection.execute(
            text("INSERT INTO accounts (last4) VALUES (:v)"),
            {"v": cipher.encrypt("1234", "accounts.last4")},
        )
    engine.dispose()
    samples = encrypted_samples(tmp_path, KEY)  # tables the file lacks are skipped
    assert [context for _, context in samples] == ["accounts.last4"]
    with pytest.raises(WrongKeyError):
        encrypted_samples(tmp_path, OTHER_KEY)


def test_opening_with_the_database_key_is_the_key_check(tmp_path):
    make_database(tmp_path).dispose()
    assert key_opens_database(tmp_path, MASTER, database_encryption=True) is True
    assert key_opens_database(tmp_path, OTHER_MASTER, database_encryption=True) is False


def test_the_key_check_has_nothing_to_try_on_a_new_folder(tmp_path):
    assert key_opens_database(tmp_path, MASTER, database_encryption=True) is None


def test_the_key_check_on_a_plain_file_says_not_encrypted_yet(tmp_path):
    make_plain_database(tmp_path)
    with pytest.raises(UnencryptedDatabaseError):
        key_opens_database(tmp_path, MASTER, database_encryption=True)


def test_copy_database_writes_an_encrypted_copy(tmp_path):
    engine = make_database(tmp_path)
    destination = tmp_path / "budget.db.bak-0030"
    copy_database(engine, destination, KEY)
    engine.dispose()
    data = destination.read_bytes()
    assert data and not data.startswith(SQLITE_HEADER)
    assert MARKER.encode() not in data
    with open_read_only(destination, KEY) as connection:
        assert connection.execute("SELECT body FROM note").fetchone()[0] == MARKER
    with pytest.raises(WrongKeyError):
        with open_read_only(destination, OTHER_KEY):
            pass


def test_copy_database_without_a_key_is_still_plain(tmp_path):
    engine = create_db_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
    destination = tmp_path / "copy.db"
    copy_database(engine, destination)
    engine.dispose()
    assert destination.read_bytes().startswith(SQLITE_HEADER)


def test_a_failing_open_never_shows_the_key(tmp_path):
    make_database(tmp_path).dispose()
    with pytest.raises(WrongKeyError) as err:
        database_revision(database_path(tmp_path), OTHER_KEY)
    assert OTHER_KEY.hex() not in str(err.value)
    assert OTHER_KEY.hex() not in repr(err.value.__cause__)
