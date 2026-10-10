"""Stock trades found in a bank-style file (services/bank_trades.py), under /stocks so a joined
computer or phone may see them like the rest of the Stocks pages."""

from fastapi import APIRouter, status

from app.deps import PathId, SessionDep
from app.schemas.bank_trades import BankTradesFound, BankTradesOut
from app.services import bank_trade_list as service
from app.services.bank_trades import find_trades
from app.services.dividend_matching import find_dividends

router = APIRouter(prefix="/api/local/stocks/bank-trades", tags=["stocks"])


@router.get("")
def list_trades(session: SessionDep) -> BankTradesOut:
    """Trades found in your transactions, newest first; ticker, shares and price once recorded."""
    return service.list_trades(session)


@router.post("/find")
def find(session: SessionDep) -> BankTradesFound:
    """Look through every transaction for trades and their sweeps (dividends first)."""
    find_dividends(session)
    found = find_trades(session)
    session.commit()
    return BankTradesFound(found=found.trades, sweeps_linked=found.sweeps)


@router.post("/{trade_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(trade_id: PathId, session: SessionDep) -> None:
    """Not a trade: count it (and its sweep) like any other transaction from now on."""
    service.dismiss(session, trade_id)
