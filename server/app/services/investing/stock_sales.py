"""Stock sales and realized gains: list, add, delete, and the yearly summary.

Purchases are in ``stock_lots``; the math is in ``stock_gains``.
"""

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import StockLot, StockSale, StockSaleOrder
from app.schemas.investing.stocks import (
    GainsSummaryOut,
    RealizedOut,
    SaleCreate,
    SaleOut,
    TermTotalsOut,
)
from app.services.investing import stock_gains as gains
from app.services.investing.bank_trades import find_trades, forget_recorded, remember_symbol
from app.services.investing.holdings_check import Snapshot, checked_by, snapshots
from app.services.investing.stock_records import (
    check_account,
    check_trade_transaction,
    get_order,
    in_year,
    rematch,
    to_gains_lot,
    to_gains_sale,
    untaxed_account_ids,
)
from app.shares import micro_to_text


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
        [to_gains_lot(r) for r in lots],
        [to_gains_sale(r) for r in orders],
        [gains.Piece(p.order_id, p.lot_id, p.shares_micro, p.proceeds_cents) for p in pieces],
    )
    by_sale: dict[int, list[gains.Realized]] = {}
    for item in realized:
        by_sale.setdefault(item.sale_id, []).append(item)
    return by_sale


def _sale_out(
    order: StockSaleOrder, pieces: list[gains.Realized], taxed: bool, files: dict[int, Snapshot]
) -> SaleOut:
    """``taxed`` False for a sale inside a retirement account or HSA: no gain to report, so no
    wash-sale flag either."""
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
        possible_wash_sale=taxed and any(p.possible_wash_sale for p in pieces),
        transaction_id=order.transaction_id,
        checked_by=checked_by(
            files, order.account_id, order.symbol, order.sold_on, order.transaction_id
        ),
        taxed=taxed,
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
                possible_wash_sale=taxed and p.possible_wash_sale,
            )
            for p in pieces
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _sales_out(session: Session, orders: list[StockSaleOrder]) -> list[SaleOut]:
    realized = _realized(session, {o.symbol for o in orders})
    untaxed = untaxed_account_ids(session)
    files = snapshots(session)
    return [
        _sale_out(o, realized.get(o.id, []), o.account_id not in untaxed, files) for o in orders
    ]


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
        query = query.where(in_year(tax_year))
    orders = session.scalars(
        query.order_by(StockSaleOrder.sold_on.desc(), StockSaleOrder.id.desc())
    ).all()
    return _sales_out(session, list(orders))


def sale_out(session: Session, sale_id: int) -> SaleOut:
    return _sales_out(session, [get_order(session, sale_id)])[0]


def create_sale(session: Session, data: SaleCreate) -> SaleOut:
    values = data.model_dump(exclude={"shares", "proceeds"})
    check_trade_transaction(session, values, is_buy=False)
    check_account(session, values["account_id"])
    order = StockSaleOrder(**values)
    session.add(order)
    session.flush()
    new_id = order.id
    try:
        rematch(session, order.symbol, order.account_id)
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
    remember_symbol(
        session, values["transaction_id"], values["symbol"]
    )  # a trade from the bank file
    if values["transaction_id"] is not None:
        find_trades(session, {values["transaction_id"]})  # links its deposit sweep, if any
    session.commit()
    return sale_out(session, new_id)


def delete_sale(session: Session, sale_id: int) -> None:
    order = get_order(session, sale_id)
    symbol, account_id, transaction_id = order.symbol, order.account_id, order.transaction_id
    session.delete(order)  # its per-lot pieces go with it (ON DELETE CASCADE)
    session.flush()
    # Later sales may now be matched to older shares. Removing a sale frees up shares, so this
    # can't fail.
    rematch(session, symbol, account_id)
    forget_recorded(session, transaction_id)
    session.commit()


def gains_summary(session: Session, tax_year: int) -> GainsSummaryOut:
    """Short- and long-term totals for taxed sales dated in ``tax_year`` (not those inside a
    retirement account or HSA)."""
    untaxed = untaxed_account_ids(session)
    orders = [
        o
        for o in session.scalars(
            select(StockSaleOrder)
            .where(in_year(tax_year))
            .order_by(StockSaleOrder.sold_on, StockSaleOrder.id)
        )
        if o.account_id not in untaxed
    ]
    realized = _realized(session, {o.symbol for o in orders})
    files = snapshots(session)
    summary = gains.summarize((item for o in orders for item in realized.get(o.id, [])), tax_year)
    return GainsSummaryOut(
        tax_year=tax_year,
        short_term=TermTotalsOut(**asdict(summary.short_term)),
        long_term=TermTotalsOut(**asdict(summary.long_term)),
        total_gain_cents=summary.total_gain_cents,
        possible_wash_sale_count=summary.possible_wash_sale_count,
        sales=[_sale_out(o, realized.get(o.id, []), True, files) for o in orders],
    )
