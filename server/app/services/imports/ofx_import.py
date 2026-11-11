"""Bank and card OFX/QFX import: read the file, match it to the account, preview, then add rows.

Same path as the CSV import after parsing (``csv_import``): ordinary ("normal") transactions with
``source = "csv"`` (the one value for "from an imported file"), auto-sorted by the category rules,
then dividends, stock trades, transfers and repeat gifts. The bank's own ``FITID`` is the
duplicate check: ``import_fingerprint`` is a hash of the account and the ID, so a second import of
the same file, or of an overlapping one, adds nothing. OFX amounts already have money out as
negative, for cards too. A card file that looks backwards is held until the user chooses to flip it
(``ofx_signs``). Nothing here logs file contents, account numbers,
descriptions or amounts (ADR-0016).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import AccountKind, CategorySource, Transaction, TransactionKind, TransactionSource
from app.schemas.imports.csv_import import PreviewRow
from app.schemas.imports.ofx_import import (
    OfxChoices,
    OfxCommitChoices,
    OfxImportResult,
    OfxPreview,
    OfxStatementInfo,
)
from app.services.budget.category_rules import load_matcher, rule_fields
from app.services.imports import ofx_parsing as parsing
from app.services.imports.csv_import import import_conflict
from app.services.imports.history import record
from app.services.imports.ofx_rows import OVERLAP_NOTE, RowSet, build_rows
from app.services.imports.ofx_signs import FLIPPED, file_looks_flipped
from app.services.investing.bank_trades import find_trades
from app.services.investing.dividend_matching import find_dividends
from app.services.ledger.accounts import get_account
from app.services.ledger.transfer_matching import match_transfers
from app.services.tax.repeat_gifts import repeat_gifts

PREVIEW_ROWS = 50
MAX_PROBLEM_ROWS = 100
_DIGITS = re.compile(r"[0-9]{4}")


@dataclass
class _Prepared:
    statements: list[parsing.OfxStatement]
    chosen: int | None  # 1-based
    problems: list[str]  # the chosen account's own notes
    rows: list[tuple[PreviewRow, str | None]]  # each row with its fingerprint
    needs_confirmation: bool
    extra: RowSet = field(default_factory=RowSet)
    flip: bool = False  # the card's signs are flipped (the user's choice)
    looks_flipped: bool = False  # a card file that seems backwards and no choice made yet


def _mismatch(file_last4: str, saved: str) -> ApiError:
    return ApiError(
        422,
        "wrong_account",
        f"This file is for the account ending {file_last4}, but this account is saved as ending "
        f"{saved}. Choose the matching account, or correct the last four digits in this "
        "account's settings.",
    )


def _choose(account, statements, number: int | None) -> int | None:
    """The statement to import (1-based), or None when several fit and the user must pick."""
    saved = account.last4
    if number is not None:
        if not 1 <= number <= len(statements):
            raise ApiError(422, "no_such_statement", "That account isn't in this file.")
        if saved and statements[number - 1].last4 != saved:
            raise _mismatch(statements[number - 1].last4, saved)
        return number
    fits = [i for i, s in enumerate(statements, 1) if not saved or s.last4 == saved]
    if not fits:
        shown = ", ".join(sorted({s.last4 for s in statements}))
        raise _mismatch(shown, saved)
    return fits[0] if len(fits) == 1 else None


def _pick_message(account, statements) -> str:
    ends = ", ".join(f"{i}: ending {s.last4}" for i, s in enumerate(statements, 1))
    which = "More than one account in this file fits" if account.last4 else "This file has"
    return f"{which} more than one account ({ends}). Choose which one to import."


def _prepare(session: Session, account_id: int, data: bytes, choices: OfxChoices) -> _Prepared:
    account = get_account(session, account_id)
    try:
        file = parsing.parse_ofx(data)
    except parsing.OfxError as error:
        raise ApiError(400, "unreadable_file", str(error)) from None
    statements = [s for s in file.statements if s.last4]
    chosen = _choose(account, statements, choices.statement)
    if chosen is None:
        return _Prepared(statements, None, [], [], False)
    statement = statements[chosen - 1]
    card = account.kind == AccountKind.CREDIT_CARD or statement.kind == "CREDITCARD"
    suspect = card and choices.flip_sign is None and file_looks_flipped(statement.transactions)
    flip = choices.flip_sign is True
    if flip and not card:
        raise ApiError(
            422,
            "flip_not_for_this_account",
            "Flipping signs is only for credit card files. This account's file already lists "
            "money out as negative, so it can't be flipped.",
        )
    extra = build_rows(session, account_id, statement, flip)
    return _Prepared(
        statements, chosen, statement.problems, extra.rows, not account.last4, extra, flip, suspect
    )


def _left_out(problems: list[str]) -> list[str]:
    return [p for p in problems if not p.startswith("The statement balance")]


def preview(session: Session, account_id: int, data: bytes, choices: OfxChoices) -> OfxPreview:
    p = _prepare(session, account_id, data, choices)
    account = get_account(session, account_id)
    rows = [r for r, _ in p.rows]
    counts = Counter(r.status for r in rows)
    problems = [r for r in rows[PREVIEW_ROWS:] if r.status == "invalid"][:MAX_PROBLEM_ROWS]
    notes: list[str] = []
    if p.chosen is None:
        notes.append(_pick_message(account, p.statements))
    if p.needs_confirmation and p.chosen:
        last4 = p.statements[p.chosen - 1].last4
        notes.append(
            f"This account has no saved account digits yet. Importing will save {last4} (the "
            "last four digits of the number in this file) and check later files against it."
        )
    if p.looks_flipped:
        notes.append(FLIPPED)
    if p.extra.overlap:
        notes.append(OVERLAP_NOTE)
    if p.extra.possible:
        n = len(p.extra.possible)
        notes.append(
            f"{n} new transaction{'s look' if n != 1 else ' looks'} like "
            "something already in this account (same date and amount). They will still be added."
        )
    return OfxPreview(
        statements=[
            OfxStatementInfo(number=i, last4=s.last4, kind=s.kind, transactions=len(s.transactions))
            for i, s in enumerate(p.statements, 1)
        ],
        chosen=p.chosen,
        needs_confirmation=p.needs_confirmation,
        message=" ".join(notes) or None,
        problems=_left_out(p.problems),
        looks_flipped=p.looks_flipped,
        flip_sign=p.flip,
        zero_rows=p.extra.zero,
        possible_duplicate_rows=len(p.extra.possible),
        possible_duplicates=p.extra.possible[:PREVIEW_ROWS],
        total_rows=len(rows) + p.extra.zero,
        new_rows=counts["new"],
        duplicate_rows=counts["duplicate"],
        invalid_rows=counts["invalid"],
        rows=rows[:PREVIEW_ROWS] + problems,
    )


def commit(session: Session, account_id: int, data: bytes, choices: OfxCommitChoices):
    """Add every new row in one database transaction: all of them, or none."""
    p = _prepare(session, account_id, data, choices)
    if p.chosen is None:
        account = get_account(session, account_id)
        raise ApiError(422, "choose_statement", _pick_message(account, p.statements))
    last4 = p.statements[p.chosen - 1].last4
    if p.needs_confirmation and not choices.confirm_account:
        raise ApiError(
            422,
            "confirm_account",
            f"This account has no saved account digits yet. Please confirm that this file "
            f"(account ending {last4}) belongs to it.",
        )
    if p.needs_confirmation and not _DIGITS.fullmatch(last4):
        raise ApiError(
            422,
            "account_digits",
            "This file's account number doesn't end in four digits, so it can't be saved. "
            "Use a file from the bank's download for a numbered account.",
        )
    if p.looks_flipped:
        raise ApiError(
            422,
            "choose_card_signs",
            "This card's file seems to list charges as positive numbers, which would import "
            "your purchases as money in. Look at the preview and choose whether to flip them.",
        )
    invalid = [r.row_number for r, _ in p.rows if r.status == "invalid"]
    left_out = _left_out(p.problems)
    if (invalid or left_out) and not choices.skip_invalid_rows:
        count = len(invalid) + len(left_out)
        raise ApiError(
            422,
            "invalid_rows",
            f"{count} transaction{'s' if count != 1 else ''} in this file couldn't be used. "
            "Look at the preview, or choose to skip them.",
        )
    new = [(r, fp) for r, fp in p.rows if r.status == "new"]
    import_id = record(session, "bank", account_id, choices.file_name, len(new)) if new else None
    match = load_matcher(session)
    added = [
        Transaction(
            account_id=account_id,
            date=r.date,
            amount_cents=r.amount_cents,
            description=r.description,
            **rule_fields(match(r.description)),
            source=TransactionSource.CSV,
            kind=TransactionKind.NORMAL,
            import_fingerprint=fp,
            import_id=import_id,
        )
        for r, fp in new
    ]
    session.add_all(added)
    account = get_account(session, account_id)
    saved_now = p.needs_confirmation
    if saved_now:
        account.last4 = last4
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise import_conflict() from None
    ids = {t.id for t in added}
    dividends = find_dividends(session, ids)
    trades = find_trades(session, ids)
    matched = match_transfers(session, ids)
    gifts = repeat_gifts(session, ids)
    session.commit()
    return OfxImportResult(
        imported=len(new),
        transfers_matched=matched,
        dividends_found=dividends.dividends,
        dividend_sweeps_linked=dividends.sweeps,
        donations_added=gifts.recorded,
        trades_found=trades.trades,
        trade_sweeps_linked=trades.sweeps,
        categorized=sum(t.category_source == CategorySource.RULE for t in added),
        skipped_duplicates=sum(r.status == "duplicate" for r, _ in p.rows),
        skipped_invalid=len(invalid) + len(left_out),
        skipped_zero=p.extra.zero,
        account_saved=saved_now,
    )
