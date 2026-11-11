"""Turning one OFX account's transactions into preview rows (see ``ofx_import``).

Each row gets a fingerprint (account + the bank's ``FITID``) for the duplicate check. Zero-amount
lines are counted and left out ("nothing to add"). New rows that look like something already in the
account (same day and amount) are listed as possible duplicates, for banks that give every download
fresh IDs. Nothing here logs descriptions or amounts.
"""

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.schemas.imports.csv_import import PreviewRow
from app.services.imports.ofx_parsing import OfxStatement

NO_DESCRIPTION = "(no description)"
CHANGED = "This transaction is already here with a different amount (it may have been edited)."
OVERLAP_NOTE = (
    "This account already has imported transactions for these dates that aren't from this file "
    "(an earlier bank file, or a CSV file). The same purchases may show up twice: Budget Buddy "
    "can only match a bank file to its own earlier downloads."
)
SIGNS_DIFFER = (
    "This transaction is already here with the opposite sign: this file's signs differ from "
    "the earlier import. Try flipping the signs."
)
_CHUNK = 500


@dataclass
class RowSet:
    rows: list[tuple[PreviewRow, str | None]] = field(default_factory=list)
    zero: int = 0
    overlap: bool = False
    possible: list[PreviewRow] = field(default_factory=list)


def fingerprint(account_id: int, fitid: str) -> str:
    return hashlib.sha256(json.dumps(["ofx1", account_id, fitid]).encode()).hexdigest()


def _existing(session: Session, fps: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for start in range(0, len(fps), _CHUNK):
        part = fps[start : start + _CHUNK]
        found.update(
            session.execute(
                select(Transaction.import_fingerprint, Transaction.amount_cents).where(
                    Transaction.import_fingerprint.in_(part)
                )
            ).all()
        )
    return found


def build_rows(
    session: Session, account_id: int, statement: OfxStatement, flip: bool = False
) -> RowSet:
    out = RowSet()
    for t in statement.transactions:
        if t.cents == 0:
            out.zero += 1
            continue
        row = PreviewRow(
            row_number=t.position,
            date=t.posted,
            description=t.description or NO_DESCRIPTION,
            amount_cents=-t.cents if flip else t.cents,
        )
        out.rows.append((row, fingerprint(account_id, t.fitid)))
    known = _existing(session, [fp for _, fp in out.rows if fp])
    for row, fp in out.rows:
        if fp in known and known[fp] == row.amount_cents:
            row.status = "duplicate"
        elif fp in known and known[fp] == -row.amount_cents:
            row.status, row.problem = "invalid", SIGNS_DIFFER
        elif fp in known:  # same ID, other amount: maybe edited here. Flag it, never merge
            row.status, row.problem = "invalid", CHANGED
    new = [r for r, _ in out.rows if r.status == "new"]
    if new:
        dates = [r.date for r in new]
        mine = {fp for _, fp in out.rows}
        rows = session.execute(
            select(
                Transaction.date, Transaction.amount_cents, Transaction.import_fingerprint
            ).where(
                Transaction.account_id == account_id,
                Transaction.date.between(min(dates), max(dates)),
            )
        ).all()
        out.overlap = any(fp is not None and fp not in mine for _, _, fp in rows)
        seen = {(d, c) for d, c, _ in rows}
        out.possible = [r for r in new if (r.date, r.amount_cents) in seen]
    return out
