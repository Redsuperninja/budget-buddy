from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.deps import PathId, QueryId, SessionDep
from app.schemas.stocks import GainsSummaryOut, LotCreate, LotOut, SaleCreate, SaleOut
from app.services import stocks as service

router = APIRouter(prefix="/api/local/stocks", tags=["stocks"])

SymbolFilter = Annotated[str | None, Query(max_length=16, description="Stock symbol, e.g. VTI")]
TaxYear = Annotated[int, Path(ge=2000, le=2100)]


@router.get("/lots")
def list_lots(
    session: SessionDep, symbol: SymbolFilter = None, account_id: QueryId = None
) -> list[LotOut]:
    return service.list_lots(session, symbol, account_id)


@router.post("/lots", status_code=status.HTTP_201_CREATED)
def create_lot(data: LotCreate, session: SessionDep) -> LotOut:
    return service.create_lot(session, data)


@router.get("/lots/{lot_id}")
def get_lot(lot_id: PathId, session: SessionDep) -> LotOut:
    return service.lot_out(session, lot_id)


@router.delete("/lots/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lot(lot_id: PathId, session: SessionDep) -> None:
    service.delete_lot(session, lot_id)


@router.get("/sales")
def list_sales(
    session: SessionDep,
    symbol: SymbolFilter = None,
    account_id: QueryId = None,
    tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> list[SaleOut]:
    return service.list_sales(session, symbol, account_id, tax_year)


@router.post("/sales", status_code=status.HTTP_201_CREATED)
def create_sale(data: SaleCreate, session: SessionDep) -> SaleOut:
    return service.create_sale(session, data)


@router.get("/sales/{sale_id}")
def get_sale(sale_id: PathId, session: SessionDep) -> SaleOut:
    return service.sale_out(session, sale_id)


@router.delete("/sales/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sale(sale_id: PathId, session: SessionDep) -> None:
    service.delete_sale(session, sale_id)


@router.get("/gains/{tax_year}")
def gains_summary(tax_year: TaxYear, session: SessionDep) -> GainsSummaryOut:
    """Estimated realized gains for sales dated in one tax year, split short / long term."""
    return service.gains_summary(session, tax_year)
