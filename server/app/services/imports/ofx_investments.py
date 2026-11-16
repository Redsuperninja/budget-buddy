"""Reading a brokerage OFX/QFX statement: holdings, trades, income, cash sweeps (roadmap 26-4a).

Same rules as ``ofx_parsing.py`` (ADR-0016): text only, no XML library, nothing logged or kept
except what the dataclasses in ofx_invest_types.py hold, only the last four characters of the
account number, problems in plain English instead of crashing. This step only READS (saving:
26-4b, 26-4c).

Number formats, all exact (no floats):
- Money (totals, commission, fees, market value, cash lines) is integer cents.
- Units and unit prices are integer **micro-units** (1.5 shares = 1_500_000), because funds
  have fractional shares and prices often have 4 decimals. A unit price with more than 6
  decimals is rounded to 6 (``_price``); units with more are a problem line.
- Signs are as the file states them (a sell's units are normally negative, a buy's total negative).
"""

import datetime as dt
import re
from dataclasses import replace

from app.services.imports import ofx_parsing as base
from app.services.imports.csv_parsing import clean_description
from app.services.imports.ofx_invest_types import OfxBrokerage, OfxHolding, OfxIncome, OfxTrade

MICRO = 6  # decimals kept for units and unit prices
_LONG_DECIMAL = re.compile(r"([+-]?)([0-9]*)\.([0-9]{7,})")
_TICKER = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,9}")
_SECURITY_TAGS = {"STOCKINFO", "MFINFO", "OPTINFO", "DEBTINFO", "OTHERINFO"}
_POSITIONS = {"POSSTOCK": "stock", "POSMF": "fund"}
_TRADES = {  # tag: (side, kind)
    "BUYSTOCK": ("buy", "stock"),
    "BUYMF": ("buy", "fund"),
    "SELLSTOCK": ("sell", "stock"),
    "SELLMF": ("sell", "fund"),
}
_LINES = {"INCOME", "INVBANKTRAN"}
_INCOME_TYPES = ("CGLONG", "CGSHORT", "DIV", "INTEREST", "MISC")
_COLLECT = _SECURITY_TAGS | set(_POSITIONS) | set(_TRADES) | _LINES | {"INVACCTFROM"}
_NOT_READ = {  # tags we recognise but don't read yet, in the words the user would use
    "POSOPT": "option holding",
    "POSDEBT": "bond holding",
    "POSOTHER": "other holding",
    "BUYOPT": "option purchase",
    "SELLOPT": "option sale",
    "CLOSUREOPT": "option expiry or exercise",
    "BUYDEBT": "bond purchase",
    "SELLDEBT": "bond sale",
    "BUYOTHER": "other security purchase",
    "SELLOTHER": "other security sale",
    "INVEXPENSE": "investment expense",
    "JRNLFUND": "cash transfer between accounts",
    "JRNLSEC": "security transfer between accounts",
    "MARGININTEREST": "margin interest",
    "REINVEST": "dividend reinvestment",
    "RETOFCAP": "return of capital",
    "SPLIT": "stock split",
    "TRANSFER": "transfer of shares",
}


def read_brokerages(text: str, start: int) -> list[OfxBrokerage]:
    """Every ``INVSTMTRS`` in the file, with the file-wide security list resolved at the end."""
    statements: list[OfxBrokerage] = []
    raw: list[tuple[OfxBrokerage, str, dict[str, str], int]] = []
    securities: dict[str, tuple[str, str]] = {}  # UNIQUEID -> (ticker, name)
    current: OfxBrokerage | None = None
    collecting: str | None = None
    leaves: dict[str, str] = {}
    total = 0
    for found in base._TAG.finditer(text, start):
        closing, tag, value = found.groups()
        tag = tag.upper()
        if collecting:
            if closing and tag == collecting:
                _store(collecting, leaves, current, raw, securities)
                collecting = None
            elif not closing:
                leaves[tag] = base._unescape(value)
        elif closing:
            current = None if tag == "INVSTMTRS" else current
        elif tag == "INVSTMTRS":
            if len(statements) >= base.MAX_STATEMENTS:
                raise base.OfxError("This file has more than 50 accounts in it.")
            current = OfxBrokerage(last4="")
            statements.append(current)
        elif tag in _SECURITY_TAGS or (current and tag in _COLLECT):
            collecting, leaves = tag, {}
            total += tag not in _SECURITY_TAGS | {"INVACCTFROM"}
        elif current and tag in _NOT_READ:
            current.not_read[tag] = current.not_read.get(tag, 0) + 1
            total += 1
        elif current and tag == "DTASOF" and current.as_of is None:
            current.as_of = _date_or_none(value)
        if total > base.MAX_TRANSACTIONS:  # holdings, trades, income, cash lines and skipped lines
            raise base.OfxError(
                "This file has more than 10,000 transactions. Download a shorter date range."
            )
    for statement, tag, entry, number in raw:
        _resolve(statement, tag, entry, number, securities)
    for statement in statements:
        _note_not_read(statement)
    return [s for s in statements if s.last4]


def _date_or_none(text: str) -> dt.date | None:
    try:
        return base.parse_date(text)
    except ValueError:
        return None


def _store(tag, leaves, current, raw, securities) -> None:
    if tag in _SECURITY_TAGS:
        ident = leaves.get("UNIQUEID", "")
        if ident:
            securities.setdefault(
                ident, (leaves.get("TICKER", "").upper(), leaves.get("SECNAME", ""))
            )
    elif current is None:
        return
    elif tag == "INVACCTFROM":
        current.last4 = re.sub(r"[^0-9A-Za-z]", "", leaves.get("ACCTID", ""))[-4:]
    elif tag in _POSITIONS:
        current.listed_holdings += 1
        raw.append((current, tag, leaves, current.listed_holdings))
    else:
        current.listed += 1
        raw.append((current, tag, leaves, current.listed))


def _security(leaves: dict[str, str], securities) -> tuple[str, str]:
    """(ticker, name) for the leaves' ``UNIQUEID``; raises ValueError when it can't be told."""
    ident = leaves.get("UNIQUEID", "")
    ticker, name = securities.get(ident, ("", ""))
    if not ticker or not _TICKER.fullmatch(ticker):
        raise ValueError("the file doesn't say which stock or fund this is (no ticker)")
    return ticker, clean_description(name)


def _price(leaves, label="unit price") -> int:
    """Unit price in micro-units. More than 6 decimals (some funds quote 8) is rounded half away
    from zero to 6, here and nowhere else; the TOTAL stays the authority for the money."""
    text = leaves.get("UNITPRICE", "").strip()
    try:
        return base.parse_scaled(text, MICRO)
    except ValueError:
        pass
    match = _LONG_DECIMAL.fullmatch(text)
    if not match:
        raise ValueError(f"the {label} isn't a number we can read exactly")
    sign, whole, frac = match.groups()
    kept = base.parse_scaled(f"{whole or '0'}.{frac[:MICRO]}", MICRO)
    kept += frac[MICRO] >= "5"
    return -kept if sign == "-" else kept


def _number(leaves, key, scale, label, default=None) -> int:
    text = leaves.get(key, "")
    if not text and default is not None:
        return default
    try:
        return base.parse_scaled(text, scale)
    except ValueError:
        raise ValueError(f"the {label} isn't a number we can read exactly") from None


def _date(leaves, key, label) -> dt.date:
    try:
        return base.parse_date(leaves.get(key, ""))
    except ValueError:
        raise ValueError(f"the {label} isn't a date we can read") from None


def _fitid(leaves, seen) -> str:
    fitid = leaves.get("FITID", "")
    if not fitid or len(fitid) > base.MAX_FITID or base._UNUSABLE_ID.search(fitid):
        raise ValueError("the broker's transaction ID is missing or not usable")
    if fitid in seen:
        raise ValueError("the broker used the same transaction ID twice")
    return fitid


def _resolve(statement, tag, leaves, number, securities) -> None:
    seen = statement.seen
    problems = statement.problems
    try:
        _check_currency(leaves)
        if tag in _POSITIONS:
            statement.holdings.append(_holding(statement, tag, leaves, number, securities))
        elif tag in _TRADES:
            statement.trades.append(_trade(tag, leaves, number, securities, seen))
            seen.add(statement.trades[-1].fitid)
        elif tag == "INCOME":
            statement.income.append(_income(leaves, number, securities, seen))
            seen.add(statement.income[-1].fitid)
        else:
            item = base._transaction(leaves)
            if item.fitid in seen:
                raise ValueError("the broker used the same transaction ID twice")
            statement.cash.append(replace(item, position=number))
            seen.add(item.fitid)
    except ValueError as error:
        what = "Holding" if tag in _POSITIONS else "Investment line"
        base._note(problems, f"{what} {number} was left out: {error}.")


def _check_currency(leaves) -> None:
    """A line in its own currency (CURRENCY, ORIGCURRENCY) is not dollars, even in a USD file."""
    code = (leaves.get("CURSYM") or leaves.get("CURRENCY") or "").strip().upper()
    if code and code != "USD":
        raise ValueError("it is in a currency other than US dollars")


def _holding(statement, tag, leaves, number, securities) -> OfxHolding:
    if leaves.get("POSTYPE", "LONG").upper() != "LONG":
        raise ValueError("it is a short position, which isn't supported")
    ticker, name = _security(leaves, securities)
    as_of = _date_or_none(leaves.get("DTPRICEASOF", "")) or statement.as_of
    if as_of is None:
        raise ValueError("the file gives no date for the price")
    return OfxHolding(
        ticker,
        name,
        _POSITIONS[tag],
        _number(leaves, "UNITS", MICRO, "number of units"),
        _price(leaves),
        _number(leaves, "MKTVAL", 2, "market value"),
        as_of,
        number,
    )


def _trade(tag, leaves, number, securities, seen) -> OfxTrade:
    side, kind = _TRADES[tag]
    if leaves.get("BUYTYPE", "BUY").upper() not in ("BUY", "") or leaves.get(
        "SELLTYPE", "SELL"
    ).upper() not in ("SELL", ""):
        raise ValueError("it is a short sale or cover, which isn't supported")
    fitid = _fitid(leaves, seen)
    ticker, name = _security(leaves, securities)
    return OfxTrade(
        fitid,
        side,
        kind,
        ticker,
        name,
        _number(leaves, "UNITS", MICRO, "number of units"),
        _price(leaves),
        _number(leaves, "COMMISSION", 2, "commission", 0),
        _number(leaves, "FEES", 2, "fees", 0),
        _number(leaves, "TOTAL", 2, "total"),
        _date(leaves, "DTTRADE", "trade date"),
        clean_description(leaves.get("MEMO", "")) or name,
        number,
    )


def _income(leaves, number, securities, seen) -> OfxIncome:
    fitid = _fitid(leaves, seen)
    kind = leaves.get("INCOMETYPE", "").upper()
    if kind not in _INCOME_TYPES:
        raise ValueError("the kind of income isn't one we know")
    ticker, name = _security(leaves, securities) if leaves.get("UNIQUEID") else ("", "")
    return OfxIncome(
        fitid,
        kind,
        ticker,
        _number(leaves, "TOTAL", 2, "total"),
        _date(leaves, "DTTRADE", "date"),
        clean_description(leaves.get("MEMO", "")) or name,
        number,
        abs(_number(leaves, "WITHHOLDING", 2, "tax withheld", 0)),
        leaves.get("TAXEXEMPT", "").strip().upper() == "Y",
    )


def _note_not_read(statement: OfxBrokerage) -> None:
    for tag, count in statement.not_read.items():
        word = _NOT_READ[tag]
        base._note(
            statement.problems,
            f"{count} {word}{'s' if count > 1 else ''} ({tag}) in this brokerage account "
            "were left out: that kind isn't supported yet.",
        )
