"""Bank CSV import: upload limits, who may upload, and the database."""

import pytest
from alembic import command
from csv_helpers import CHECKING_CSV, ok, send, txns
from sqlalchemy import inspect

from app.db import alembic_config, create_db_engine, run_migrations
from app.services.imports import csv_import, csv_parsing


def test_file_too_large(client, checking, monkeypatch):
    monkeypatch.setattr(csv_import, "MAX_UPLOAD_BYTES", 100)
    response = send(client, checking, CHECKING_CSV * 2)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_too_many_rows(client, checking, monkeypatch):
    monkeypatch.setattr(csv_parsing, "MAX_ROWS", 2)
    body = "Date,Description,Amount\n" + "2026-01-05,Fake,-1.00\n" * 30
    response = send(client, checking, body)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_many_rows"


@pytest.mark.parametrize(
    ("body", "content_type", "status", "code"),
    [
        (CHECKING_CSV, "application/json", 415, "not_a_csv"),
        (CHECKING_CSV, "image/png", 415, "not_a_csv"),
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00", "text/csv", 400, "not_a_csv"),
        (b"", "text/csv", 400, "empty_file"),
        (b"  \r\n", "text/csv", 400, "empty_file"),
    ],
)
def test_not_a_csv(client, checking, body, content_type, status, code):
    response = send(client, checking, body, content_type=content_type)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "content_type", ["application/vnd.ms-excel", "text/plain; charset=utf-8", "TEXT/CSV"]
)
def test_csv_content_types_browsers_send(client, checking, content_type):
    ok(send(client, checking, CHECKING_CSV, content_type=content_type))


def test_import_needs_a_page_on_this_computer(make_client, checking):
    """CSRF: another website can't post a file here (LocalAccessMiddleware's Origin check)."""
    stranger = make_client(headers={"Origin": "http://evil.example"})
    response = send(stranger, checking, CHECKING_CSV, "commit")
    assert response.status_code == 403


# --- database --------------------------------------------------------------------------------


def test_deleting_an_account_removes_its_saved_mapping(client, make_account):
    account = make_account(name="Fake Empty")["id"]
    body = "Date,Description,Amount\n2026-01-05,Fake,-3.00\n"
    assert ok(send(client, account, body, "commit", save_mapping=True))["imported"] == 1
    for txn in txns(client, account):
        assert client.delete(f"/api/local/transactions/{txn['id']}").status_code == 204
    assert client.delete(f"/api/local/accounts/{account}").status_code == 204
    # A new account can't inherit it, even if SQLite hands out the same ID again.
    again = make_account(name="Fake New")["id"]
    assert ok(send(client, again, body))["used_saved_mapping"] is False


def test_migration_0004_downgrade_and_upgrade(tmp_path):
    engine = create_db_engine(tmp_path)
    try:
        run_migrations(engine)
        config = alembic_config()
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0003")
        tables = inspect(engine).get_table_names()
        assert "csv_import_mappings" not in tables
        columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
        assert "import_fingerprint" not in columns
        run_migrations(engine)
        columns = {c["name"] for c in inspect(engine).get_columns("transactions")}
        assert "import_fingerprint" in columns
    finally:
        engine.dispose()
