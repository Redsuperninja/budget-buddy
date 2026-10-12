"""Stock gains math, table-driven with worked examples. Fake symbols and amounts only."""

import datetime as dt

import pytest

from app.services.investing.stock_gains import (
    WASH_SALE_WINDOW_DAYS,
    Lot,
    NotEnoughShares,
    Piece,
    Sale,
    Term,
    TermTotals,
    holding_term,
    long_term_from,
    match_fifo,
    realize,
    summarize,
)
from app.shares import micro_to_text, shares_to_micro

D = dt.date.fromisoformat
SH = 1_000_000  # one share in millionths


def lot(id, acquired, shares_micro, cost, symbol="FAKE", account=None):
    return Lot(id, symbol, account, D(acquired), shares_micro, cost)


def sale(id, sold, shares_micro, proceeds, symbol="FAKE", account=None):
    return Sale(id, symbol, account, D(sold), shares_micro, proceeds)


# --- holding period ----------------------------------------------------------------------------
# The holding period starts the day after the purchase; more than one year is long term.


@pytest.mark.parametrize(
    ("acquired", "sold", "term"),
    [
        ("2025-03-10", "2025-03-10", Term.SHORT),  # same day
        ("2025-03-10", "2026-03-10", Term.SHORT),  # exactly one year: still short
        ("2025-03-10", "2026-03-11", Term.LONG),  # one year and a day
        ("2023-12-31", "2024-12-31", Term.SHORT),  # across a leap year, exactly one year
        ("2023-12-31", "2025-01-01", Term.LONG),
        ("2025-01-31", "2026-01-31", Term.SHORT),
        ("2025-01-31", "2026-02-01", Term.LONG),
        # Bought on leap day: the period starts Mar 1, 2024 and a year runs to Feb 28, 2025.
        ("2024-02-29", "2025-02-28", Term.SHORT),
        ("2024-02-29", "2025-03-01", Term.LONG),
        # Bought Feb 28, 2024: the period starts Feb 29, 2024. 2025 has no Feb 29, so the year
        # runs through Feb 28, 2025.
        ("2024-02-28", "2025-02-28", Term.SHORT),
        ("2024-02-28", "2025-03-01", Term.LONG),
        # Bought Feb 27, 2024: period starts Feb 28, 2024, a year runs through Feb 27, 2025.
        ("2024-02-27", "2025-02-27", Term.SHORT),
        ("2024-02-27", "2025-02-28", Term.LONG),
        # Bought Feb 28, 2023: the period starts Mar 1, 2023, and a year runs through
        # Feb 29, 2024, so selling on leap day is still short term.
        ("2023-02-28", "2024-02-29", Term.SHORT),
        ("2023-02-28", "2024-03-01", Term.LONG),
        ("2020-06-15", "2026-06-15", Term.LONG),  # many years
    ],
)
def test_holding_term(acquired, sold, term):
    assert holding_term(D(acquired), D(sold)) is term


@pytest.mark.parametrize(
    ("acquired", "first_long_day"),
    [
        ("2025-03-10", "2026-03-11"),
        ("2024-02-29", "2025-03-01"),
        ("2024-02-28", "2025-03-01"),
        ("2023-02-28", "2024-03-01"),
        ("2023-02-27", "2024-02-28"),
        ("2024-12-31", "2026-01-01"),
    ],
)
def test_long_term_from(acquired, first_long_day):
    assert long_term_from(D(acquired)) == D(first_long_day)


def test_sale_before_purchase_has_no_term():
    with pytest.raises(ValueError):
        holding_term(D("2026-02-01"), D("2026-01-31"))


# --- shares as exact millionths ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "micro", "back"),
    [
        ("10", 10 * SH, "10"),
        ("2.5", 2_500_000, "2.5"),
        ("0.000001", 1, "0.000001"),
        ("1.500000", 1_500_000, "1.5"),  # extra zeros are fine
        (" 3 ", 3 * SH, "3"),
        ("0123.4", 123_400_000, "123.4"),
    ],
)
def test_shares_round_trip(text, micro, back):
    assert shares_to_micro(text) == micro
    assert micro_to_text(micro) == back


@pytest.mark.parametrize(
    "text", ["", "1.0000001", "-1", "+1", "1e3", "1,000", "1.", ".5", "abc", "1 000", "١"]
)
def test_bad_share_text(text):
    with pytest.raises(ValueError):
        shares_to_micro(text)


def test_shares_reject_floats():
    with pytest.raises(TypeError):
        shares_to_micro(1.5)
    with pytest.raises(TypeError):
        micro_to_text(1.5)


# --- FIFO matching and gains: worked examples --------------------------------------------------
# Each case: lots, sales, then the expected realized pieces as
# (sale_id, lot_id, shares_micro, proceeds_cents, cost_basis_cents, gain_cents, term).

FIFO_CASES = {
    # 10 shares bought for $1,000.00 (fees included), all sold 17 months later for $1,500.00.
    "whole lot, long term": (
        [lot(1, "2025-01-02", 10 * SH, 100_000)],
        [sale(1, "2026-06-01", 10 * SH, 150_000)],
        [(1, 1, 10 * SH, 150_000, 100_000, 50_000, Term.LONG)],
    ),
    # One sale spans two lots. Proceeds $1,050.00 for 7 shares: 5/7 = $750.00 to lot 1,
    # the rest ($300.00) to lot 2. Lot 2's cost for 2 of 5 shares = $750.00 * 2/5 = $300.00.
    # Lot 1 was held over a year (long term from 2026-01-11), lot 2 wasn't (from 2026-06-02).
    "spans two lots": (
        [lot(1, "2025-01-10", 5 * SH, 50_000), lot(2, "2025-06-01", 5 * SH, 75_000)],
        [sale(1, "2026-03-01", 7 * SH, 105_000)],
        [
            (1, 1, 5 * SH, 75_000, 50_000, 25_000, Term.LONG),
            (1, 2, 2 * SH, 30_000, 30_000, 0, Term.SHORT),
        ],
    ),
    # 3 shares for $100.00, sold one at a time. $100.00 / 3 doesn't split evenly; the cost is
    # shared out cumulatively (round(10000*1/3)=3333, round(10000*2/3)=6667, then 10000), so
    # the pieces are $33.33 + $33.34 + $33.33 = exactly $100.00.
    "partial lot sold in three parts": (
        [lot(1, "2026-01-05", 3 * SH, 10_000)],
        [
            sale(1, "2026-02-01", 1 * SH, 4_000),
            sale(2, "2026-03-01", 1 * SH, 3_000),
            sale(3, "2026-04-01", 1 * SH, 3_500),
        ],
        [
            (1, 1, SH, 4_000, 3_333, 667, Term.SHORT),
            (2, 1, SH, 3_000, 3_334, -334, Term.SHORT),
            (3, 1, SH, 3_500, 3_333, 167, Term.SHORT),
        ],
    ),
    # $1.00 for 3 shares from 3 lots: proceeds split 33 + 34 + 33 cents, nothing lost.
    "proceeds split across lots without losing a cent": (
        [
            lot(1, "2026-01-01", SH, 30),
            lot(2, "2026-01-02", SH, 30),
            lot(3, "2026-01-03", SH, 30),
        ],
        [sale(1, "2026-02-01", 3 * SH, 100)],
        [
            (1, 1, SH, 33, 30, 3, Term.SHORT),
            (1, 2, SH, 34, 30, 4, Term.SHORT),
            (1, 3, SH, 33, 30, 3, Term.SHORT),
        ],
    ),
    # Fractional shares: 0.5 share for $100.00; 0.123456 share sold for $30.00.
    # Cost = $100.00 * 0.123456 / 0.5 = $24.6912 -> $24.69.
    "fractional shares": (
        [lot(1, "2026-01-02", 500_000, 10_000)],
        [sale(1, "2026-05-01", 123_456, 3_000)],
        [(1, 1, 123_456, 3_000, 2_469, 531, Term.SHORT)],
    ),
    # Lots are given out of order (the older one was entered later): FIFO goes by date.
    "oldest purchase first, whatever order they were entered": (
        [lot(1, "2025-09-01", 5 * SH, 60_000), lot(2, "2025-02-01", 5 * SH, 40_000)],
        [sale(1, "2026-03-01", 5 * SH, 55_000)],
        [(1, 2, 5 * SH, 55_000, 40_000, 15_000, Term.LONG)],
    ),
    # Two purchases on the same day: the one entered first is sold first.
    "same-day lots in entry order": (
        [lot(2, "2026-01-02", SH, 1_000), lot(1, "2026-01-02", SH, 2_000)],
        [sale(1, "2026-02-02", SH, 1_500)],
        [(1, 1, SH, 1_500, 2_000, -500, Term.SHORT)],
    ),
    # Sales handled in date order, even if given out of order: the earlier sale gets the
    # older lot.
    "sales in date order": (
        [lot(1, "2024-01-02", 2 * SH, 2_000), lot(2, "2026-01-02", 2 * SH, 4_000)],
        [sale(2, "2026-05-01", 2 * SH, 5_000), sale(1, "2026-04-01", 2 * SH, 5_000)],
        [
            (1, 1, 2 * SH, 5_000, 2_000, 3_000, Term.LONG),
            (2, 2, 2 * SH, 5_000, 4_000, 1_000, Term.SHORT),
        ],
    ),
    # A stock that became worthless and was sold for $0: the whole cost is a loss.
    "sold for nothing": (
        [lot(1, "2026-01-02", 4 * SH, 12_345)],
        [sale(1, "2026-08-03", 4 * SH, 0)],
        [(1, 1, 4 * SH, 0, 12_345, -12_345, Term.SHORT)],
    ),
    # Each account is matched on its own; the same symbol elsewhere isn't touched.
    "separate accounts": (
        [
            lot(1, "2024-01-02", SH, 1_000, account=7),
            lot(2, "2025-01-02", SH, 2_000, account=8),
        ],
        [sale(1, "2026-04-01", SH, 3_000, account=8)],
        [(1, 2, SH, 3_000, 2_000, 1_000, Term.LONG)],
    ),
    # A purchase dated after the sale can't be used by it.
    "later purchase skipped": (
        [lot(1, "2026-01-02", SH, 1_000), lot(2, "2026-06-01", SH, 1_000)],
        [sale(1, "2026-03-01", SH, 1_200)],
        [(1, 1, SH, 1_200, 1_000, 200, Term.SHORT)],
    ),
}


@pytest.mark.parametrize(("lots", "sales", "expected"), FIFO_CASES.values(), ids=FIFO_CASES)
def test_fifo_worked_examples(lots, sales, expected):
    pieces = match_fifo(lots, sales)
    realized = realize(lots, sales, pieces)
    got = [
        (
            r.sale_id,
            r.lot_id,
            r.shares_micro,
            r.proceeds_cents,
            r.cost_basis_cents,
            r.gain_cents,
            r.term,
        )
        for r in realized
    ]
    assert got == expected
    # Money is conserved: each sale's pieces add up to its proceeds.
    for s in sales:
        assert sum(p.proceeds_cents for p in pieces if p.sale_id == s.id) == s.proceeds_cents
        assert sum(p.shares_micro for p in pieces if p.sale_id == s.id) == s.shares_micro


@pytest.mark.parametrize(
    ("lots", "sales", "short_sale_id"),
    [
        # 5 shares held, 6 sold.
        ([lot(1, "2026-01-02", 5 * SH, 500)], [sale(1, "2026-02-01", 6 * SH, 700)], 1),
        # Sold before buying (the only purchase is dated after the sale).
        ([lot(1, "2026-02-01", SH, 100)], [sale(1, "2026-01-31", SH, 100)], 1),
        # Shares are in another account.
        ([lot(1, "2026-01-02", SH, 100, account=1)], [sale(1, "2026-02-01", SH, 100)], 1),
        # Another symbol.
        ([lot(1, "2026-01-02", SH, 100, symbol="OTHER")], [sale(1, "2026-02-01", SH, 100)], 1),
        # The second sale needs shares the first already used.
        (
            [lot(1, "2026-01-02", 10 * SH, 1_000)],
            [sale(1, "2026-02-01", 6 * SH, 700), sale(2, "2026-03-01", 5 * SH, 600)],
            2,
        ),
        # One millionth of a share too many.
        ([lot(1, "2026-01-02", SH, 100)], [sale(1, "2026-02-01", SH + 1, 100)], 1),
    ],
)
def test_selling_more_than_held(lots, sales, short_sale_id):
    with pytest.raises(NotEnoughShares) as caught:
        match_fifo(lots, sales)
    assert caught.value.sale.id == short_sale_id


# --- wash sales (flag only) --------------------------------------------------------------------
# Lot 1: 10 shares bought 2025-01-02 for $1,000.00. Sold 2026-03-31 for $600.00 (a $400.00 loss).
# Lot 2 is another purchase; is it within 30 days before or after the sale?

WASH_SALE_DATE = "2026-03-31"


@pytest.mark.parametrize(
    ("other_lot", "proceeds", "flagged"),
    [
        (None, 60_000, False),  # no other purchase
        (lot(2, "2026-03-01", SH, 6_000), 60_000, True),  # 30 days before
        (lot(2, "2026-02-28", SH, 6_000), 60_000, False),  # 31 days before
        (lot(2, "2026-04-30", SH, 6_000), 60_000, True),  # 30 days after
        (lot(2, "2026-05-01", SH, 6_000), 60_000, False),  # 31 days after
        (lot(2, "2026-03-31", SH, 6_000), 60_000, True),  # same day
        (lot(2, "2026-03-15", SH, 6_000, account=9), 60_000, True),  # in another account
        (lot(2, "2026-03-15", SH, 6_000, symbol="OTHER"), 60_000, False),  # another stock
        (lot(2, "2026-03-15", SH, 6_000), 120_000, False),  # a gain, not a loss
        (lot(2, "2026-03-15", SH, 6_000), 100_000, False),  # break-even is not a loss
    ],
)
def test_wash_sale_flag(other_lot, proceeds, flagged):
    lots = [lot(1, "2025-01-02", 10 * SH, 100_000)] + ([other_lot] if other_lot else [])
    sales = [sale(1, WASH_SALE_DATE, 10 * SH, proceeds)]
    (only,) = realize(lots, sales, match_fifo(lots, sales))
    assert only.possible_wash_sale is flagged
    # Flag only: the loss and cost aren't adjusted.
    assert only.cost_basis_cents == 100_000
    assert only.gain_cents == proceeds - 100_000


def test_wash_sale_window_is_30_days():
    assert WASH_SALE_WINDOW_DAYS == 30


@pytest.mark.parametrize(
    ("bought", "sold", "flagged"),
    [
        ("2024-02-29", "2024-03-30", True),  # 30 days counting leap day
        ("2024-01-31", "2024-03-01", True),  # 30 days in a leap year (Feb has 29 days)
        ("2025-01-30", "2025-03-01", True),  # 30 days in a normal year
        ("2025-01-29", "2025-03-01", False),  # 31 days
    ],
)
def test_wash_sale_window_across_february(bought, sold, flagged):
    lots = [lot(1, "2023-01-02", SH, 10_000), lot(2, bought, SH, 5_000)]
    sales = [sale(1, sold, SH, 4_000)]
    pieces = match_fifo(lots, sales)
    assert [p.lot_id for p in pieces] == [1]
    assert realize(lots, sales, pieces)[0].possible_wash_sale is flagged


def test_selling_part_of_a_recent_purchase_at_a_loss_is_not_a_wash_sale():
    # Bought 10 shares, sold 4 of them at a loss 10 days later. The 6 left came from the same
    # purchase, so they aren't replacement shares (Rev. Rul. 56-602).
    lots = [lot(1, "2026-03-01", 10 * SH, 10_000)]
    sales = [sale(1, "2026-03-11", 4 * SH, 3_000)]
    (only,) = realize(lots, sales, match_fifo(lots, sales))
    assert (only.gain_cents, only.possible_wash_sale) == (-1_000, False)


@pytest.mark.parametrize(
    ("sold_shares", "expected"),
    [
        # Lot A: 10 shares 2026-01-02 for $1,000.00. Lot B: 10 shares 2026-03-20 for $500.00.
        # Sell 15 on 2026-03-31 for $750.00 ($50.00 a share): A's 10 shares get $500.00, a
        # $500.00 loss; B's 5 get $250.00 for $250.00 of cost (no gain). B's 5 shares left were
        # bought 11 days before, so they're replacement shares: A's loss is flagged.
        (15, [(1, -50_000, True), (2, 0, False)]),
        # Sell all 20 for $1,000.00: B is used up too, so nothing is left as a replacement.
        (20, [(1, -50_000, False), (2, 0, False)]),
    ],
)
def test_partly_used_lot_in_the_same_sale_is_a_replacement(sold_shares, expected):
    lots = [lot(1, "2026-01-02", 10 * SH, 100_000), lot(2, "2026-03-20", 10 * SH, 50_000)]
    sales = [sale(1, "2026-03-31", sold_shares * SH, sold_shares * 5_000)]
    realized = realize(lots, sales, match_fifo(lots, sales))
    assert [(r.lot_id, r.gain_cents, r.possible_wash_sale) for r in realized] == expected


def test_only_loss_pieces_are_flagged():
    # One sale uses an old cheap lot (gain) and a newer expensive lot (loss); there's also a
    # purchase 5 days after. Only the losing piece is a possible wash sale.
    lots = [
        lot(1, "2024-01-02", SH, 1_000),
        lot(2, "2026-01-02", SH, 9_000),
        lot(3, "2026-04-06", SH, 5_000),
    ]
    sales = [sale(1, "2026-04-01", 2 * SH, 10_000)]
    realized = realize(lots, sales, match_fifo(lots, sales))
    assert [(r.lot_id, r.gain_cents, r.possible_wash_sale) for r in realized] == [
        (1, 4_000, False),
        (2, -4_000, True),
    ]


# --- yearly summary ----------------------------------------------------------------------------


def test_summary_for_a_tax_year():
    lots = [
        lot(1, "2024-06-03", 10 * SH, 100_000),
        lot(2, "2025-11-03", 10 * SH, 200_000),
        lot(3, "2026-02-10", 1 * SH, 15_000),  # bought within 30 days of the loss sale
    ]
    sales = [
        sale(1, "2025-12-15", 2 * SH, 30_000),  # 2025, from lot 1: long-term gain
        sale(2, "2026-01-20", 10 * SH, 180_000),  # 8 from lot 1 (long), 2 from lot 2 (short)
        sale(3, "2026-02-20", 3 * SH, 45_000),  # from lot 2: short-term loss, wash flag
    ]
    realized = realize(lots, sales, match_fifo(lots, sales))
    # Sale 2: lot 1 gets 8/10 of $1,800.00 = $1,440.00 for 8 shares that cost $800.00.
    #         lot 2 gets $360.00 for 2 shares that cost $400.00: a $40.00 short-term loss.
    #         Lot 3 is bought 21 days after this sale, so that loss is flagged too.
    # Sale 3: 3 shares of lot 2 for $450.00 that cost $600.00: a $150.00 short-term loss.
    summary = summarize(realized, 2026)
    assert summary.long_term == TermTotals(144_000, 80_000, 64_000)
    assert summary.short_term == TermTotals(36_000 + 45_000, 40_000 + 60_000, -4_000 - 15_000)
    assert summary.total_gain_cents == 64_000 - 19_000
    assert summary.possible_wash_sale_count == 2

    last_year = summarize(realized, 2025)
    assert last_year.long_term == TermTotals(30_000, 20_000, 10_000)
    assert last_year.short_term == TermTotals()
    assert last_year.possible_wash_sale_count == 0

    assert summarize(realized, 2024).total_gain_cents == 0


def test_summary_counts_each_flagged_sale_once():
    lots = [
        lot(1, "2026-01-02", SH, 5_000),
        lot(2, "2026-01-03", SH, 5_000),
        lot(3, "2026-02-20", SH, 1_000),
    ]
    sales = [sale(1, "2026-02-01", 2 * SH, 2_000)]
    realized = realize(lots, sales, match_fifo(lots, sales))
    assert [r.possible_wash_sale for r in realized] == [True, True]
    assert summarize(realized, 2026).possible_wash_sale_count == 1


def test_piece_dataclass_is_plain_ints():
    pieces = match_fifo([lot(1, "2026-01-02", SH, 100)], [sale(1, "2026-02-01", SH, 99)])
    assert pieces == [Piece(1, 1, SH, 99)]
    assert all(type(v) is int for v in (pieces[0].shares_micro, pieces[0].proceeds_cents))
