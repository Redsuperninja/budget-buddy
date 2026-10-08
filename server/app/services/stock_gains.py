"""Stock gains math: FIFO lot matching, short vs long term, wash-sale flags. No database here.

Everything is an **estimate**, not tax advice. Your broker's Form 1099-B is the official record.

Units: shares are whole millionths of a share (``shares_micro``, see ``SHARES_SCALE``) and money
is whole cents. Nothing is ever a float.

Rounding (the only places it happens):
- A lot's cost is shared out over the shares sold from it *cumulatively*, rounding half up:
  the shares sold so far from the lot cost ``round(cost * sold_so_far / lot_shares)``, and each
  piece gets the difference from the previous total. So the pieces of a fully sold lot always add
  up to exactly its cost, and no cent is lost or made up.
- A sale's proceeds are shared out over the lots it used the same way.

Rules (statutory, not tax-year numbers, so they live here rather than in ``app/tax_data``):
- Holding period: it starts the day *after* you buy (Rev. Rul. 66-7). More than one year is long
  term, otherwise short term (26 U.S.C. 1222; IRS Publication 550, "Holding Period"):
  https://www.irs.gov/publications/p550 and https://www.law.cornell.edu/uscode/text/26/1222
- Wash sale: a loss sale with a purchase of the same stock 30 days before or after the sale
  (26 U.S.C. 1091; Publication 550, "Wash Sales"). We only *flag* a possible wash sale; the loss
  and the replacement shares' cost are not adjusted. The rest of the same purchase as the losing
  shares doesn't count as a replacement (Rev. Rul. 56-602); another purchase this sale only
  partly used does. Only purchases entered in Budget Buddy are checked, in any account; a
  replacement bought in an IRA makes the loss lost for good, not postponed (Rev. Rul. 2008-5).
  https://www.law.cornell.edu/uscode/text/26/1091
"""

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

WASH_SALE_WINDOW_DAYS = 30  # 26 U.S.C. 1091(a): 30 days before or after the sale


class Term(StrEnum):
    SHORT = "short"  # held one year or less
    LONG = "long"  # held more than one year


@dataclass(frozen=True)
class Lot:
    """Shares bought in one purchase. ``cost_basis_cents`` includes fees."""

    id: int
    symbol: str
    account_id: int | None
    acquired_on: dt.date
    shares_micro: int
    cost_basis_cents: int


@dataclass(frozen=True)
class Sale:
    """One sale as entered. ``proceeds_cents`` is after fees."""

    id: int
    symbol: str
    account_id: int | None
    sold_on: dt.date
    shares_micro: int
    proceeds_cents: int


@dataclass(frozen=True)
class Piece:
    """The part of a sale that came out of one lot."""

    sale_id: int
    lot_id: int
    shares_micro: int
    proceeds_cents: int


@dataclass(frozen=True)
class Realized:
    """A piece with its cost, gain (negative = loss), and term worked out."""

    sale_id: int
    lot_id: int
    symbol: str
    account_id: int | None
    acquired_on: dt.date
    sold_on: dt.date
    shares_micro: int
    proceeds_cents: int
    cost_basis_cents: int
    gain_cents: int
    term: Term
    possible_wash_sale: bool


@dataclass(frozen=True)
class TermTotals:
    proceeds_cents: int = 0
    cost_basis_cents: int = 0
    gain_cents: int = 0


@dataclass(frozen=True)
class YearSummary:
    tax_year: int
    short_term: TermTotals
    long_term: TermTotals
    total_gain_cents: int
    possible_wash_sale_count: int  # number of sales with at least one flagged piece


class NotEnoughShares(Exception):
    """A sale needs more shares than were held (by its date, in its account) after earlier
    sales. ``sale`` is the first sale that can't be covered."""

    def __init__(self, sale: Sale) -> None:
        super().__init__(f"sale {sale.id} has more shares than were held")
        self.sale = sale


def long_term_from(acquired_on: dt.date) -> dt.date:
    """The first sale date that counts as long term for shares bought on ``acquired_on``.

    The holding period starts the day after the purchase, and a sale is long term once a full
    year from that start has passed. A year that starts on Feb 29 ends on Feb 28 the next year
    (there's no Feb 29), so the next day, Mar 1, is long term.

    >>> long_term_from(dt.date(2025, 3, 10))  # held from Mar 11, 2025
    datetime.date(2026, 3, 11)
    """
    start = acquired_on + dt.timedelta(days=1)
    try:
        return start.replace(year=start.year + 1)
    except ValueError:  # start is Feb 29 and next year has no Feb 29
        return dt.date(start.year + 1, 3, 1)


def holding_term(acquired_on: dt.date, sold_on: dt.date) -> Term:
    if sold_on < acquired_on:
        raise ValueError("A sale can't come before the purchase.")
    return Term.LONG if sold_on >= long_term_from(acquired_on) else Term.SHORT


def share_of(total: int, part: int, whole: int) -> int:
    """``total * part / whole`` rounded half up. All three are >= 0 and ``whole`` > 0."""
    return (2 * total * part + whole) // (2 * whole)


def _group_key(symbol: str, account_id: int | None) -> tuple[str, int | None]:
    return symbol, account_id


def _fifo_lots(lots: Iterable[Lot]) -> list[Lot]:
    return sorted(lots, key=lambda lot: (lot.acquired_on, lot.id))


def _date_order(sales: Iterable[Sale]) -> list[Sale]:
    return sorted(sales, key=lambda sale: (sale.sold_on, sale.id))


def match_fifo(lots: Iterable[Lot], sales: Iterable[Sale]) -> list[Piece]:
    """Match each sale to lots, oldest purchase first (FIFO), separately per symbol and account.

    Sales are handled in date order. A sale can only use shares bought on or before its date.
    Raises ``NotEnoughShares`` for the first sale that needs more shares than are left.
    """
    remaining: dict[int, int] = {}
    lots_by_group: dict[tuple, list[Lot]] = defaultdict(list)
    for lot in _fifo_lots(lots):
        remaining[lot.id] = lot.shares_micro
        lots_by_group[_group_key(lot.symbol, lot.account_id)].append(lot)

    pieces: list[Piece] = []
    for sale in _date_order(sales):
        taken: list[tuple[int, int]] = []  # (lot_id, shares_micro)
        need = sale.shares_micro
        for lot in lots_by_group[_group_key(sale.symbol, sale.account_id)]:
            if need == 0 or lot.acquired_on > sale.sold_on:
                break
            take = min(need, remaining[lot.id])
            if take:
                taken.append((lot.id, take))
                need -= take
        if need:
            raise NotEnoughShares(sale)

        done = given = 0
        for lot_id, shares in taken:
            remaining[lot_id] -= shares
            done += shares
            proceeds = share_of(sale.proceeds_cents, done, sale.shares_micro) - given
            given += proceeds
            pieces.append(Piece(sale.id, lot_id, shares, proceeds))
    return pieces


def realize(lots: Iterable[Lot], sales: Iterable[Sale], pieces: Iterable[Piece]) -> list[Realized]:
    """Work out each piece's cost, gain, term, and wash-sale flag, in sale date order.

    ``lots`` should include every lot of the symbols involved, in every account: a purchase in
    any of your accounts can make a loss a possible wash sale.
    """
    lots_by_id = {lot.id: lot for lot in lots}
    sales_by_id = {sale.id: sale for sale in sales}
    order = {sale.id: i for i, sale in enumerate(_date_order(sales_by_id.values()))}
    ordered = sorted(
        pieces, key=lambda p: (order[p.sale_id], lots_by_id[p.lot_id].acquired_on, p.lot_id)
    )
    # Lots each sale used up completely (nothing left after it). Shares left in a lot a sale
    # only partly used can still be replacement shares for another lot's loss.
    emptied_by_sale: dict[int, set[int]] = defaultdict(set)
    running: dict[int, int] = defaultdict(int)
    for piece in ordered:
        running[piece.lot_id] += piece.shares_micro
        if running[piece.lot_id] == lots_by_id[piece.lot_id].shares_micro:
            emptied_by_sale[piece.sale_id].add(piece.lot_id)

    sold_from_lot: dict[int, int] = defaultdict(int)
    costed_from_lot: dict[int, int] = defaultdict(int)
    out: list[Realized] = []
    for piece in ordered:
        lot, sale = lots_by_id[piece.lot_id], sales_by_id[piece.sale_id]
        sold_from_lot[lot.id] += piece.shares_micro
        cost = (
            share_of(lot.cost_basis_cents, sold_from_lot[lot.id], lot.shares_micro)
            - costed_from_lot[lot.id]
        )
        costed_from_lot[lot.id] += cost
        gain = piece.proceeds_cents - cost
        out.append(
            Realized(
                sale_id=sale.id,
                lot_id=lot.id,
                symbol=sale.symbol,
                account_id=sale.account_id,
                acquired_on=lot.acquired_on,
                sold_on=sale.sold_on,
                shares_micro=piece.shares_micro,
                proceeds_cents=piece.proceeds_cents,
                cost_basis_cents=cost,
                gain_cents=gain,
                term=holding_term(lot.acquired_on, sale.sold_on),
                possible_wash_sale=gain < 0
                and _bought_nearby(sale, lot.id, lots_by_id.values(), emptied_by_sale[sale.id]),
            )
        )
    return out


def _bought_nearby(sale: Sale, loss_lot_id: int, lots: Iterable[Lot], emptied: set[int]) -> bool:
    """Was the same symbol bought (in any account entered here) within 30 days before or after
    the sale, as possible replacement shares for the loss on ``loss_lot_id``?

    Not counted: the rest of the losing lot itself (Rev. Rul. 56-602), and other lots this same
    sale used up completely. Another lot the sale only partly used still counts, since its
    remaining shares are replacement shares.
    """
    window = dt.timedelta(days=WASH_SALE_WINDOW_DAYS)
    return any(
        lot.symbol == sale.symbol
        and lot.id != loss_lot_id
        and lot.id not in emptied
        and abs(lot.acquired_on - sale.sold_on) <= window
        for lot in lots
    )


def summarize(realized: Iterable[Realized], tax_year: int) -> YearSummary:
    """Totals for sales dated in ``tax_year`` (gains count in the year of the sale date)."""
    totals = {Term.SHORT: [0, 0, 0], Term.LONG: [0, 0, 0]}
    flagged_sales: set[int] = set()
    for item in realized:
        if item.sold_on.year != tax_year:
            continue
        row = totals[item.term]
        row[0] += item.proceeds_cents
        row[1] += item.cost_basis_cents
        row[2] += item.gain_cents
        if item.possible_wash_sale:
            flagged_sales.add(item.sale_id)
    short, long_ = (TermTotals(*totals[t]) for t in (Term.SHORT, Term.LONG))
    return YearSummary(
        tax_year=tax_year,
        short_term=short,
        long_term=long_,
        total_gain_cents=short.gain_cents + long_.gain_cents,
        possible_wash_sale_count=len(flagged_sales),
    )
