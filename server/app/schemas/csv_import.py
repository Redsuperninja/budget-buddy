import datetime as dt
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.common import Schema

# The date layouts we understand, by the name people see. The values are strptime codes.
DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "MM/DD/YYYY": "%m/%d/%Y",
    "MM/DD/YY": "%m/%d/%y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "DD/MM/YY": "%d/%m/%y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "MM-DD-YYYY": "%m-%d-%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
    "YYYYMMDD": "%Y%m%d",
    "Mon D, YYYY": "%b %d, %Y",
    "D Mon YYYY": "%d %b %Y",
}
DateFormat = Literal[tuple(DATE_FORMATS)]
Delimiter = Literal[",", ";", "\t", "|"]
Column = Annotated[int, Field(ge=0, le=199, description="Column number, counting from 0")]
HeaderRows = Annotated[
    int,
    Field(ge=0, le=20, description="Rows to skip at the top; the last one holds the column names"),
]


class CsvMapping(Schema):
    """Which column holds what. Either ``amount_column``, or ``debit_column``/``credit_column``."""

    delimiter: Delimiter = ","
    header_rows: HeaderRows = 1
    date_column: Column
    description_column: Column
    amount_column: Column | None = None
    debit_column: Column | None = None
    credit_column: Column | None = None
    date_format: DateFormat
    # Card issuers often export charges as positive numbers; flip them so money out is negative.
    flip_sign: bool = False

    @model_validator(mode="after")
    def _amount_columns(self):
        split = self.debit_column is not None or self.credit_column is not None
        if (self.amount_column is None) == (not split):
            raise ValueError(
                "Pick either one amount column, or separate money-out and money-in columns."
            )
        return self


class MappingChoices(Schema):
    """Query parameters: any part of the mapping you want to set. The rest is the saved or
    detected mapping."""

    delimiter: Delimiter | None = None
    header_rows: HeaderRows | None = None
    date_column: Column | None = None
    description_column: Column | None = None
    amount_column: Column | None = None
    debit_column: Column | None = None
    credit_column: Column | None = None
    date_format: DateFormat | None = None
    flip_sign: bool | None = None


class CommitChoices(MappingChoices):
    save_mapping: bool = False
    skip_invalid_rows: bool = False
    file_name: str | None = Field(None, max_length=200)  # for the import history


class PreviewRow(Schema):
    row_number: int  # as a spreadsheet would number it, counting the header rows
    date: dt.date | None = None
    description: str | None = None
    amount_cents: int | None = None
    status: Literal["new", "duplicate", "invalid"] = "new"
    problem: str | None = None


class ImportPreview(Schema):
    mapping: CsvMapping | None
    used_saved_mapping: bool
    message: str | None
    columns: list[str]
    sample: list[list[str]]  # the first few rows exactly as they are in the file
    total_rows: int
    new_rows: int
    duplicate_rows: int
    invalid_rows: int
    rows: list[PreviewRow]  # the first rows, plus every row with a problem (both capped)


class ImportResult(Schema):
    imported: int
    # Of the imported rows, how many an auto-categorization rule put in a category.
    categorized: int
    # Pairs linked as transfers between your accounts (a card payment, money into savings...).
    transfers_matched: int = 0
    # Dividends found (filed under "Dividends") and deposit sweeps linked to one.
    dividends_found: int = 0
    dividend_sweeps_linked: int = 0
    skipped_duplicates: int
    skipped_invalid: int
    mapping_saved: bool
