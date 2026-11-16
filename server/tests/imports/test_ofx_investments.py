import datetime as dt

import pytest

from app.services.imports import ofx_parsing as ofx
from tests.imports.ofx_helpers import checking, sgml
from tests.imports.ofx_invest_helpers import TRADES, both, brokerage, brokerage_xml


def read(body: str):
    return ofx.parse_ofx(sgml(body))


def test_sgml_brokerage_happy_path():
    result = read(brokerage())
    assert result.statements == [] and result.problems == []
    (b,) = result.brokerages
    assert (b.last4, b.as_of) == ("4321", dt.date(2026, 1, 10))
    stock, fund = b.holdings
    assert (stock.ticker, stock.kind, stock.units_micro, stock.unit_price_micro) == (
        "FKCO",
        "stock",
        10_500_000,
        25_123_400,
    )
    assert (stock.value_cents, stock.as_of) == (26380, dt.date(2026, 1, 10))
    assert stock.name == "FAKE CORP =COMMON"
    assert (fund.ticker, fund.units_micro, fund.unit_price_micro) == (
        "FKIDX",
        3_123_456,
        100_000_000,
    )
    buy, sell = b.trades
    assert (buy.fitid, buy.side, buy.kind, buy.ticker) == ("B1", "buy", "stock", "FKCO")
    assert (buy.units_micro, buy.commission_cents, buy.fees_cents, buy.total_cents) == (
        10_000_000,
        100,
        25,
        -25625,
    )
    assert buy.trade_date == dt.date(2026, 1, 2) and buy.description == "Bought =FAKE"
    assert (sell.side, sell.kind, sell.units_micro, sell.total_cents) == (
        "sell",
        "fund",
        -1_500_000,
        15018,
    )
    assert sell.commission_cents == 0 and sell.description == "FAKE INDEX FUND"
    div, interest = b.income
    assert (div.kind, div.ticker, div.total_cents, div.paid) == (
        "DIV",
        "FKCO",
        420,
        dt.date(2026, 1, 6),
    )
    assert (interest.kind, interest.ticker, interest.total_cents) == ("INTEREST", "", 5)
    (sweep,) = b.cash
    assert (sweep.fitid, sweep.cents, sweep.posted, sweep.description) == (
        "C1",
        50000,
        dt.date(2026, 1, 8),
        "FAKE SWEEP",
    )
    assert b.problems == [] and "987654321" not in repr(result)


def test_xml_brokerage_and_no_floats():
    (b,) = ofx.parse_ofx(brokerage_xml()).brokerages
    (trade,) = b.trades
    assert (trade.ticker, trade.description, trade.units_micro, trade.total_cents) == (
        "FKCO",
        "FAKE & CO",
        2_000_000,
        -2000,
    )
    assert b.holdings[0].value_cents == 2000
    for item in (trade, b.holdings[0]):
        assert not any(isinstance(v, float) for v in vars(item).values())


def test_bank_and_brokerage_in_one_file():
    result = ofx.parse_ofx(both())
    (bank,) = result.statements
    (b,) = result.brokerages
    assert bank.last4 == "6789" and [t.fitid for t in bank.transactions] == ["FAKE001", "FAKE002"]
    assert bank.balance_cents == 123456
    assert len(b.trades) == 2 and [c.fitid for c in b.cash] == ["C1"]  # the sweep isn't a bank line
    assert result.problems == []


def test_missing_security_info_leaves_lines_out_not_crash():
    result = read(brokerage(seclist=""))
    (b,) = result.brokerages
    assert b.holdings == [] and b.trades == []
    assert [i.fitid for i in b.income] == ["I2"]  # income that names no security still reads
    assert [c.fitid for c in b.cash] == ["C1"]
    assert any("Holding 1 was left out" in p and "no ticker" in p for p in result.problems)
    assert any("Investment line 1 was left out" in p for p in result.problems)
    assert "111111111" not in " ".join(result.problems)


@pytest.mark.parametrize(
    ("old", "new", "word"),
    [
        ("<UNITS>10<", "<UNITS>1,0<", "number of units"),
        ("<UNITS>10<", "<UNITS>1.0000001<", "number of units"),
        ("<TOTAL>-256.25", "<TOTAL>-256.255", "total"),
        ("<COMMISSION>1.00", "<COMMISSION>one", "commission"),
        ("<DTTRADE>20260102120000", "<DTTRADE>soon", "trade date"),
        ("<FITID>B1", "<FITID>", "transaction ID"),
        ("<FITID>S1", "<FITID>B1", "same transaction ID"),
        ("<INCOMETYPE>DIV", "<INCOMETYPE>GIFT", "kind of income"),
        ("<MKTVAL>263.80", "<MKTVAL>lots", "market value"),
        ("<UNITPRICE>25.1234", "<UNITPRICE>1e3", "unit price"),
        ("<BUYTYPE>BUY", "<BUYTYPE>BUYTOCOVER", "short sale"),
        ("<POSTYPE>LONG<UNITS>10.5", "<POSTYPE>SHORT<UNITS>10.5", "short position"),
    ],
)
def test_bad_values_are_left_out_with_a_plain_note(old, new, word):
    body = brokerage().replace(old, new, 1)
    assert body != brokerage()
    result = read(body)
    assert any(word in p for p in result.problems), result.problems


def test_a_bad_line_leaves_the_rest_readable():
    (b,) = read(brokerage().replace("<UNITS>10<", "<UNITS>x<", 1)).brokerages
    assert [t.fitid for t in b.trades] == ["S1"] and len(b.income) == 2 and len(b.holdings) == 2


def test_unsupported_types_are_listed_as_left_out():
    unsupported = (
        "<BUYOPT><INVBUY><INVTRAN><FITID>O1<DTTRADE>20260102</INVTRAN></INVBUY></BUYOPT>"
        "<BUYOPT><INVBUY><INVTRAN><FITID>O2<DTTRADE>20260102</INVTRAN></INVBUY></BUYOPT>"
        "<MARGININTEREST><INVTRAN><FITID>M1<DTTRADE>20260102</INVTRAN><TOTAL>-1.00"
        "</MARGININTEREST>"
        "<REINVEST><INVTRAN><FITID>R1<DTTRADE>20260102</INVTRAN></REINVEST>"
    )
    body = TRADES.replace("<BUYSTOCK>", unsupported + "<BUYSTOCK>", 1)
    body += (
        "<INVPOSLIST><POSOPT><INVPOS><SECID><UNIQUEID>333333333</SECID></INVPOS></POSOPT>"
        "</INVPOSLIST>"
    )
    result = read(brokerage(body))
    (b,) = result.brokerages
    assert len(b.trades) == 2 and len(b.income) == 2  # supported lines are still read
    text = " ".join(result.problems)
    for words in (
        "2 option purchases",
        "1 margin interest",
        "1 dividend reinvestment",
        "1 option holding",
    ):
        assert words in text
    assert "FKCO260619C" not in text


def test_oversize_and_limits():
    with pytest.raises(ofx.OfxError, match="too big"):
        ofx.parse_ofx(b"<OFX>" + b" " * ofx.MAX_BYTES)
    one = "<INVBANKTRAN><STMTTRN><DTPOSTED>20260101<TRNAMT>1<FITID>F</STMTTRN></INVBANKTRAN>"
    lines = "<INVTRANLIST>" + one * 10_001 + "</INVTRANLIST>"
    with pytest.raises(ofx.OfxError, match="10,000"):
        read(brokerage(lines))
    empty = "<INVSTMTRS><INVACCTFROM><ACCTID>1111</INVACCTFROM></INVSTMTRS>"
    assert (
        len(read(brokerage("").replace("<INVSTMTTRNRS>", "<INVSTMTTRNRS>" + empty)).brokerages) == 2
    )
    crowded = brokerage("").replace("<INVSTMTTRNRS>", "<INVSTMTTRNRS>" + empty * 51)
    with pytest.raises(ofx.OfxError, match="50 accounts"):
        read(crowded)


def test_brokerage_only_file_is_accepted_and_empty_file_is_not():
    assert read(brokerage("")).brokerages[0].holdings == []
    nothing = checking().replace("<ACCTID>000123456789", "<ACCTID>")
    with pytest.raises(ofx.OfxError, match="no bank, card or brokerage"):
        read(nothing)


def test_not_usd_is_still_refused():
    with pytest.raises(ofx.OfxError, match="US dollar"):
        read(brokerage(cur="EUR"))


def _income(fitid, kind, total, date="20260106", extra=""):
    return (
        f"<INCOME><INVTRAN><FITID>{fitid}<DTTRADE>{date}</INVTRAN><SECID><UNIQUEID>111111111"
        f"</SECID><INCOMETYPE>{kind}<TOTAL>{total}{extra}</INCOME>"
    )


def _one(inner):
    return read(brokerage(f"<INVTRANLIST>{inner}</INVTRANLIST>")).brokerages[0]


def test_buymf_sellstock_and_income_kinds():
    buy = (
        "<BUYMF><INVBUY><INVTRAN><FITID>M1<DTTRADE>20260102</INVTRAN><SECID><UNIQUEID>222222222"
        "</SECID><UNITS>2.5<UNITPRICE>10<TOTAL>-25.00</INVBUY><BUYTYPE>BUY</BUYMF>"
    )
    sell = (
        "<SELLSTOCK><INVSELL><INVTRAN><FITID>M2<DTTRADE>20260103</INVTRAN><SECID><UNIQUEID>"
        "111111111</SECID><UNITS>-2<UNITPRICE>30<FEES>0.50<TOTAL>59.50</INVSELL>"
        "<SELLTYPE>SELL</SELLSTOCK>"
    )
    b = _one(buy + sell + _income("G1", "CGLONG", "7.00") + _income("G2", "CGSHORT", "1.00"))
    assert [(t.side, t.kind, t.ticker) for t in b.trades] == [
        ("buy", "fund", "FKIDX"),
        ("sell", "stock", "FKCO"),
    ]
    assert b.trades[1].fees_cents == 50 and b.trades[1].total_cents == 5950
    assert [i.kind for i in b.income] == ["CGLONG", "CGSHORT"]
    assert _one(_income("G3", "MISC", "2.00")).income[0].kind == "MISC"


def test_income_reversal_withholding_and_tax_exempt():
    b = _one(
        _income("R1", "DIV", "-4.20")
        + _income("W1", "DIV", "10.00", extra="<WITHHOLDING>1.50<TAXEXEMPT>Y")
    )
    reversal, held = b.income
    assert reversal.total_cents == -420 and (reversal.withholding_cents, reversal.tax_exempt) == (
        0,
        False,
    )
    assert (held.withholding_cents, held.tax_exempt) == (150, True)


def test_trade_date_with_timezone_is_kept_as_written():
    inner = TRADES.replace("<DTTRADE>20260102120000", "<DTTRADE>20260102235959.000[-5:EST]")
    assert read(brokerage(inner)).brokerages[0].trades[0].trade_date == dt.date(2026, 1, 2)


def test_foreign_currency_line_is_left_out_even_in_a_usd_file():
    foreign = TRADES.replace(
        "<TOTAL>-256.25", "<TOTAL>-256.25<CURRENCY><CURRATE>1.1<CURSYM>EUR</CURRENCY>", 1
    )
    result = read(brokerage(foreign))
    assert [t.fitid for t in result.brokerages[0].trades] == ["S1"]
    assert any("currency other than US dollars" in p for p in result.problems)
    usd = TRADES.replace("<TOTAL>-256.25", "<TOTAL>-256.25<CURRENCY><CURSYM>USD</CURRENCY>", 1)
    assert len(read(brokerage(usd)).brokerages[0].trades) == 2


def test_long_fund_price_is_rounded_to_six_decimals_and_keeps_the_trade():
    inner = TRADES.replace("<UNITPRICE>100.1234", "<UNITPRICE>100.12345678", 1)
    sell = read(brokerage(inner)).brokerages[0].trades[1]
    assert sell.unit_price_micro == 100_123_457 and sell.total_cents == 15018
    down = TRADES.replace("<UNITPRICE>100.1234", "<UNITPRICE>100.1234564", 1)
    assert read(brokerage(down)).brokerages[0].trades[1].unit_price_micro == 100_123_456
    junk = TRADES.replace("<UNITPRICE>100.1234", "<UNITPRICE>1.2345678x", 1)
    assert any("unit price" in p for p in read(brokerage(junk)).problems)


def test_scaled_numbers_stay_inside_sqlite_integers():
    assert ofx.parse_scaled("9999999999.999999", 6) == 9_999_999_999_999_999
    with pytest.raises(ValueError):
        ofx.parse_scaled("10000000000", 6)
    assert ofx.parse_amount("99999999999999.99") == 9_999_999_999_999_999
    with pytest.raises(ValueError):
        ofx.parse_amount("100000000000000")
    assert 9_999_999_999_999_999 < 2**63


def test_many_lines_read_quickly_and_repeats_are_still_caught():
    one = "<INVBANKTRAN><STMTTRN><DTPOSTED>20260101<TRNAMT>1<FITID>F{}</STMTTRN></INVBANKTRAN>"
    lines = "".join(one.format(n) for n in range(5000)) + one.format(7)
    b = _one(lines)
    assert len(b.cash) == 5000 and any("same transaction ID" in p for p in b.problems)
