"""The yearly tax summary as a CSV file for a spreadsheet or a tax preparer (roadmap #13).

One row per item: the year's pay-stub totals, each donation, each part of each stock sale (one per
purchase lot it came from), and each other deduction, then the disclaimer. Amounts are plain
dollars ("1234.56", losses negative). Any text that a spreadsheet could run as a formula gets a
leading apostrophe ("CSV injection"). Nothing is logged.
"""

import csv
import datetime as dt
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Donation, DonationKind
from app.services import deductions
from app.services.investing import stock_sales
from app.services.tax_summary import build
from app.spreadsheet import formula_safe

HEADER = ["Section", "Item", "Date", "Amount ($)", "Notes"]


def dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(cents), 100)
    return f"{sign}{whole}.{rest:02d}"


def _date(value: dt.date | None) -> str:
    return value.isoformat() if value else ""


def _rows(session: Session, year: int) -> list[list[str]]:
    summary = build(session, year)
    rows = [
        ["Pay (year totals)", line.label, "", dollars(line.amount_cents), ""]
        for line in summary.pay
    ]
    gifts = session.scalars(
        select(Donation)
        .where(Donation.date >= dt.date(year, 1, 1), Donation.date <= dt.date(year, 12, 31))
        .order_by(Donation.date, Donation.id)
    )
    for gift in gifts:
        item = f"{gift.organization} ({'cash' if gift.kind == DonationKind.CASH else 'goods'})"
        rows.append(["Donation", item, _date(gift.date), dollars(gift.amount_cents), ""])
    for sale in stock_sales.gains_summary(session, year).sales:
        for piece in sale.lots:
            item = f"{sale.symbol}: {piece.shares} shares bought {piece.acquired_on.isoformat()}"
            note = (
                f"{piece.term} term; proceeds {dollars(piece.proceeds_cents)}; "
                f"cost basis {dollars(piece.cost_basis_cents)}"
                + ("; possible wash sale" if piece.possible_wash_sale else "")
            )
            gain = dollars(piece.gain_cents)
            rows.append(["Stock sale gain or loss", item, _date(sale.sold_on), gain, note])
    for d in deductions.list_deductions(session, year):
        item = deductions.label(d.kind) + (f": {d.description}" if d.description else "")
        rows.append(
            [
                "Other deduction",
                item,
                _date(d.date),
                dollars(d.amount_cents),
                deductions.hint(d.kind),
            ]
        )
    rows.append(["Note", summary.disclaimer, "", "", ""])
    return [[formula_safe(cell) if i in (1, 4) else cell for i, cell in enumerate(r)] for r in rows]


def export_csv(session: Session, year: int) -> bytes:
    """The file's bytes: UTF-8 with a byte-order mark so Excel shows accents correctly."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(HEADER)
    writer.writerows(_rows(session, year))
    return out.getvalue().encode("utf-8-sig")
