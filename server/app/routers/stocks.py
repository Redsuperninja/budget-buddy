from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.deps import PathId, QueryId, SessionDep
from app.schemas.price_feed import PriceFeedIn, PriceFeedOut, RefreshResult
from app.schemas.stock_holdings import HoldingsOut, PriceIn
from app.schemas.stocks import GainsSummaryOut, LotCreate, LotOut, SaleCreate, SaleOut
from app.services import price_feed, stock_holdings, stock_lots, stock_sales

router = APIRouter(prefix="/api/local/stocks", tags=["stocks"])

SymbolFilter = Annotated[str | None, Query(max_length=16, description="Stock symbol, e.g. VTI")]
TaxYear = Annotated[int, Path(ge=2000, le=2100)]


@router.get("/lots")
def list_lots(
    session: SessionDep, symbol: SymbolFilter = None, account_id: QueryId = None
) -> list[LotOut]:
    return stock_lots.list_lots(session, symbol, account_id)


@router.post("/lots", status_code=status.HTTP_201_CREATED)
def create_lot(data: LotCreate, session: SessionDep) -> LotOut:
    return stock_lots.create_lot(session, data)


@router.get("/lots/{lot_id}")
def get_lot(lot_id: PathId, session: SessionDep) -> LotOut:
    return stock_lots.lot_out(session, lot_id)


@router.delete("/lots/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lot(lot_id: PathId, session: SessionDep) -> None:
    stock_lots.delete_lot(session, lot_id)


@router.get("/sales")
def list_sales(
    session: SessionDep,
    symbol: SymbolFilter = None,
    account_id: QueryId = None,
    tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> list[SaleOut]:
    return stock_sales.list_sales(session, symbol, account_id, tax_year)


@router.post("/sales", status_code=status.HTTP_201_CREATED)
def create_sale(data: SaleCreate, session: SessionDep) -> SaleOut:
    return stock_sales.create_sale(session, data)


@router.get("/sales/{sale_id}")
def get_sale(sale_id: PathId, session: SessionDep) -> SaleOut:
    return stock_sales.sale_out(session, sale_id)


@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(sale_id: PathId, session: SessionDep) -> None:
    stock_sales.delete_sale(session, sale_id)


@router.get("/gains/{tax_year}")
def gains_summary(tax_year: TaxYear, session: SessionDep) -> GainsSummaryOut:
    """Estimated realized gains for sales dated in one tax year, split short / long term."""
    return stock_sales.gains_summary(session, tax_year)


@router.get("/holdings")
def holdings(session: SessionDep) -> HoldingsOut:
    """Shares held now in each account, what they cost, and their value at your latest prices."""
    return stock_holdings.holdings(session)


@router.post("/prices", status_code=status.HTTP_204_NO_CONTENT)
def set_price(data: PriceIn, session: SessionDep) -> None:
    """Save the latest price of a symbol (per share), replacing the one before."""
    stock_holdings.set_price(session, data)


@router.get("/price-feed")
def price_feed_settings(session: SessionDep) -> PriceFeedOut:
    return price_feed.settings(session)


@router.put("/price-feed")
def save_price_feed(data: PriceFeedIn, session: SessionDep) -> PriceFeedOut:
    """Turn live prices on or off, and save or remove the Finnhub key (never sent back)."""
    return price_feed.save_settings(session, data)


@router.post("/prices/refresh")
def refresh_prices(session: SessionDep) -> RefreshResult:
    """Fetch the latest prices of the symbols you hold, if live prices are on (ADR-0010)."""
    return price_feed.refresh(session)
