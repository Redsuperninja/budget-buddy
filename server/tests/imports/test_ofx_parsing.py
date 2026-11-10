import datetime as dt

import pytest

from app.services.imports import ofx_parsing as ofx
from tests.imports.ofx_helpers import card_xml, checking, sgml, transaction


def test_sgml_checking_statement():
    result = ofx.parse_ofx(sgml(checking()))
    (statement,) = result.statements
    assert (statement.kind, statement.last4) == ("CHECKING", "6789")
    assert statement.balance_cents == 123456 and statement.balance_date == dt.date(2026, 1, 10)
    first, second = statement.transactions
    assert (first.fitid, first.posted, first.cents, first.description) == (
        "FAKE001",
        dt.date(2026, 1, 5),
        -1250,
        "FAKE GROCERY",
    )
    assert second.cents == 200000 and result.problems == []


def test_xml_credit_card_statement_unescapes_and_keeps_last4_only():
    result = ofx.parse_ofx(card_xml().encode())
    (statement,) = result.statements
    assert (statement.kind, statement.last4) == ("CREDITCARD", "2222")
    assert statement.transactions[0].description == "FAKE & SONS"
    assert "4111" not in repr(result)


def test_name_and_memo_are_joined_and_cleaned():
    body = checking([transaction(name="FAKE =SHOP", memo="note\x07 here")])
    (item,) = ofx.parse_ofx(sgml(body)).statements[0].transactions
    assert item.description == "FAKE =SHOP - note here"
    assert (
        ofx.parse_ofx(sgml(checking([transaction(name="=CMD()")])))
        .statements[0]
        .transactions[0]
        .description
        == "'=CMD()"
    )


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12.5", 1250),
        ("-0.05", -5),
        ("+7", 700),
        (".5", 50),
        ("1000", 100000),
        ("-12.3400", -1234),
        ("5.", 500),
    ],
)
def test_amounts_are_exact(text, cents):
    assert ofx.parse_amount(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1,234.50", "12,34", "1.005", "--1", "1e3", "$5", "."])
def test_amounts_never_guessed(text):
    with pytest.raises(ValueError):
        ofx.parse_amount(text)


def test_dates():
    assert ofx.parse_date("20260105") == dt.date(2026, 1, 5)
    assert ofx.parse_date("20260105235959.123[-5:EST]") == dt.date(2026, 1, 5)
    with pytest.raises(ValueError):
        ofx.parse_date("20261305")


def test_bad_transactions_are_left_out_and_numbered():
    body = checking(
        [
            transaction("A", "oops"),
            transaction("B"),
            transaction("B", "-1.00"),
            transaction("", "1.00"),
            transaction("D", date="x"),
        ]
    )
    result = ofx.parse_ofx(sgml(body))
    assert [t.fitid for t in result.statements[0].transactions] == ["B"]
    assert [p.split(" was")[0] for p in result.problems] == [
        "Transaction 1",
        "Transaction 3",
        "Transaction 4",
        "Transaction 5",
    ]
    assert all("oops" not in p for p in result.problems)


@pytest.mark.parametrize(
    "data",
    [b"", b"hello", b"<html><body>no</body></html>", b"<OFX></OFX>"],
)
def test_not_a_bank_file(data):
    with pytest.raises(ofx.OfxError):
        ofx.parse_ofx(data)


def test_only_us_dollars():
    with pytest.raises(ofx.OfxError, match="US dollar"):
        ofx.parse_ofx(sgml(checking(cur="EUR")))


def test_limits():
    with pytest.raises(ofx.OfxError, match="too big"):
        ofx.parse_ofx(b"x" * (ofx.MAX_BYTES + 1))
    many = [transaction(f"F{i}") for i in range(ofx.MAX_TRANSACTIONS + 1)]
    with pytest.raises(ofx.OfxError, match="10,000"):
        ofx.parse_ofx(sgml(checking(many)))


def test_entities_and_doctype_are_never_expanded():
    evil = '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>' + checking(
        [transaction(name="&e; &#65;")]
    )
    (item,) = ofx.parse_ofx(sgml(evil)).statements[0].transactions
    assert item.description == "&e; &#65;"


def test_windows_1252_text():
    body = checking([transaction(name="CAFÉ")])
    assert ofx.parse_ofx(sgml(body)).statements[0].transactions[0].description == "CAFÉ"


def test_bad_balance_is_reported_not_fatal():
    result = ofx.parse_ofx(sgml(checking(balance="n/a")))
    assert result.statements[0].balance_cents is None and "balance" in result.problems[0]


def test_floods_are_stopped_early():
    with pytest.raises(ofx.OfxError, match="complicated"):
        ofx.parse_ofx(b"<OFX>" + b"<a>" * (ofx.MAX_TAGS + 1))
    with pytest.raises(ofx.OfxError, match="50 accounts"):
        ofx.parse_ofx(b"<OFX>" + b"<STMTRS>" * (ofx.MAX_STATEMENTS + 1))
    bad = checking([transaction(f"F{i}", "x") for i in range(300)])
    result = ofx.parse_ofx(sgml(bad))
    assert len(result.problems) == ofx.MAX_PROBLEMS + 1
    assert result.problems[-1].startswith("There were more")


def test_account_fields_are_cleaned():
    body = checking(acct="12‮=1+").replace("CHECKING", "X" * 500)
    (statement,) = ofx.parse_ofx(body.encode("utf-8")).statements
    assert statement.last4 == "121" and statement.kind == ""
    assert ofx.parse_ofx(sgml(checking())).statements[0].kind == "CHECKING"


def test_only_plain_ascii_digits():
    for text in ("١٢.5", "１２"):
        with pytest.raises(ValueError):
            ofx.parse_amount(text)
    with pytest.raises(ValueError):
        ofx.parse_date("٢٠٢٦٠١٠٥")


def test_huge_amounts_are_problems_not_crashes():
    with pytest.raises(ValueError):
        ofx.parse_amount("9" * 30)
    assert ofx.parse_amount("9" * 14) == int("9" * 14) * 100
    result = ofx.parse_ofx(sgml(checking([transaction("A", "9" * 30)])))
    assert result.statements[0].transactions == [] and "Transaction 1" in result.problems[0]


def test_ids_with_hidden_characters_are_refused():
    body = checking([transaction("A‮B"), transaction("C​D"), transaction("OK1")])
    result = ofx.parse_ofx(body.encode("utf-8"))
    assert [t.fitid for t in result.statements[0].transactions] == ["OK1"]
    assert len(result.problems) == 2
