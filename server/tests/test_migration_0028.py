"""Migration 0028 (encrypting organization, employer, institution, and merchant names)."""

import pytest
from alembic import command
from crypto_helpers import KEY, raw_rows
from sqlalchemy import text

from app.crypto import EncryptionError, FieldCipher
from app.db import alembic_config, create_db_engine

NAMES = {
    "donations": "organization",
    "paychecks": "employer",
    "accounts": "institution",
    "receipts": "merchant",
}


def _migrate(engine, target, direction="upgrade"):
    config = alembic_config()
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, direction)(config, target)


def _insert_plaintext_rows(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO accounts (id, name, kind, institution) VALUES "
                "(1, 'Everyday', 'checking', 'Fake Credit Union'), (2, 'Cash', 'cash', NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO paychecks (pay_date, employer, gross_cents, net_cents, account_id) "
                "VALUES ('2026-01-15', 'Fake Widgets Inc', 100, 90, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO receipts (date, merchant, total_cents) "
                "VALUES ('2026-01-01', 'Fake Pharmacy', 500)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO donations (date, organization, amount_cents, kind) "
                "VALUES ('2026-01-01', 'Fake Food Bank', 100, 'cash')"
            )
        )


def _plain(data_dir) -> dict[str, list]:
    return {
        table: [r[0] for r in raw_rows(data_dir, f"SELECT {col} FROM {table} ORDER BY id")]
        for table, col in NAMES.items()
    }


def test_migration_0028_encrypts_existing_names_and_downgrade_restores_them(tmp_path):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0027")
        _insert_plaintext_rows(engine)
        before = _plain(tmp_path)
        assert before["donations"] == ["Fake Food Bank"]

        _migrate(engine, "0028")
        after = _plain(tmp_path)
        for values in after.values():
            for value in values:
                assert value is None or (isinstance(value, bytes) and b"Fake" not in value)
        assert after["accounts"][1] is None  # an empty value stays empty
        assert all(v for t, v in after.items() if t != "accounts")
        # Links are untouched (no table rebuild firing ON DELETE SET NULL).
        assert raw_rows(tmp_path, "SELECT account_id FROM paychecks") == [(1,)]

        _migrate(engine, "0027", "downgrade")
        assert _plain(tmp_path) == before
    finally:
        engine.dispose()


def test_migration_0028_needs_the_key_when_there_is_data(tmp_path):
    engine = create_db_engine(tmp_path)  # no cipher
    try:
        _migrate(engine, "0027")
        _insert_plaintext_rows(engine)
        with pytest.raises(EncryptionError):
            _migrate(engine, "0028")
        assert raw_rows(tmp_path, "SELECT version_num FROM alembic_version") == [("0027",)]
        assert raw_rows(tmp_path, "SELECT institution FROM accounts WHERE id = 1") == [
            ("Fake Credit Union",)
        ]
    finally:
        engine.dispose()


def test_api_returns_the_names_and_the_file_holds_only_ciphertext(client, data_dir, make_account):
    account = make_account(institution="Fake Credit Union")
    paycheck = {
        "pay_date": "2026-01-15",
        "employer": "Fake Widgets Inc",
        "gross_cents": 1000,
        "net_cents": 1000,
    }
    gift = {
        "date": "2026-01-15",
        "organization": "Fake Food Bank",
        "kind": "cash",
        "amount_cents": 500,
    }
    receipt = {"date": "2026-01-15", "merchant": "Fake Pharmacy", "total_cents": 700}
    assert client.post("/api/local/paychecks", json=paycheck).status_code == 201
    assert client.post("/api/local/donations", json=gift).status_code == 201
    assert client.post("/api/local/receipts", json=receipt).status_code == 201

    assert client.get("/api/local/accounts").json()[0]["institution"] == "Fake Credit Union"
    assert account["institution"] == "Fake Credit Union"
    assert client.get("/api/local/paychecks").json()["items"][0]["employer"] == "Fake Widgets Inc"
    assert client.get("/api/local/donations").json()["items"][0]["organization"] == "Fake Food Bank"
    assert client.get("/api/local/receipts").json()["items"][0]["merchant"] == "Fake Pharmacy"

    client.app.state.engine.dispose()
    for table, column in NAMES.items():
        (value,) = raw_rows(data_dir, f"SELECT {column} FROM {table}")[0]
        assert isinstance(value, bytes) and b"Fake" not in value


def test_migration_0028_rerun_does_not_double_encrypt_or_fail(tmp_path):
    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0027")
        _insert_plaintext_rows(engine)
        _migrate(engine, "0028")
        once = _plain(tmp_path)
        with engine.begin() as conn:  # as if the version stamp had been lost
            config = alembic_config()
            config.attributes["connection"] = conn
            command.stamp(config, "0027")
        _migrate(engine, "0028")  # must neither fail nor encrypt twice
        assert _plain(tmp_path) == once
        _migrate(engine, "0027", "downgrade")
        assert _plain(tmp_path)["donations"] == ["Fake Food Bank"]
        with engine.begin() as conn:
            config = alembic_config()
            config.attributes["connection"] = conn
            command.stamp(config, "0028")
        _migrate(engine, "0027", "downgrade")  # already text: left alone
        assert _plain(tmp_path)["donations"] == ["Fake Food Bank"]
    finally:
        engine.dispose()


def test_upgrade_from_0027_writes_scrub_marker_and_flags_the_old_copy(tmp_path, monkeypatch):
    from app import db as db_module

    engine = create_db_engine(tmp_path, field_cipher=FieldCipher(KEY))
    try:
        _migrate(engine, "0027")
        _insert_plaintext_rows(engine)
        db_path = db_module.database_path(tmp_path)
        marker = db_module.scrub_marker_path(db_path)
        marker_seen = []
        real = db_module._vacuum_and_checkpoint

        def spy(eng):
            marker_seen.append(marker.is_file())
            return real(eng)

        monkeypatch.setattr(db_module, "_vacuum_and_checkpoint", spy)
        db_module.run_migrations(engine)
        assert marker_seen == [True]  # the clean-up ran because the marker was written
        assert not marker.exists()  # and finished
        backup = tmp_path / "budget.db.bak-0027"
        assert backup.is_file()
        assert db_module.unencrypted_backups(db_path) == [backup]
    finally:
        engine.dispose()
    assert b"Fake Food Bank" not in db_path.read_bytes()
