"""Bank CSV import (roadmap #6). Every file here is made up."""

import codecs
import datetime as dt
import logging

import pytest
from alembic import command
from sqlalchemy import inspect

from app.db import alembic_config, create_db_engine, run_migrations
from app.services import csv_import
from app.services.csv_import import clean_description, parse_amount, parse_date

CHECKING_CSV = (
    "Date,Description,Amount,Balance\r\n"
    '01/03/2026,FAKE GROCERY 123,"-$1,234.56",100.00\r\n'
    '01/04/2026,Fake Payroll,"$2,000.00",2100.00\r\n'
    "01/05/2026,Fake Coffee,(4.50),2095.50\r\n"
    "01/05/2026,Fake Coffee,(4.50),2091.00\r\n"
)


def url(account_id: int, action: str = "preview") -> str:
    base = f"/api/local/accounts/{account_id}/csv-import"
    return base if action == "commit" else f"{base}/{action}"


def send(client, account_id, body, action="preview", content_type="text/csv", **params):
    if isinstance(body, str):
        body = body.encode()
    headers = {"Content-Type": content_type}
    return client.post(url(account_id, action), content=body, params=params, headers=headers)


def ok(response) -> dict:
    assert response.status_code == 200, response.text
    return response.json()


def txns(client, account_id) -> list[dict]:
    items = client.get("/api/local/transactions", params={"account_id": account_id}).json()
    return sorted(items["items"], key=lambda t: t["id"])


@pytest.fixture
def checking(make_account) -> int:
    return make_account()["id"]


# --- parsing helpers -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12.34", 1234),
        ("-12.34", -1234),
        ("$1,234.56", 123456),
        ("-$1,234.56", -123456),
        ("$-5", -500),
        ("(4.50)", -450),
        ("($1,000.00)", -100000),
        ("12.00-", -1200),
        ("+7.1", 710),
        (" 1 000.00 ", 100000),
        ("1\xa0000.00", 100000),  # non-breaking space
        ("", None),
        ("  ", None),
        ("$", None),
    ],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    "text", ["12,34", "1,23,456.00", "1.005", "abc", "(-4.50)", "1e3", "--5", "12.3.4"]
)
def test_parse_amount_refuses_to_guess(text):
    with pytest.raises(ValueError):
        parse_amount(text)


@pytest.mark.parametrize(
    ("text", "fmt", "expected"),
    [
        ("2026-01-05", "YYYY-MM-DD", dt.date(2026, 1, 5)),
        ("1/5/2026", "MM/DD/YYYY", dt.date(2026, 1, 5)),
        ("01/05/26", "MM/DD/YY", dt.date(2026, 1, 5)),
        ("05/01/2026", "DD/MM/YYYY", dt.date(2026, 1, 5)),
        ("05.01.2026", "DD.MM.YYYY", dt.date(2026, 1, 5)),
        ("20260105", "YYYYMMDD", dt.date(2026, 1, 5)),
        ("Jan 5, 2026", "Mon D, YYYY", dt.date(2026, 1, 5)),
        ("5 Jan 2026", "D Mon YYYY", dt.date(2026, 1, 5)),
        ("01/05/2026 10:30:00", "MM/DD/YYYY", dt.date(2026, 1, 5)),
        ("2026-01-05T10:30:00", "YYYY-MM-DD", dt.date(2026, 1, 5)),
    ],
)
def test_parse_date(text, fmt, expected):
    assert parse_date(text, fmt) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('=HYPERLINK("x")', '\'=HYPERLINK("x")'),
        ("+1 FAKE", "'+1 FAKE"),
        ("-FAKE", "'-FAKE"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("  Fake\tShop\n  ", "Fake Shop"),
        ("\t=cmd", "'=cmd"),
        ("Fake Shop", "Fake Shop"),
    ],
)
def test_clean_description_neutralizes_formulas(text, expected):
    assert clean_description(text) == expected


# --- preview and import ----------------------------------------------------------------------


def test_preview_detects_columns_and_parses_bank_quirks(client, checking):
    body = codecs.BOM_UTF8 + CHECKING_CSV.encode()
    preview = ok(send(client, checking, body))
    assert preview["mapping"] == {
        "delimiter": ",",
        "header_rows": 1,
        "date_column": 0,
        "description_column": 1,
        "amount_column": 2,
        "debit_column": None,
        "credit_column": None,
        "date_format": "MM/DD/YYYY",
        "flip_sign": False,
    }
    assert preview["columns"] == ["Date", "Description", "Amount", "Balance"]  # BOM gone
    assert preview["used_saved_mapping"] is False
    assert (preview["total_rows"], preview["new_rows"], preview["invalid_rows"]) == (4, 4, 0)
    rows = preview["rows"]
    assert [r["amount_cents"] for r in rows] == [-123456, 200000, -450, -450]
    assert rows[0] == {
        "row_number": 2,
        "date": "2026-01-03",
        "description": "FAKE GROCERY 123",
        "amount_cents": -123456,
        "status": "new",
        "problem": None,
    }
    assert txns(client, checking) == []  # preview never saves anything


def test_import_then_reimport_overlapping_statement_skips_duplicates(client, checking):
    result = ok(send(client, checking, CHECKING_CSV, "commit"))
    assert result == {
        "imported": 4,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
        "mapping_saved": False,
    }
    imported = txns(client, checking)
    # Two identical coffees on the same day are both real purchases, so both are kept.
    assert [t["amount_cents"] for t in imported] == [-123456, 200000, -450, -450]
    assert {(t["source"], t["kind"], t["category_id"]) for t in imported} == {
        ("csv", "normal", None)
    }

    # The next statement overlaps on 01/05 (one coffee) and adds a third coffee and a new row.
    overlap = (
        "Date,Description,Amount\n"
        "01/05/2026,Fake Coffee,-4.50\n"
        "01/05/2026,  fake  COFFEE ,-4.50\n"  # same after tidying spaces and case
        "01/05/2026,Fake Coffee,-4.50\n"
        "01/06/2026,Fake Rent,-900.00\n"
    )
    preview = ok(send(client, checking, overlap))
    assert [r["status"] for r in preview["rows"]] == ["duplicate", "duplicate", "new", "new"]
    result = ok(send(client, checking, overlap, "commit"))
    assert (result["imported"], result["skipped_duplicates"]) == (2, 2)
    assert len(txns(client, checking)) == 6

    # Importing the same file a third time adds nothing.
    assert ok(send(client, checking, overlap, "commit"))["imported"] == 0
    account = client.get(f"/api/local/accounts/{checking}").json()
    assert account["balance_cents"] == -123456 + 200000 - 450 * 3 - 90000


def test_same_rows_on_another_account_are_not_duplicates(client, checking, make_account):
    savings = make_account(name="Fake Savings", kind="savings")["id"]
    ok(send(client, checking, CHECKING_CSV, "commit"))
    assert ok(send(client, savings, CHECKING_CSV, "commit"))["imported"] == 4


def test_separate_debit_and_credit_columns(client, checking):
    body = (
        "Posted Date,Payee,Debit Amount,Credit Amount\n"
        "2026-02-01,Fake Shop,12.00,\n"
        "2026-02-02,Fake Refund,,3.50\n"
        "2026-02-03,Fake Fee,-1.25,\n"  # some banks put a minus on debits too
        "2026-02-04,Fake Zero,0.00,8.00\n"
    )
    preview = ok(send(client, checking, body))
    mapping = preview["mapping"]
    assert (mapping["amount_column"], mapping["debit_column"], mapping["credit_column"]) == (
        None,
        2,
        3,
    )
    assert mapping["date_format"] == "YYYY-MM-DD"
    assert [r["amount_cents"] for r in preview["rows"]] == [-1200, 350, -125, 800]


def test_flip_sign_for_card_that_exports_charges_as_positive(client, make_account):
    """ARCHITECTURE "Signs and balances": card charges are negative, payments positive."""
    card = make_account(name="Fake Card", kind="credit_card")["id"]
    body = (
        "Transaction Date,Description,Amount\n"
        "03/01/2026,FAKE STORE,120.00\n"
        "03/02/2026,FAKE AIRLINE,250.00\n"
        "03/03/2026,FAKE STORE REFUND,-20.00\n"
    )
    result = ok(send(client, card, body, "commit", flip_sign=True, save_mapping=True))
    assert result["imported"] == 3
    assert [t["amount_cents"] for t in txns(client, card)] == [-12000, -25000, 2000]
    balance = client.get(f"/api/local/accounts/{card}").json()["balance_cents"]
    assert balance == -35000  # $350.00 owed

    # The saved mapping remembers the flip, so next time it's one click.
    preview = ok(send(client, card, body))
    assert preview["used_saved_mapping"] is True
    assert preview["mapping"]["flip_sign"] is True
    assert preview["duplicate_rows"] == 3


def test_saved_mapping_is_reused_and_can_be_forgotten(client, checking):
    # No header row, so the columns must be chosen by hand the first time.
    body = "Fake Shop One,5.00,15/01/2026\nFake Shop Two,-6.00,16/01/2026\n"
    choices = {
        "header_rows": 0,
        "date_column": 2,
        "description_column": 0,
        "amount_column": 1,
        "date_format": "DD/MM/YYYY",
    }
    result = ok(send(client, checking, body, "commit", save_mapping=True, **choices))
    assert (result["imported"], result["mapping_saved"]) == (2, True)

    preview = ok(send(client, checking, "Fake Shop Three,1.00,17/01/2026\n"))
    assert preview["used_saved_mapping"] is True
    assert preview["rows"][0]["date"] == "2026-01-17"
    assert preview["columns"] == ["Column 1", "Column 2", "Column 3"]

    assert client.delete(url(checking, "mapping")).status_code == 204
    assert ok(send(client, checking, body))["used_saved_mapping"] is False
    assert client.delete(url(checking, "mapping")).status_code == 204  # already gone: fine


def test_saved_mapping_that_does_not_fit_the_file_is_ignored(client, checking):
    wide = "Date,Ref,Other,Description,Amount\n2026-01-01,1,x,Fake,-1.00\n"
    ok(send(client, checking, wide, "commit", save_mapping=True))
    preview = ok(send(client, checking, CHECKING_CSV))  # only 4 columns: amount was column 4
    assert preview["used_saved_mapping"] is False
    assert preview["mapping"]["amount_column"] == 2


def test_header_after_preamble_lines(client, checking):
    body = (
        "Account Name: Fake Checking\n"
        "Statement period: fake\n"
        "\n"
        "Trans Date;Details;Withdrawals;Deposits\n"
        "05.01.2026;Fake Shop;1.234,00;\n"  # European decimal comma: refused, not guessed
        "06.01.2026;Fake Pay;;100.00\n"
    )
    preview = ok(send(client, checking, body))
    assert preview["mapping"]["delimiter"] == ";"
    assert preview["mapping"]["header_rows"] == 4
    assert preview["mapping"]["date_format"] == "DD.MM.YYYY"
    statuses = [(r["row_number"], r["status"]) for r in preview["rows"]]
    assert statuses == [(5, "invalid"), (6, "new")]
    assert (
        preview["rows"][0]["problem"] == "The money-out amount isn't a dollar amount we can read."
    )


def test_no_header_columns_are_guessed_from_the_cells(client, checking):
    body = "2026-01-05,FAKE SUPERMARKET PURCHASE,-12.00\n2026-01-06,FAKE PHARMACY,-3.00\n"
    mapping = ok(send(client, checking, body))["mapping"]
    assert (mapping["header_rows"], mapping["date_column"], mapping["amount_column"]) == (0, 0, 2)
    assert mapping["description_column"] == 1


def test_unrecognizable_file_asks_for_the_columns(client, checking):
    preview = ok(send(client, checking, "a,b\nc,d\n"))
    assert preview["mapping"] is None
    assert "choose" in preview["message"]
    assert preview["sample"] == [["a", "b"], ["c", "d"]]
    response = send(client, checking, "a,b\nc,d\n", "commit")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mapping_needed"


def test_day_first_dates_can_be_chosen(client, checking):
    body = "Date,Description,Amount\n03/02/2026,Fake,-1.00\n"
    assert ok(send(client, checking, body))["rows"][0]["date"] == "2026-03-02"  # US first
    preview = ok(send(client, checking, body, date_format="DD/MM/YYYY"))
    assert preview["rows"][0]["date"] == "2026-02-03"


@pytest.mark.parametrize(
    ("encoding", "prefix"),
    [("utf-16", b""), ("cp1252", b""), ("utf-8", codecs.BOM_UTF8)],
)
def test_file_encodings(client, checking, encoding, prefix):
    body = prefix + "Date,Description,Amount\n2026-01-05,Café Fake,-3.00\n".encode(encoding)
    preview = ok(send(client, checking, body))
    assert preview["rows"][0]["description"] == "Café Fake"


def test_formula_cells_are_neutralized_on_import(client, checking):
    body = 'Date,Description,Amount\n2026-01-05,"=HYPERLINK(""http://x"")",-3.00\n'
    ok(send(client, checking, body, "commit"))
    assert txns(client, checking)[0]["description"] == '\'=HYPERLINK("http://x")'


def test_bad_rows_block_the_import_unless_skipped(client, checking, caplog):
    body = (
        "Date,Description,Amount\n"
        "2026-01-05,Fake Good,-3.00\n"
        "not a date,SECRET-DESCRIPTION,-777.77\n"
        "2026-01-06,Fake Zero,0.00\n"
        "2026-01-07,,-1.00\n"
        "2026-01-08,Fake Short\n"
        "\n"  # blank lines are ignored, not errors
    )
    caplog.set_level(logging.DEBUG)
    response = send(client, checking, body, "commit")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_rows"
    assert "4 rows" in error["message"]
    assert "row 3, 4, 5, 6" in error["message"]
    assert "SECRET" not in response.text and "777" not in response.text
    assert txns(client, checking) == []

    problems = {r["row_number"]: r["problem"] for r in ok(send(client, checking, body))["rows"]}
    assert problems == {
        2: None,
        3: "The date isn't in the YYYY-MM-DD format.",
        4: "The amount is zero.",
        5: "The description is empty.",
        6: "This row has fewer columns than the others.",
    }

    result = ok(send(client, checking, body, "commit", skip_invalid_rows=True))
    assert (result["imported"], result["skipped_invalid"]) == (1, 4)
    # Nothing from the file reaches the logs.
    assert "SECRET" not in caplog.text and "777" not in caplog.text
    assert "Fake Good" not in caplog.text


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"amount_column": 2, "debit_column": 1}, "either one amount column"),
        ({"amount_column": 9}, "only has 3 columns"),
        ({"date_format": "MM/YYYY/DD"}, None),
        ({"surprise": 1}, None),
    ],
)
def test_bad_mapping_choices(client, checking, params, message):
    body = "Date,Description,Amount\n2026-01-05,Fake,-3.00\n"
    response = send(client, checking, body, **params)
    assert response.status_code == 422, response.text
    if message:
        assert message in response.json()["error"]["message"]


def test_unknown_account(client):
    response = send(client, 999, CHECKING_CSV)
    assert response.status_code == 404
    assert client.delete(url(999, "mapping")).status_code == 404


# --- upload limits ---------------------------------------------------------------------------


def test_file_too_large(client, checking, monkeypatch):
    monkeypatch.setattr(csv_import, "MAX_UPLOAD_BYTES", 100)
    response = send(client, checking, CHECKING_CSV * 2)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_too_many_rows(client, checking, monkeypatch):
    monkeypatch.setattr(csv_import, "MAX_ROWS", 2)
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
