"""The brokerage statement shapes (roadmap 26-4a). Numbers: see ``ofx_investments.py``."""

import datetime as dt
from dataclasses import dataclass, field

from app.services.imports import ofx_parsing as base


@dataclass(frozen=True)
class OfxHolding:
    ticker: str
    name: str
    kind: str  # "stock" or "fund"
    units_micro: int
    unit_price_micro: int
    value_cents: int  # the broker's market value
    as_of: dt.date
    position: int = 0  # 1, 2, ... among the holdings listed in the file


@dataclass(frozen=True)
class OfxTrade:
    fitid: str
    side: str  # "buy" or "sell"
    kind: str  # "stock" or "fund"
    ticker: str
    name: str
    units_micro: int
    unit_price_micro: int
    commission_cents: int
    fees_cents: int
    total_cents: int  # what moved in the account, as the broker states it
    trade_date: dt.date
    description: str
    position: int = 0  # 1, 2, ... among this account's investment lines as listed


@dataclass(frozen=True)
class OfxIncome:
    fitid: str
    # CGLONG/CGSHORT are a fund's capital-gain payouts (1099-DIV), NOT gains from selling shares.
    kind: str  # CGLONG, CGSHORT, DIV, INTEREST or MISC
    ticker: str  # empty for income that names no security (cash interest)
    total_cents: int
    paid: dt.date
    description: str
    position: int = 0
    withholding_cents: int = 0  # tax the broker held back (WITHHOLDING), as a positive amount
    tax_exempt: bool = False  # TAXEXEMPT: e.g. municipal bond interest


@dataclass
class OfxBrokerage:
    last4: str
    as_of: dt.date | None = None  # the statement's own date
    holdings: list[OfxHolding] = field(default_factory=list)
    trades: list[OfxTrade] = field(default_factory=list)
    income: list[OfxIncome] = field(default_factory=list)
    cash: list[base.OfxTransaction] = field(default_factory=list)  # cash sweep lines
    problems: list[str] = field(default_factory=list)
    listed: int = 0  # investment lines listed, usable or not
    listed_holdings: int = 0
    not_read: dict[str, int] = field(default_factory=dict)  # unsupported tag -> how many
    seen: set[str] = field(default_factory=set, repr=False)  # accepted FITIDs, for repeats
