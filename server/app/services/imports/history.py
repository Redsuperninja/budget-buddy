"""Import history: every file you imported, and undoing one.

Each import that adds something records an ``ImportBatch``; what it added (transactions, stock
purchases and sales, positions) carries its ``import_id``. Removing an import deletes those rows
in one go, all or nothing:

- A transaction's links go with it the way the database already handles them: its paycheck and
  donation links are cleared, its dividend record is deleted, and a transfer partner from another
  import (or typed in) goes back to a normal transaction it can be matched again.
- A stock trade from somewhere else that was linked to one of its transactions stays, unlinked.
- Its stock purchases and sales are deleted and every affected symbol is matched again with FIFO;
  if a sale from elsewhere needs those shares, nothing is removed (409).

Nothing here logs file names, descriptions or amounts.
"""

import unicodedata

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import (
    Account,
    ImportBatch,
    Position,
    StockLot,
    StockSale,
    StockSaleOrder,
    Transaction,
)
from app.schemas.imports.history import ImportOut
from app.services import stock_gains as gains
from app.services.combined_sweeps import free_sweeps_of
from app.services.ledger.transfers import unlink_sides
from app.services.stock_records import in_account, rematch

MAX_FILE_NAME = 200


def clean_file_name(name: str | None) -> str:
    """Printable characters only (no control or direction-changing characters, which could make
    a name show misleadingly), at most ``MAX_FILE_NAME``."""
    text = "".join(c for c in (name or "") if unicodedata.category(c) not in ("Cc", "Cf"))
    return text.strip()[:MAX_FILE_NAME]


def record(
    session: Session, kind: str, account_id: int | None, file_name: str | None, rows: int
) -> int:
    """Add an import to the history (not saved until the caller commits); returns its id."""
    batch = ImportBatch(
        kind=kind, account_id=account_id, file_name=clean_file_name(file_name), rows_added=rows
    )
    session.add(batch)
    session.flush()
    return batch.id


def list_imports(session: Session) -> list[ImportOut]:
    """Newest first."""
    rows = session.execute(
        select(ImportBatch, Account.name)
        .outerjoin(Account, Account.id == ImportBatch.account_id)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
    ).all()
    return [
        ImportOut(
            id=b.id,
            kind=b.kind,
            account_id=b.account_id,
            account_name=name,
            file_name=b.file_name,
            rows_added=b.rows_added,
            created_at=b.created_at,
        )
        for b, name in rows
    ]


def _release_partners(session: Session, import_id: int) -> None:
    """Transfer partners outside this import go back to normal transactions."""
    mine = select(Transaction.id).where(Transaction.import_id == import_id)
    partners = session.scalars(
        select(Transaction).where(
            Transaction.transfer_pair_id.in_(mine), Transaction.import_id.is_not(import_id)
        )
    )
    unlink_sides(*partners, remember=False)


def _remove_trades(session: Session, import_id: int) -> None:
    lots = session.scalars(select(StockLot).where(StockLot.import_id == import_id)).all()
    orders = session.scalars(
        select(StockSaleOrder).where(StockSaleOrder.import_id == import_id)
    ).all()
    affected = {(r.symbol, r.account_id) for r in [*lots, *orders]}
    for symbol, account_id in affected:  # FIFO pieces are rebuilt below
        order_ids = select(StockSaleOrder.id).where(
            StockSaleOrder.symbol == symbol, in_account(StockSaleOrder.account_id, account_id)
        )
        session.execute(delete(StockSale).where(StockSale.order_id.in_(order_ids)))
    session.execute(delete(StockSaleOrder).where(StockSaleOrder.import_id == import_id))
    session.execute(delete(StockLot).where(StockLot.import_id == import_id))
    session.flush()
    try:
        for symbol, account_id in sorted(affected, key=str):
            rematch(session, symbol, account_id)
    except gains.NotEnoughShares as exc:
        session.rollback()
        raise ApiError(
            409,
            "import_in_use",
            f"Your sale of {exc.sale.symbol} on {exc.sale.sold_on.isoformat()} needs shares this "
            "import added, so it can't be removed. Delete that sale first.",
        ) from None


def remove(session: Session, import_id: int) -> None:
    batch = session.get(ImportBatch, import_id)
    if batch is None:
        raise not_found("import")
    _release_partners(session, import_id)
    mine = select(Transaction.id).where(Transaction.import_id == import_id)
    for model in (StockLot, StockSaleOrder):  # trades from elsewhere keep their shares, unlinked
        session.execute(
            update(model)
            .where(model.transaction_id.in_(mine), model.import_id.is_not(import_id))
            .values(transaction_id=None)
        )
    _remove_trades(session, import_id)
    session.execute(delete(Position).where(Position.import_id == import_id))
    free_sweeps_of(session, mine)  # a sweep shared with dividends or trades from other files
    # The database clears paycheck, donation, transfer and sweep links and deletes dividends.
    session.execute(delete(Transaction).where(Transaction.import_id == import_id))
    session.delete(batch)
    session.commit()
