"""Shared pieces of the stock lots and sales code: lookups, filters and the FIFO rebuild.

A sale is stored as entered (``StockSaleOrder``) plus one ``StockSale`` row per lot it used.
Those per-lot rows are rebuilt with FIFO for the whole symbol and account every time a purchase
or sale there is added or removed (``rematch``), so a purchase entered late (with an earlier
date) still gets sold first, the way FIFO requires. The math is in ``stock_gains``.
"""

import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import StockLot, StockSale, StockSaleOrder
from app.schemas.stocks import WASH_SALE_LIMITS
from app.services import stock_gains as gains
from app.services.accounts import TAX_FREE_KINDS, get_account


def to_gains_lot(row: StockLot) -> gains.Lot:
    return gains.Lot(
        row.id, row.symbol, row.account_id, row.acquired_on, row.shares_micro, row.cost_basis_cents
    )


def to_gains_sale(row: StockSaleOrder) -> gains.Sale:
    return gains.Sale(
        row.id, row.symbol, row.account_id, row.sold_on, row.shares_micro, row.proceeds_cents
    )


def in_account(column, account_id: int | None):
    return column.is_(None) if account_id is None else column == account_id


def in_year(tax_year: int):
    """Sales dated in ``tax_year``: gains count in the year of the sale (trade) date."""
    return StockSaleOrder.sold_on.between(dt.date(tax_year, 1, 1), dt.date(tax_year, 12, 31))


def get_lot(session: Session, lot_id: int) -> StockLot:
    lot = session.get(StockLot, lot_id)
    if lot is None:
        raise not_found("stock purchase")
    return lot


def get_order(session: Session, sale_id: int) -> StockSaleOrder:
    order = session.get(StockSaleOrder, sale_id)
    if order is None:
        raise not_found("stock sale")
    return order


def check_account(session: Session, account_id: int | None) -> None:
    if account_id is None:
        return
    if get_account(session, account_id).kind in TAX_FREE_KINDS:
        raise ApiError(
            422,
            "tax_free_account",
            "Sales inside a retirement account or HSA aren't taxed, so there's nothing to track "
            "here. Pick a regular brokerage account, or leave the account empty. "
            + WASH_SALE_LIMITS,
        )


def rematch(session: Session, symbol: str, account_id: int | None) -> None:
    """Rebuild the per-lot pieces of every sale of ``symbol`` in this account with FIFO.

    Raises ``gains.NotEnoughShares`` (and leaves the session to be rolled back) if a sale needs
    more shares than were held.
    """
    lots = session.scalars(
        select(StockLot).where(
            StockLot.symbol == symbol, in_account(StockLot.account_id, account_id)
        )
    ).all()
    orders = session.scalars(
        select(StockSaleOrder).where(
            StockSaleOrder.symbol == symbol, in_account(StockSaleOrder.account_id, account_id)
        )
    ).all()
    pieces = gains.match_fifo([to_gains_lot(r) for r in lots], [to_gains_sale(r) for r in orders])
    sold_on = {order.id: order.sold_on for order in orders}
    if orders:
        session.execute(delete(StockSale).where(StockSale.order_id.in_([o.id for o in orders])))
    session.add_all(
        StockSale(
            order_id=piece.sale_id,
            lot_id=piece.lot_id,
            sold_on=sold_on[piece.sale_id],
            shares_micro=piece.shares_micro,
            proceeds_cents=piece.proceeds_cents,
        )
        for piece in pieces
    )
    session.flush()
