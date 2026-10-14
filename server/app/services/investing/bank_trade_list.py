"""The Investments page's list of trades found in your bank file: when, which company, bought or
sold, the amount, and (once you've recorded it) the ticker, shares and price per share. Also "not a
trade". See ``bank_trades`` for how they're found."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Account, BankTrade, SecuritySymbol, StockLot, StockSaleOrder, Transaction
from app.models.tax import SHARES_SCALE
from app.schemas.investing.bank_trades import BankTradeOut, BankTradesOut
from app.services.investing.bank_trades import ticker_in
from app.services.investing.combined_sweeps import free_sweep

RECORDED = (
    "This trade is recorded on the Stocks page. To undo it, delete the purchase or sale there."
)


def price_per_share(amount_cents: int, shares_micro: int | None) -> int | None:
    """Cents per share, rounded half up (whole cents, no floats)."""
    if not shares_micro:
        return None
    return (amount_cents * SHARES_SCALE * 2 + shares_micro) // (shares_micro * 2)


def _recorded(session: Session, ids: list[int]) -> dict[int, tuple[str, int]]:
    """Transaction id -> (symbol, shares) of the purchase or sale recorded from it."""
    lots = select(StockLot.transaction_id, StockLot.symbol, StockLot.shares_micro).where(
        StockLot.transaction_id.in_(ids)
    )
    sales = select(
        StockSaleOrder.transaction_id, StockSaleOrder.symbol, StockSaleOrder.shares_micro
    ).where(StockSaleOrder.transaction_id.in_(ids))
    return {row[0]: (row[1], row[2]) for row in session.execute(lots.union_all(sales))}


def list_trades(session: Session) -> BankTradesOut:
    rows = session.execute(
        select(BankTrade, Transaction, Account.name)
        .join(Transaction, Transaction.id == BankTrade.transaction_id)
        .join(Account, Account.id == Transaction.account_id)
        .where(BankTrade.dismissed.is_(False))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
    ).all()
    recorded = _recorded(session, [t.id for _, t, _ in rows])
    symbols = dict(session.execute(select(SecuritySymbol.security, SecuritySymbol.symbol)).all())
    items = []
    for trade, paid, account_name in rows:
        amount = abs(paid.amount_cents)
        symbol, shares = recorded.get(paid.id, (None, None))
        items.append(
            BankTradeOut(
                id=trade.id,
                transaction_id=paid.id,
                sweep_transaction_id=trade.sweep_transaction_id,
                date=paid.date,
                account_id=paid.account_id,
                account_name=account_name,
                security=trade.security,
                side="buy" if paid.amount_cents < 0 else "sell",
                amount_cents=amount,
                recorded=symbol is not None,
                symbol=symbol,
                shares_micro=shares,
                price_cents=price_per_share(amount, shares),
                suggested_symbol=symbols.get(trade.security) or ticker_in(paid.description),
            )
        )
    return BankTradesOut(items=items)


def dismiss(session: Session, trade_id: int) -> None:
    """Not a trade: leave it (and its sweep) to be counted like any other transaction, and never
    find it again."""
    trade = session.get(BankTrade, trade_id)
    if trade is None:
        raise not_found("trade")
    if _recorded(session, [trade.transaction_id]):
        raise ApiError(409, "trade_recorded", RECORDED)
    trade.dismissed = True
    free_sweep(session, trade.sweep_transaction_id)  # from every trade or dividend sharing it
    trade.sweep_transaction_id = None
    session.commit()
