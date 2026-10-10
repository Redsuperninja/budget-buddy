"""Stock purchases (lots): list, add and delete. Sales are in ``stock_sales``."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import StockLot, StockSale, StockSaleOrder
from app.schemas.stocks import LotCreate, LotOut
from app.services import stock_gains as gains
from app.services.bank_trades import find_trades, forget_recorded, remember_symbol
from app.services.holdings_check import Snapshot, checked_by, snapshots
from app.services.stock_records import (
    check_account,
    check_trade_transaction,
    get_lot,
    in_account,
    rematch,
)
from app.shares import micro_to_text


def _sold_by_lot(session: Session, lot_ids: list[int]) -> dict[int, int]:
    rows = session.execute(
        select(StockSale.lot_id, func.sum(StockSale.shares_micro))
        .where(StockSale.lot_id.in_(lot_ids))
        .group_by(StockSale.lot_id)
    )
    return {lot_id: sold for lot_id, sold in rows}


def _lot_out(lot: StockLot, sold: dict[int, int], files: dict[int, Snapshot]) -> LotOut:
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
        transaction_id=lot.transaction_id,
        checked_by=checked_by(
            files, lot.account_id, lot.symbol, lot.acquired_on, lot.transaction_id
        ),
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
    files = snapshots(session)
    return [_lot_out(lot, sold, files) for lot in lots]


def lot_out(session: Session, lot_id: int) -> LotOut:
    lot = get_lot(session, lot_id)
    return _lot_out(lot, _sold_by_lot(session, [lot.id]), snapshots(session))


def create_lot(session: Session, data: LotCreate) -> LotOut:
    values = data.model_dump(exclude={"shares", "cost_basis"})
    check_trade_transaction(session, values, is_buy=True)
    check_account(session, values["account_id"])
    lot = StockLot(**values)
    session.add(lot)
    session.flush()
    # An earlier-dated purchase changes which shares FIFO sells first. Adding shares can never
    # make a sale short of shares, so this can't fail.
    rematch(session, lot.symbol, lot.account_id)
    remember_symbol(session, lot.transaction_id, lot.symbol)  # a trade from the bank file
    if lot.transaction_id is not None:
        # Links its deposit sweep, if there is one. (Dividends already had first pick of the
        # sweeps when the transactions were added.)
        find_trades(session, {lot.transaction_id})
    session.commit()
    return lot_out(session, lot.id)


def delete_lot(session: Session, lot_id: int) -> None:
    lot = get_lot(session, lot_id)
    symbol, account_id, transaction_id = lot.symbol, lot.account_id, lot.transaction_id
    order_ids = select(StockSaleOrder.id).where(
        StockSaleOrder.symbol == symbol, in_account(StockSaleOrder.account_id, account_id)
    )
    session.execute(delete(StockSale).where(StockSale.order_id.in_(order_ids)))
    session.delete(lot)
    session.flush()
    try:
        rematch(session, symbol, account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        raise ApiError(
            409,
            "purchase_in_use",
            f"Your sale of {exc.sale.symbol} on {exc.sale.sold_on.isoformat()} needs the shares "
            "from this purchase, so it can't be deleted. Delete that sale first.",
        ) from None
    forget_recorded(session, transaction_id)
    session.commit()
