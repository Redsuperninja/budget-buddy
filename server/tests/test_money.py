from decimal import Decimal

import pytest

from app.money import cents_to_display, dollars_to_cents


@pytest.mark.parametrize(
    ("value", "cents"),
    [
        ("0", 0),
        ("12", 1200),
        ("12.3", 1230),
        ("12.34", 1234),
        (" 12.34 ", 1234),
        ("-5.50", -550),
        ("0.01", 1),
        ("0.10", 10),
        ("19.99", 1999),
        ("+7.00", 700),
        (".50", 50),
        ("-.5", -50),
        ("12.", 1200),
        ("+3.", 300),
        ("1.500", 150),
        ("2.0000000000", 200),
        ("-0.00", 0),
        ("999999999.99", 99999999999),
        ("99999999999.99", 9999999999999),
        (Decimal("1E+2"), 10000),
        (Decimal("1.500"), 150),
        (Decimal("0.07"), 7),
        (Decimal("-1234.5"), -123450),
    ],
)
def test_dollars_to_cents(value, cents):
    result = dollars_to_cents(value)
    assert result == cents
    assert type(result) is int


@pytest.mark.parametrize("value", ["1.234", "0.001", "1.005", "1.0050", Decimal("0.005")])
def test_dollars_to_cents_rejects_fractions_of_a_cent(value):
    with pytest.raises(ValueError, match="fractions of a cent"):
        dollars_to_cents(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "$5",
        "1,000.00",
        "NaN",
        "Infinity",
        "-inf",
        "1E+2",
        "1e2",
        "1_000",
        ".",
        "-.",
        "+.",
        "..5",
        "5..",
        "--5",
        "١٢",  # Arabic-Indic digits
        "１２",  # full-width digits
        "1 000",
        Decimal("NaN"),
        Decimal("-Infinity"),
    ],
)
def test_dollars_to_cents_rejects_non_numbers(value):
    with pytest.raises(ValueError):
        dollars_to_cents(value)


@pytest.mark.parametrize(
    "value",
    [
        "100000000000.00",
        "-100000000000",
        "9" * 40,
        "1" + "0" * 5000,
        Decimal("1E+100000"),
        Decimal("-1E+12"),
    ],
)
def test_dollars_to_cents_rejects_huge_amounts(value):
    with pytest.raises(ValueError, match="too large"):
        dollars_to_cents(value)


def test_dollars_to_cents_long_fraction_is_value_error():
    with pytest.raises(ValueError):
        dollars_to_cents("0." + "0" * 100 + "1")
    assert dollars_to_cents("3." + "0" * 100) == 300


@pytest.mark.parametrize("value", [1.1, 0.1, 5, True, None])
def test_dollars_to_cents_rejects_floats_and_other_types(value):
    with pytest.raises(TypeError):
        dollars_to_cents(value)


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "$0.00"),
        (1, "$0.01"),
        (99, "$0.99"),
        (100, "$1.00"),
        (123456, "$1,234.56"),
        (100000000, "$1,000,000.00"),
        (-1, "-$0.01"),
        (-123456, "-$1,234.56"),
    ],
)
def test_cents_to_display(cents, text):
    assert cents_to_display(cents) == text


@pytest.mark.parametrize("value", [1.5, Decimal("1"), "100", True])
def test_cents_to_display_rejects_non_int(value):
    with pytest.raises(TypeError):
        cents_to_display(value)


def test_round_trip():
    for text in ("0.00", "0.01", "-0.99", "1234.56", "-1000000.00"):
        cents = dollars_to_cents(text)
        shown = cents_to_display(cents).replace("$", "").replace(",", "")
        assert dollars_to_cents(shown) == cents
