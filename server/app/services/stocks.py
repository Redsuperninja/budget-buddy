"""Stock purchases (lots), sales, and realized gains. The math is in ``stock_gains``.

A sale is stored as entered (``StockSaleOrder``) plus one ``StockSale`` row per lot it used.
Those per-lot rows are rebuilt with FIFO for the whole symbol and account every time a purchase
or sale there is added or removed, so a purchase entered late (with an earlier date) still gets
sold first, the way FIFO requires.
"""

import datetime as dt
from dataclasses import asdict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import StockLot, StockSale, StockSaleOrder
from app.schemas.stocks import (
    WASH_SALE_LIMITS,
    GainsSummaryOut,
    LotCreate,
    LotOut,
    RealizedOut,
    SaleCreate,
    SaleOut,
    TermTotalsOut,
)
from app.services import stock_gains as gains
from app.services.accounts import TAX_FREE_KINDS, get_account
from app.shares import micro_to_text


def _lot(row: StockLot) -> gains.Lot:
    return gains.Lot(
        row.id, row.symbol, row.account_id, row.acquired_on, row.shares_micro, row.cost_basis_cents
    )


def _sale(row: StockSaleOrder) -> gains.Sale:
    return gains.Sale(
        row.id, row.symbol, row.account_id, row.sold_on, row.shares_micro, row.proceeds_cents
    )


def _in_account(column, account_id: int | None):
    return column.is_(None) if account_id is None else column == account_id


def _in_year(tax_year: int):
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


def _check_account(session: Session, account_id: int | None) -> None:
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


def _rematch(session: Session, symbol: str, account_id: int | None) -> None:
    """Rebuild the per-lot pieces of every sale of ``symbol`` in this account with FIFO.

    Raises ``gains.NotEnoughShares`` (and leaves the session to be rolled back) if a sale needs
    more shares than were held.
    """
    lots = session.scalars(
        select(StockLot).where(
            StockLot.symbol == symbol, _in_account(StockLot.account_id, account_id)
        )
    ).all()
    orders = session.scalars(
        select(StockSaleOrder).where(
            StockSaleOrder.symbol == symbol, _in_account(StockSaleOrder.account_id, account_id)
        )
    ).all()
    pieces = gains.match_fifo([_lot(r) for r in lots], [_sale(r) for r in orders])
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


# --- lots ----------------------------------------------------------------------------------


def _sold_by_lot(session: Session, lot_ids: list[int]) -> dict[int, int]:
    rows = session.execute(
        select(StockSale.lot_id, func.sum(StockSale.shares_micro))
        .where(StockSale.lot_id.in_(lot_ids))
        .group_by(StockSale.lot_id)
    )
    return {lot_id: sold for lot_id, sold in rows}


def _lot_out(lot: StockLot, sold: dict[int, int]) -> LotOut:
    remaining = lot.shares_micro - sold.get(lot.id, 0)
    return LotOut(
        id=lot.id,
        account_id=lot.account_id,
        symbol=lot.symbol,
        acquired_on=lot.acquired_on,
        shares_micro=lot.shares_micro,
        shares=micro_to_text(lot.shares_micro),
        cost_basis_cents=lot.cost_basis_cents,
        remaining_shares_micro=remaining,
        remaining_shares=micro_to_text(remaining),
        long_term_from=gains.long_term_from(lot.acquired_on),
        created_at=lot.created_at,
        updated_at=lot.updated_at,
    )


def list_lots(session: Session, symbol: str | None, account_id: int | None) -> list[LotOut]:
    """Oldest purchase first (the order FIFO sells them in)."""
    query = select(StockLot)
    if symbol:
        query = query.where(StockLot.symbol == symbol.strip().upper())
    if account_id is not None:
        query = query.where(StockLot.account_id == account_id)
    lots = session.scalars(query.order_by(StockLot.symbol, StockLot.acquired_on, StockLot.id)).all()
    sold = _sold_by_lot(session, [lot.id for lot in lots])
    return [_lot_out(lot, sold) for lot in lots]


def lot_out(session: Session, lot_id: int) -> LotOut:
    lot = get_lot(session, lot_id)
    return _lot_out(lot, _sold_by_lot(session, [lot.id]))


def create_lot(session: Session, data: LotCreate) -> LotOut:
    values = data.model_dump(exclude={"shares", "cost_basis"})
    _check_account(session, values["account_id"])
    lot = StockLot(**values)
    session.add(lot)
    session.flush()
    # An earlier-dated purchase changes which shares FIFO sells first. Adding shares can never
    # make a sale short of shares, so this can't fail.
    _rematch(session, lot.symbol, lot.account_id)
    session.commit()
    return lot_out(session, lot.id)


def delete_lot(session: Session, lot_id: int) -> None:
    lot = get_lot(session, lot_id)
    symbol, account_id = lot.symbol, lot.account_id
    order_ids = select(StockSaleOrder.id).where(
        StockSaleOrder.symbol == symbol, _in_account(StockSaleOrder.account_id, account_id)
    )
    session.execute(delete(StockSale).where(StockSale.order_id.in_(order_ids)))
    session.delete(lot)
    session.flush()
    try:
        _rematch(session, symbol, account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        raise ApiError(
            409,
            "purchase_in_use",
            f"Your sale of {exc.sale.symbol} on {exc.sale.sold_on.isoformat()} needs the shares "
            "from this purchase, so it can't be deleted. Delete that sale first.",
        ) from None
    session.commit()


# --- sales ---------------------------------------------------------------------------------


def _realized(session: Session, symbols: set[str]) -> dict[int, list[gains.Realized]]:
    """``{sale_id: [pieces]}`` for every sale of these symbols. Lots of the symbol in every
    account are loaded, since a purchase anywhere can flag a possible wash sale."""
    if not symbols:
        return {}
    lots = session.scalars(select(StockLot).where(StockLot.symbol.in_(symbols))).all()
    orders = session.scalars(select(StockSaleOrder).where(StockSaleOrder.symbol.in_(symbols))).all()
    pieces = session.scalars(
        select(StockSale).where(StockSale.order_id.in_([o.id for o in orders]))
    ).all()
    realized = gains.realize(
        [_lot(r) for r in lots],
        [_sale(r) for r in orders],
        [gains.Piece(p.order_id, p.lot_id, p.shares_micro, p.proceeds_cents) for p in pieces],
    )
    by_sale: dict[int, list[gains.Realized]] = {}
    for item in realized:
        by_sale.setdefault(item.sale_id, []).append(item)
    return by_sale


def _sale_out(order: StockSaleOrder, pieces: list[gains.Realized]) -> SaleOut:
    return SaleOut(
        id=order.id,
        account_id=order.account_id,
        symbol=order.symbol,
        sold_on=order.sold_on,
        shares_micro=order.shares_micro,
        shares=micro_to_text(order.shares_micro),
        proceeds_cents=order.proceeds_cents,
        cost_basis_cents=sum(p.cost_basis_cents for p in pieces),
        gain_cents=sum(p.gain_cents for p in pieces),
        possible_wash_sale=any(p.possible_wash_sale for p in pieces),
        lots=[
            RealizedOut(
                lot_id=p.lot_id,
                acquired_on=p.acquired_on,
                shares_micro=p.shares_micro,
                shares=micro_to_text(p.shares_micro),
                proceeds_cents=p.proceeds_cents,
                cost_basis_cents=p.cost_basis_cents,
                gain_cents=p.gain_cents,
                term=p.term,
                possible_wash_sale=p.possible_wash_sale,
            )
            for p in pieces
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _sales_out(session: Session, orders: list[StockSaleOrder]) -> list[SaleOut]:
    realized = _realized(session, {o.symbol for o in orders})
    return [_sale_out(o, realized.get(o.id, [])) for o in orders]


def list_sales(
    session: Session, symbol: str | None, account_id: int | None, tax_year: int | None
) -> list[SaleOut]:
    """Newest sale first."""
    query = select(StockSaleOrder)
    if symbol:
        query = query.where(StockSaleOrder.symbol == symbol.strip().upper())
    if account_id is not None:
        query = query.where(StockSaleOrder.account_id == account_id)
    if tax_year is not None:
        query = query.where(_in_year(tax_year))
    orders = session.scalars(
        query.order_by(StockSaleOrder.sold_on.desc(), StockSaleOrder.id.desc())
    ).all()
    return _sales_out(session, list(orders))


def sale_out(session: Session, sale_id: int) -> SaleOut:
    return _sales_out(session, [get_order(session, sale_id)])[0]


def create_sale(session: Session, data: SaleCreate) -> SaleOut:
    values = data.model_dump(exclude={"shares", "proceeds"})
    _check_account(session, values["account_id"])
    order = StockSaleOrder(**values)
    session.add(order)
    session.flush()
    new_id = order.id
    try:
        _rematch(session, order.symbol, order.account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        short = exc.sale
        if short.id == new_id:
            message = (
                f"You're selling more shares of {short.symbol} than you owned on "
                f"{short.sold_on.isoformat()}. Only purchases in the same account, dated on or "
                "before the sale, count. Check the number of shares and the date, or add the "
                "missing purchase first."
            )
        else:
            message = (
                f"This sale would leave your later sale of {short.symbol} on "
                f"{short.sold_on.isoformat()} selling more shares than you owned. Check the "
                "number of shares and the date, or add the missing purchase first."
            )
        raise ApiError(422, "not_enough_shares", message) from None
    session.commit()
    return sale_out(session, new_id)


def delete_sale(session: Session, sale_id: int) -> None:
    order = get_order(session, sale_id)
    symbol, account_id = order.symbol, order.account_id
    session.delete(order)  # its per-lot pieces go with it (ON DELETE CASCADE)
    session.flush()
    # Later sales may now be matched to older shares. Removing a sale frees up shares, so this
    # can't fail.
    _rematch(session, symbol, account_id)
    session.commit()


# --- yearly summary --------------------------------------------------------------------------


def gains_summary(session: Session, tax_year: int) -> GainsSummaryOut:
    """Short- and long-term totals for sales dated in ``tax_year``."""
    orders = list(
        session.scalars(
            select(StockSaleOrder)
            .where(_in_year(tax_year))
            .order_by(StockSaleOrder.sold_on, StockSaleOrder.id)
        ).all()
    )
    realized = _realized(session, {o.symbol for o in orders})
    summary = gains.summarize((item for o in orders for item in realized.get(o.id, [])), tax_year)
    return GainsSummaryOut(
        tax_year=tax_year,
        short_term=TermTotalsOut(**asdict(summary.short_term)),
        long_term=TermTotalsOut(**asdict(summary.long_term)),
        total_gain_cents=summary.total_gain_cents,
        possible_wash_sale_count=summary.possible_wash_sale_count,
        sales=[_sale_out(o, realized.get(o.id, [])) for o in orders],
    )
