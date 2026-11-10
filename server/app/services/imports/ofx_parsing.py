"""Reading a bank's OFX/QFX download (roadmap 26-1, ADR-0016).

OFX 1.x is SGML (leaf tags have no closing tag) and OFX 2.x is XML; QFX is OFX with extra headers.
This is a small tag reader, not an XML parser: it only splits text into tags and values, so there
are no entities, DTDs or external files to expand. Only the five plain XML escapes are undone.

Banking and credit card statements are read here (transactions with the bank's own ``FITID``, and
the statement balance). Brokerage statements arrive in 26-4. Nothing here logs or keeps file
contents: the full account number is never stored, only its last four characters, and error
messages name only numbers.
"""

import datetime as dt
import re
from dataclasses import dataclass, field

from app.services.imports.csv_parsing import clean_description

MAX_BYTES = 5_000_000
MAX_TRANSACTIONS = 10_000
MAX_FITID = 255
MAX_STATEMENTS = 50
MAX_TAGS = 500_000
MAX_PROBLEMS = 100
MAX_DOLLAR_DIGITS = 14  # far above any real balance, far below SQLite's integer limit
KINDS = ("CHECKING", "SAVINGS", "MONEYMRKT", "CREDITLINE", "CD", "CREDITCARD")

_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9_.]*)>([^<\r\n]*)")
_CHARSET = re.compile(rb"CHARSET:\s*([0-9A-Za-z-]+)")
_AMOUNT = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?")
_DATE = re.compile(
    r"([0-9]{4})([0-9]{2})([0-9]{2})(?:[0-9]{4}(?:[0-9]{2})?)?(?:\.[0-9]+)?(?:\[[^\]]*\])?"
)
_UNUSABLE_ID = re.compile(r"[^\x21-\x7e]")  # an ID is printable ASCII, nothing hidden
_ESCAPES = (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&"))

# Aggregates whose leaf tags we keep, and the statement blocks that start a new account.
_COLLECT = {"STMTTRN", "BANKACCTFROM", "CCACCTFROM", "LEDGERBAL"}
_STATEMENTS = {"STMTRS", "CCSTMTRS"}


class OfxError(ValueError):
    """The file can't be used at all. The message is plain English and names no file content."""


@dataclass(frozen=True)
class OfxTransaction:
    fitid: str
    posted: dt.date
    cents: int  # money in is positive, money out is negative, as the bank states it
    description: str


@dataclass
class OfxStatement:
    kind: str  # the bank's account type: CHECKING, SAVINGS, CREDITCARD, ...
    last4: str  # the last four characters of the account number, never the whole number
    transactions: list[OfxTransaction] = field(default_factory=list)
    balance_cents: int | None = None
    balance_date: dt.date | None = None


@dataclass
class OfxFile:
    statements: list[OfxStatement]
    problems: list[str]  # plain-English notes on transactions that were left out


def decode_ofx(data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise OfxError("This file is too big to be a bank download (the limit is 5 MB).")
    head = _CHARSET.search(data[:2000])
    for encoding in (["cp1252"] if head and head.group(1) == b"1252" else []) + [
        "utf-8-sig",
        "cp1252",
    ]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise OfxError("This file's text can't be read. Try downloading it again.")


def parse_amount(text: str) -> int:
    """Dollars as exact text ('-12.5', '1000', '.5') to cents. Anything else raises ValueError."""
    match = _AMOUNT.fullmatch(text.strip())
    if not match or not (match.group(2) or match.group(3)):
        raise ValueError(text)
    sign, whole, frac = match.group(1), match.group(2) or "0", match.group(3) or ""
    if frac[2:].strip("0"):
        raise ValueError(text)  # a third decimal that isn't zero would be rounded: never guess
    if len(whole) > MAX_DOLLAR_DIGITS:
        raise ValueError(text)
    cents = int(whole) * 100 + int((frac + "00")[:2])
    return -cents if sign == "-" else cents


def parse_date(text: str) -> dt.date:
    match = _DATE.fullmatch(text.strip())
    if not match:
        raise ValueError(text)
    return dt.date(*(int(part) for part in match.groups()))  # the time and zone are ignored


def _unescape(text: str) -> str:
    for escaped, plain in _ESCAPES:
        text = text.replace(escaped, plain)
    return text.strip()


def _description(leaves: dict[str, str]) -> str:
    name, memo = leaves.get("NAME", ""), leaves.get("MEMO", "")
    return clean_description(f"{name} - {memo}" if name and memo and name != memo else name or memo)


def _transaction(leaves: dict[str, str]) -> OfxTransaction:
    fitid = leaves.get("FITID", "")
    if not fitid or len(fitid) > MAX_FITID or _UNUSABLE_ID.search(fitid):
        raise ValueError("the bank's transaction ID is missing or not usable")
    try:
        cents = parse_amount(leaves.get("TRNAMT", ""))
    except ValueError:
        raise ValueError("the amount isn't a number we can read exactly") from None
    try:
        posted = parse_date(leaves.get("DTPOSTED", ""))
    except ValueError:
        raise ValueError("the date isn't one we can read") from None
    return OfxTransaction(fitid, posted, cents, _description(leaves))


def parse_ofx(data: bytes) -> OfxFile:
    text = decode_ofx(data)
    start = text.find("<OFX>")
    if start < 0:
        raise OfxError("This doesn't look like a bank download (an OFX or QFX file).")
    statements: list[OfxStatement] = []
    problems: list[str] = []
    seen: set[tuple[int, str]] = set()
    current: str | None = None
    leaves: dict[str, str] = {}
    count = 0
    for number_of_tags, found in enumerate(_TAG.finditer(text, start), 1):
        if number_of_tags > MAX_TAGS:
            raise OfxError("This file is too complicated to be a bank download.")
        closing, tag, value = found.groups()
        tag = tag.upper()
        if tag == "CURDEF" and value.strip().upper() not in ("USD", ""):
            raise OfxError("Budget Buddy reads US dollar accounts only.")
        if tag in _STATEMENTS and not closing:
            if len(statements) >= MAX_STATEMENTS:
                raise OfxError("This file has more than 50 accounts in it.")
            statements.append(
                OfxStatement(kind="CREDITCARD" if tag == "CCSTMTRS" else "", last4="")
            )
        elif tag in _COLLECT and not closing:
            current, leaves = tag, {}
        elif tag in _COLLECT and closing and current == tag and statements:
            count += tag == "STMTTRN"
            _finish(statements[-1], tag, leaves, problems, seen, (len(statements), count))
            if count > MAX_TRANSACTIONS:
                raise OfxError(
                    "This file has more than 10,000 transactions. Download a shorter date range."
                )
            current = None
        elif current and not closing:
            leaves[tag] = _unescape(value)
    if not any(s.last4 for s in statements):
        raise OfxError("This file has no bank or card statement in it.")
    return OfxFile(statements, problems)


def _finish(statement, tag, leaves, problems, seen, where: tuple[int, int]) -> None:
    number, index = where  # which statement, and which transaction in the file
    if tag in ("BANKACCTFROM", "CCACCTFROM"):
        statement.last4 = re.sub(r"[^0-9A-Za-z]", "", leaves.get("ACCTID", ""))[-4:]
        kind = leaves.get("ACCTTYPE", "").upper()
        statement.kind = kind if kind in KINDS else statement.kind
    elif tag == "LEDGERBAL":
        try:
            statement.balance_cents = parse_amount(leaves.get("BALAMT", ""))
            statement.balance_date = parse_date(leaves.get("DTASOF", ""))
        except ValueError:
            _note(problems, "The statement balance couldn't be read, so it was left out.")
    else:
        try:
            item = _transaction(leaves)
            if (number, item.fitid) in seen:
                raise ValueError("the bank used the same transaction ID twice")
        except ValueError as error:
            _note(problems, f"Transaction {index} was left out: {error}.")
            return
        seen.add((number, item.fitid))
        statement.transactions.append(item)


def _note(problems: list[str], text: str) -> None:
    """Keep at most MAX_PROBLEMS notes, then one line saying there were more."""
    if len(problems) < MAX_PROBLEMS:
        problems.append(text)
    elif len(problems) == MAX_PROBLEMS:
        problems.append("There were more problems than are listed here.")
