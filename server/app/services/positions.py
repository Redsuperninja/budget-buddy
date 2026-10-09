"""Positions from a broker's positions file: a snapshot of what one account held on a day.

Importing replaces the account's earlier snapshot. Positions never change purchases, sales or
gains; the Investments page shows them next to what your recorded purchases and sales add up
to, so a missing trade stands out. A price in the file becomes the symbol's latest price
(source "file") unless a price from a later day, or a live price from the same day, is already
saved. The file's date can't be in the future. Reading the file is in
``positions_csv``. Nothing here logs file contents, symbols or amounts.
"""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Account, ImportBatch, Position, StockLot, StockPrice, StockSaleOrder
from app.schemas.positions import (
    AccountPositionsOut,
    PositionOut,
    PositionPreviewRow,
    PositionsChoices,
    PositionsOut,
    PositionsPreview,
    PositionsResult,
)
from app.services.accounts import get_account
from app.services.csv_parsing import decode_csv, detect_delimiter, read_rows
from app.services.imports import record
from app.services.positions_csv import ParsedPosition, Skip, find_columns, parse_position
from app.services.stock_holdings import value_cents
from app.shares import micro_to_text

MAX_SKIPPED_SHOWN = 100


@dataclass
class _Prepared:
    columns: dict[str, int]
    positions: list[ParsedPosition]  # one per symbol
    skipped: list[PositionPreviewRow]


def _add(a: int | None, b: int | None) -> int | None:
    return None if a is None or b is None else a + b


def _prepare(session: Session, data: bytes, choices: PositionsChoices) -> _Prepared:
    get_account(session, choices.account_id)
    text = decode_csv(data)
    rows = read_rows(text, detect_delimiter(text))
    header, columns = find_columns(rows)
    by_symbol: dict[str, ParsedPosition] = {}
    skipped = []
    for number, row in enumerate(rows[header + 1 :], start=header + 2):
        if not any(c.strip() for c in row):
            continue
        try:
            p = parse_position(row, number, columns)
        except Skip as reason:
            skipped.append(
                PositionPreviewRow(row_number=number, status="skipped", problem=str(reason))
            )
            continue
        same = by_symbol.get(p.symbol)
        if same:  # the same symbol on several lines (lots listed one by one): add them up
            same.shares_micro += p.shares_micro
            same.cost_basis_cents = _add(same.cost_basis_cents, p.cost_basis_cents)
            same.value_cents = _add(same.value_cents, p.value_cents)
            same.price_cents = p.price_cents or same.price_cents
        else:
            by_symbol[p.symbol] = p
    return _Prepared(columns, list(by_symbol.values()), skipped)


def _row(p: ParsedPosition) -> PositionPreviewRow:
    return PositionPreviewRow(
        row_number=p.row_number,
        symbol=p.symbol,
        shares=micro_to_text(p.shares_micro),
        cost_basis_cents=p.cost_basis_cents,
        value_cents=p.value_cents,
        price_cents=p.price_cents,
    )


def preview(session: Session, data: bytes, choices: PositionsChoices) -> PositionsPreview:
    p = _prepare(session, data, choices)
    return PositionsPreview(
        columns=p.columns,
        positions=len(p.positions),
        skipped=len(p.skipped),
        rows=[_row(x) for x in p.positions] + p.skipped[:MAX_SKIPPED_SHOWN],
    )


def _save_price(session: Session, symbol: str, price_cents: int, choices: PositionsChoices) -> bool:
    price = session.get(StockPrice, symbol)
    if price is not None and (
        price.as_of > choices.as_of or (price.as_of == choices.as_of and price.source == "feed")
    ):
        return False  # a later price, or a live one from the same day, is already saved
    price = price or StockPrice(symbol=symbol)
    price.price_cents, price.as_of = price_cents, choices.as_of
    price.source, price.fetched_at = "file", None
    session.add(price)
    return True


def commit(session: Session, data: bytes, choices: PositionsChoices) -> PositionsResult:
    """Replace the account's snapshot with this file's positions, all at once."""
    p = _prepare(session, data, choices)
    session.execute(delete(Position).where(Position.account_id == choices.account_id))
    # The earlier file for this account is replaced, so it leaves the import history too.
    session.execute(
        delete(ImportBatch).where(
            ImportBatch.kind == "positions", ImportBatch.account_id == choices.account_id
        )
    )
    import_id = record(
        session, "positions", choices.account_id, choices.file_name, len(p.positions)
    )
    session.add_all(
        Position(
            account_id=choices.account_id,
            symbol=x.symbol,
            shares_micro=x.shares_micro,
            cost_basis_cents=x.cost_basis_cents,
            value_cents=x.value_cents,
            as_of=choices.as_of,
            import_id=import_id,
        )
        for x in p.positions
    )
    prices = sum(
        _save_price(session, x.symbol, x.price_cents, choices)
        for x in p.positions
        if x.price_cents is not None
    )
    session.commit()
    return PositionsResult(
        positions=len(p.positions), prices_updated=prices, skipped=len(p.skipped)
    )


def _recorded_shares(session: Session, position: Position) -> int:
    """Shares bought minus shares sold in the position's account, dated on or before the file's
    day, so a trade recorded after the file doesn't look missing."""
    bought = session.scalar(
        select(func.coalesce(func.sum(StockLot.shares_micro), 0)).where(
            StockLot.account_id == position.account_id,
            StockLot.symbol == position.symbol,
            StockLot.acquired_on <= position.as_of,
        )
    )
    sold = session.scalar(
        select(func.coalesce(func.sum(StockSaleOrder.shares_micro), 0)).where(
            StockSaleOrder.account_id == position.account_id,
            StockSaleOrder.symbol == position.symbol,
            StockSaleOrder.sold_on <= position.as_of,
        )
    )
    return bought - sold


def list_positions(session: Session) -> PositionsOut:
    prices = {p.symbol: p.price_cents for p in session.scalars(select(StockPrice))}
    rows = session.execute(
        select(Position, Account.name)
        .join(Account, Account.id == Position.account_id)
        .order_by(Account.name, Position.symbol)
    ).all()
    accounts: dict[int, AccountPositionsOut] = {}
    for position, name in rows:
        group = accounts.setdefault(
            position.account_id,
            AccountPositionsOut(
                account_id=position.account_id,
                account_name=name,
                as_of=position.as_of,
                positions=[],
                value_cents=0,
            ),
        )
        value = position.value_cents
        if value is None and position.symbol in prices:
            value = value_cents(position.shares_micro, prices[position.symbol])
        mine = _recorded_shares(session, position)
        group.positions.append(
            PositionOut(
                symbol=position.symbol,
                shares_micro=position.shares_micro,
                shares=micro_to_text(position.shares_micro),
                cost_basis_cents=position.cost_basis_cents,
                value_cents=value,
                recorded_shares_micro=mine,
                matches=mine == position.shares_micro,
            )
        )
        group.value_cents = _add(group.value_cents, value)
    return PositionsOut(accounts=list(accounts.values()))


def clear(session: Session, account_id: int) -> None:
    get_account(session, account_id)
    session.execute(delete(Position).where(Position.account_id == account_id))
    session.commit()
