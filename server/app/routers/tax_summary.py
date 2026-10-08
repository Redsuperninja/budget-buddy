from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.deps import SessionDep
from app.schemas.tax_summary import TaxSummary
from app.services import tax_export, tax_summary

router = APIRouter(prefix="/api/local/tax-summary", tags=["tax summary"])

TaxYear = Annotated[int, Path(ge=2000, le=2100)]


@router.get("/{tax_year}")
def get_tax_summary(tax_year: TaxYear, session: SessionDep) -> TaxSummary:
    """Pay, donations, stock gains and other deductions for one tax year. Not tax advice."""
    return tax_summary.build(session, tax_year)


@router.get("/{tax_year}/export.csv")
def export_tax_summary(tax_year: TaxYear, session: SessionDep) -> Response:
    """The same year as a CSV file to open in a spreadsheet or give to a tax preparer."""
    filename = f"budget-buddy-taxes-{tax_year}.csv"
    return Response(
        content=tax_export.export_csv(session, tax_year),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
