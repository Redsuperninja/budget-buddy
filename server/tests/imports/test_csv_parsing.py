"""Reading bank CSV cells: amounts, dates, descriptions."""

import datetime as dt

import pytest

from app.services.imports.csv_parsing import clean_description, parse_amount, parse_date


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
