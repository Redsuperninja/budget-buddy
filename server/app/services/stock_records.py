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
from app.models import (
    Account,
    StockLot,
    StockSale,
    StockSaleOrder,
    Transaction,
    TransactionKind,
)
from app.services import stock_gains as gains
from app.services.ledger.accounts import INVESTMENT_KINDS, TAX_FREE_KINDS, get_account


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
    """Any account may hold stocks. In a retirement account or HSA, sales aren't taxed: they're
    left out of the gains summary, but purchases there still count for wash sales."""
    if account_id is not None:
        get_account(session, account_id)


def check_trade_transaction(session: Session, values: dict, is_buy: bool) -> None:
    """A purchase or sale classified from a transaction: a regular one in a brokerage,
    retirement or HSA account, money out for a purchase or in for a sale, not already a stock
    trade. The trade goes in the transaction's account (``values["account_id"]`` is set)."""
    transaction_id = values.get("transaction_id")
    if transaction_id is None:
        return
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        raise not_found("transaction")
    account = get_account(session, transaction.account_id)
    if transaction.kind != TransactionKind.NORMAL or transaction.transfer_pair_id is not None:
        raise ApiError(422, "not_a_trade", "Only a regular transaction can be a stock trade.")
    if account.kind not in INVESTMENT_KINDS:
        raise ApiError(
            422,
            "not_a_trade",
            "Only transactions in a brokerage, retirement or HSA account can be stock trades.",
        )
    if (transaction.amount_cents < 0) != is_buy:
        side = "money out" if is_buy else "money in"
        what = "purchase" if is_buy else "sale"
        raise ApiError(422, "not_a_trade", f"A stock {what} has to be {side}.")
    if values.get("account_id") not in (None, transaction.account_id):
        raise ApiError(422, "not_a_trade", "The trade must be in the transaction's account.")
    linked = (
        select(StockLot.id)
        .where(StockLot.transaction_id == transaction_id)
        .union_all(select(StockSaleOrder.id).where(StockSaleOrder.transaction_id == transaction_id))
    )
    if session.execute(linked).first():
        raise ApiError(409, "already_a_trade", "This transaction is already a stock trade.")
    values["account_id"] = transaction.account_id


def untaxed_account_ids(session: Session) -> set[int]:
    """Retirement and HSA accounts: selling inside them isn't taxed."""
    return set(session.scalars(select(Account.id).where(Account.kind.in_(TAX_FREE_KINDS))))


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
