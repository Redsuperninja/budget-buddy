"""Bank CSV import (roadmap #6): preview and import. Every file here is made up."""

import codecs
import logging

import pytest
from csv_helpers import CHECKING_CSV, ok, send, txns, url


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
    """ledger.md "Signs and balances": card charges are negative, payments positive."""
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
