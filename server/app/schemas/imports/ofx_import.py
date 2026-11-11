from pydantic import Field

from app.schemas.common import Schema
from app.schemas.imports.csv_import import PreviewRow


class OfxChoices(Schema):
    """Query parameters. ``statement`` picks one account in a file that holds several."""

    statement: int | None = Field(None, ge=1, le=50)
    # A card file that lists charges as positive numbers: True flips them, False keeps them as
    # they are. Left out, a file that looks backwards is held back until you choose.
    flip_sign: bool | None = None


class OfxCommitChoices(OfxChoices):
    # The first import for an account: "yes, this file is for this account" (its last 4 are saved).
    confirm_account: bool = False
    skip_invalid_rows: bool = False
    file_name: str | None = Field(None, max_length=200)  # for the import history


class OfxStatementInfo(Schema):
    number: int  # 1, 2, ... in the order they appear in the file
    last4: str  # only the last four characters of the account number
    kind: str  # the bank's word: CHECKING, SAVINGS, CREDITCARD, ...
    transactions: int


class OfxPreview(Schema):
    statements: list[OfxStatementInfo]
    chosen: int | None  # the statement number used, or None when you still have to pick one
    needs_confirmation: bool  # this account has no saved last 4 yet
    message: str | None
    problems: list[str]  # this account's lines the reader left out, in plain English
    looks_flipped: bool  # a card file that seems to have charges as positive numbers
    flip_sign: bool  # the signs are flipped in these rows (your choice)
    zero_rows: int  # lines of $0.00, left out as nothing to add
    possible_duplicate_rows: int  # new rows with the same date and amount as an existing one
    possible_duplicates: list[PreviewRow]  # those rows (capped); they are still added
    total_rows: int
    new_rows: int
    duplicate_rows: int
    invalid_rows: int
    rows: list[PreviewRow]  # the first rows, plus every row with a problem (both capped)


class OfxImportResult(Schema):
    imported: int
    categorized: int
    transfers_matched: int = 0
    dividends_found: int = 0
    dividend_sweeps_linked: int = 0
    trades_found: int = 0
    trade_sweeps_linked: int = 0
    donations_added: int = 0
    skipped_duplicates: int
    skipped_invalid: int
    skipped_zero: int = 0
    account_saved: bool  # the account's last 4 were saved from this file
