"""Whole-database encryption, step 1 (ADR-0014): the engine, the key and its safety rules."""

import logging
import traceback
from pathlib import Path

import pytest
from sqlalchemy import text

from app.config import Settings
from app.crypto import sqlcipher
from app.crypto.errors import CipherProviderError, UnencryptedDatabaseError, WrongKeyError
from app.crypto.keys import PURPOSE_DB_FIELDS, PURPOSE_DB_FILE, DerivedKeys, derive_key
from app.db import create_db_engine, database_path
from app.main import create_app

pytestmark = pytest.mark.real_migrations

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
MARKER = "Zephyr Coffee Roasters 4417"
SQLITE_HEADER = b"SQLite format 3\x00"


def all_bytes(folder: Path) -> bytes:
    return b"".join(p.read_bytes() for p in sorted(folder.glob("budget.db*")) if p.is_file())


def put_marker(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE note (body TEXT)"))
        connection.execute(text("INSERT INTO note VALUES (:body)"), {"body": MARKER})


def test_encrypted_file_has_no_plaintext_and_no_sqlite_header(tmp_path):
    engine = create_db_engine(tmp_path, database_key=KEY)
    put_marker(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT body FROM note")).scalar() == MARKER
        # Open: the main file and the write-ahead log are both encrypted.
        open_bytes = all_bytes(tmp_path)
    engine.dispose()
    for data in (open_bytes, all_bytes(tmp_path)):
        assert data
        assert MARKER.encode() not in data
        assert b"CREATE TABLE" not in data
        assert not data.startswith(SQLITE_HEADER)
        assert SQLITE_HEADER not in data


def test_without_a_key_the_file_stays_plain_sqlite(tmp_path):
    engine = create_db_engine(tmp_path)
    put_marker(engine)
    engine.dispose()
    assert database_path(tmp_path).read_bytes().startswith(SQLITE_HEADER)


def test_plain_sqlite_cannot_read_an_encrypted_file(tmp_path):
    import sqlite3

    engine = create_db_engine(tmp_path, database_key=KEY)
    put_marker(engine)
    engine.dispose()
    connection = sqlite3.connect(database_path(tmp_path))
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not a database"):
            connection.execute("SELECT * FROM sqlite_master").fetchall()
    finally:
        connection.close()


def test_the_right_key_reopens_the_file(tmp_path):
    first = create_db_engine(tmp_path, database_key=KEY)
    put_marker(first)
    first.dispose()
    second = create_db_engine(tmp_path, database_key=KEY)
    with second.connect() as connection:
        assert connection.execute(text("SELECT body FROM note")).scalar() == MARKER
    second.dispose()


def test_wrong_key_is_reported_as_a_wrong_key(tmp_path):
    engine = create_db_engine(tmp_path, database_key=KEY)
    put_marker(engine)
    engine.dispose()
    wrong = create_db_engine(tmp_path, database_key=OTHER_KEY)
    with pytest.raises(WrongKeyError, match="can't open Budget Buddy's database"):
        wrong.connect()
    wrong.dispose()


def test_a_plain_file_under_a_key_says_it_is_not_encrypted_yet(tmp_path):
    plain = create_db_engine(tmp_path)
    put_marker(plain)
    plain.dispose()
    before = database_path(tmp_path).read_bytes()
    keyed = create_db_engine(tmp_path, database_key=KEY)
    with pytest.raises(UnencryptedDatabaseError, match="BUDGET_BUDDY_DATABASE_ENCRYPTION") as err:
        keyed.connect()
    assert not isinstance(err.value, WrongKeyError)
    assert "recovery" not in str(err.value)
    keyed.dispose()
    assert database_path(tmp_path).read_bytes() == before  # untouched


def test_an_app_start_on_a_plain_database_with_the_setting_on_is_not_a_wrong_key(
    data_dir, monkeypatch
):
    create_app().state.engine.dispose()  # a plain database, as before this version
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    with pytest.raises(UnencryptedDatabaseError):
        create_app()


def test_the_openssl_check_runs_before_the_database_is_read(tmp_path, monkeypatch):
    statements = []
    real = sqlcipher.dbapi_module()

    class Spy(real.Cursor):
        def execute(self, sql, *args):
            statements.append(sql)
            return super().execute(sql, *args)

    class SpyConnection(real.Connection):
        def cursor(self, factory=Spy):
            return super().cursor(factory)

    original = real.connect
    monkeypatch.setattr(real, "connect", lambda *a, **k: original(*a, factory=SpyConnection, **k))
    create_db_engine(tmp_path, database_key=KEY).connect().close()
    assert statements.index("PRAGMA cipher_provider_version") < statements.index(
        "SELECT count(*) FROM sqlite_master"
    )


def test_an_old_openssl_is_refused_even_with_the_wrong_key(tmp_path, monkeypatch):
    engine = create_db_engine(tmp_path, database_key=KEY)
    put_marker(engine)
    engine.dispose()
    monkeypatch.setattr(sqlcipher, "MIN_PROVIDER_VERSION", (99, 0, 0))
    wrong = create_db_engine(tmp_path, database_key=OTHER_KEY)
    with pytest.raises(CipherProviderError):
        wrong.connect()
    wrong.dispose()


def test_a_busy_file_is_not_called_a_wrong_key():
    class Busy:
        def execute(self, sql):
            if sql.startswith("SELECT"):
                raise sqlcipher.dbapi_module().OperationalError("database is locked")

        def fetchone(self):
            return ("OpenSSL 3.6.0 1 Oct 2025",)

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Busy()

    with pytest.raises(sqlcipher.dbapi_module().OperationalError, match="locked"):
        sqlcipher.open_with_key(Connection(), KEY)


@pytest.mark.parametrize("bad", [b"", b"short", KEY + b"x", "a" * 32])
def test_a_key_of_the_wrong_size_is_refused(tmp_path, bad):
    engine = create_db_engine(tmp_path, database_key=bad)
    with pytest.raises(WrongKeyError):
        engine.connect()
    engine.dispose()


def test_the_hex_key_never_appears_in_errors_logs_or_the_url(tmp_path, caplog):
    hex_key = OTHER_KEY.hex()
    engine = create_db_engine(tmp_path, database_key=KEY)
    put_marker(engine)
    engine.dispose()
    wrong = create_db_engine(tmp_path, database_key=OTHER_KEY)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("sqlalchemy").setLevel(logging.DEBUG)
        try:
            wrong.connect()
        except WrongKeyError as exc:
            shown = "".join(traceback.format_exception(exc))
            assert hex_key not in shown
            assert hex_key not in repr(exc)
            assert exc.__cause__ is None and exc.__suppress_context__
    for url in (str(wrong.url), repr(wrong.url), wrong.url.render_as_string(hide_password=False)):
        assert hex_key not in url
    assert hex_key not in repr(wrong)
    assert hex_key not in caplog.text
    assert KEY.hex() not in caplog.text
    wrong.dispose()


def test_the_key_is_set_first_and_only_on_the_raw_connection(tmp_path, monkeypatch):
    statements = []
    real = sqlcipher.dbapi_module()

    class Spy(real.Cursor):
        def execute(self, sql, *args):
            statements.append(sql)
            return super().execute(sql, *args)

    class SpyConnection(real.Connection):
        def cursor(self, factory=Spy):
            return super().cursor(factory)

    original = real.connect
    monkeypatch.setattr(real, "connect", lambda *a, **k: original(*a, factory=SpyConnection, **k))
    engine = create_db_engine(tmp_path, database_key=KEY)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()
    assert statements[0].startswith("PRAGMA key")
    assert sum("PRAGMA key" in s for s in statements) == 1
    assert "PRAGMA cipher_log_level = NONE" in statements[:3]


def test_an_old_openssl_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlcipher, "MIN_PROVIDER_VERSION", (99, 0, 0))
    engine = create_db_engine(tmp_path, database_key=KEY)
    with pytest.raises(CipherProviderError, match="too old"):
        engine.connect()
    engine.dispose()


def test_the_bundled_openssl_meets_the_minimum(tmp_path):
    engine = create_db_engine(tmp_path, database_key=KEY)
    with engine.connect() as connection:
        reported = connection.exec_driver_sql("PRAGMA cipher_provider_version").scalar()
    engine.dispose()
    assert sqlcipher.provider_version(reported) >= sqlcipher.MIN_PROVIDER_VERSION


def test_provider_version_parsing():
    assert sqlcipher.provider_version("OpenSSL 3.6.0 1 Oct 2025") == (3, 6, 0)
    assert sqlcipher.provider_version("OpenSSL 3.0.13 30 Jan 2024") == (3, 0, 13)
    assert sqlcipher.provider_version("LibreSSL 4.0") is None
    assert sqlcipher.provider_version("") is None


def test_the_database_key_is_its_own_subkey():
    keys = DerivedKeys.from_master(KEY)
    assert keys.db_file == derive_key(KEY, "db-file") == derive_key(KEY, PURPOSE_DB_FILE)
    assert len({keys.db_file, keys.db_fields, keys.files, keys.backup}) == 4
    assert derive_key(KEY, PURPOSE_DB_FIELDS) == keys.db_fields  # existing labels unchanged
    assert keys.db_file.hex() not in repr(keys)


def test_the_setting_is_off_by_default(data_dir):
    assert Settings().database_encryption is False
    app = create_app()
    app.state.engine.dispose()
    assert database_path(data_dir).read_bytes().startswith(SQLITE_HEADER)


def test_a_new_data_folder_is_fully_encrypted_when_the_setting_is_on(data_dir, monkeypatch):
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    app = create_app()
    with app.state.engine.connect() as connection:
        tables = connection.exec_driver_sql(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).scalar()
    app.state.engine.dispose()
    assert tables > 10
    data = all_bytes(data_dir)
    assert not data.startswith(SQLITE_HEADER)
    assert b"CREATE TABLE" not in data
    assert b"transactions" not in data


def test_a_backup_is_refused_up_front_while_encryption_is_on(data_dir, monkeypatch, capsys):
    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    app = create_app()
    app.state.engine.dispose()
    folder = data_dir.parent / "backups"
    folder.mkdir()
    from app.cli_backup import make_backup

    lines = []
    assert make_backup(Settings(), folder, output=lines.append) == 1
    assert "database encryption is turned on" in lines[0]
    assert not list(folder.iterdir()) and not list(data_dir.glob(".backup-*"))


def test_the_dashboard_backup_is_refused_with_a_clear_message(data_dir, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("BUDGET_BUDDY_DATABASE_ENCRYPTION", "1")
    app = create_app()
    client = TestClient(
        app,
        base_url="http://127.0.0.1:8765",
        client=("127.0.0.1", 50000),
        headers={"Origin": "http://127.0.0.1:8765", "X-CSRF-Token": app.state.csrf_token},
    )
    response = client.get("/api/local/backup/file")
    app.state.engine.dispose()
    assert response.status_code == 409
    assert "database encryption is turned on" in response.text
    assert not list(data_dir.glob(".backup-*"))
