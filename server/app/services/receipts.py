"""Receipts: details (shop, date, total) plus an optional photo kept encrypted on disk.

The photo file and the database row are kept in step like this:

- Saving a photo writes the new encrypted file first, then commits the row pointing at it. If the
  commit fails, the new file is deleted again. Only after the commit is any old photo deleted.
- Deleting a receipt (or its photo) commits the row change first, then deletes the file.

So a crash can only ever leave an extra, unused encrypted file behind, never a receipt pointing
at a missing photo. :func:`remove_orphan_files` clears those leftovers when the Home Base starts.

Never log a merchant, an amount, or a photo's contents. File IDs are random and safe to log.
"""

import logging
import time

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.crypto import DecryptionError, EncryptedFileStore
from app.crypto.files import FILE_SUFFIX
from app.db import SessionLocal
from app.errors import ApiError, not_found
from app.models import Category, Receipt, Transaction
from app.schemas.receipts import ReceiptCreate, ReceiptPage, ReceiptUpdate
from app.services.receipt_images import ImageKind, clean_image, detect_kind

logger = logging.getLogger(__name__)

# Leftover files younger than this are left alone, in case a save is still finishing.
ORPHAN_MIN_AGE_SECONDS = 60 * 60


def get_receipt(session: Session, receipt_id: int) -> Receipt:
    receipt = session.get(Receipt, receipt_id)
    if receipt is None:
        raise not_found("receipt")
    return receipt


def _check_references(session: Session, data: dict) -> None:
    if data.get("category_id") is not None and session.get(Category, data["category_id"]) is None:
        raise not_found("category")
    if (
        data.get("transaction_id") is not None
        and session.get(Transaction, data["transaction_id"]) is None
    ):
        raise not_found("transaction")


def list_receipts(session: Session, limit: int, offset: int) -> ReceiptPage:
    """Newest first (by date, then most recently added)."""
    total = session.scalar(select(func.count(Receipt.id)))
    items = session.scalars(
        select(Receipt).order_by(Receipt.date.desc(), Receipt.id.desc()).limit(limit).offset(offset)
    ).all()
    return ReceiptPage.model_validate(
        {"items": items, "total": total, "limit": limit, "offset": offset}
    )


def create_receipt(
    session: Session,
    store: EncryptedFileStore,
    data: ReceiptCreate,
    image: bytes | None = None,
) -> Receipt:
    """Add a receipt, optionally with its photo in the same step (phone uploads, #15)."""
    values = data.model_dump()
    _check_references(session, values)
    cleaned = clean_image(image)[0] if image is not None else None  # before anything is saved
    receipt = Receipt(**values)
    session.add(receipt)
    return _commit_with_image(session, store, receipt, cleaned)


def update_receipt(session: Session, receipt_id: int, data: ReceiptUpdate) -> Receipt:
    receipt = get_receipt(session, receipt_id)
    changes = data.changes()
    _check_references(session, changes)
    for field, value in changes.items():
        setattr(receipt, field, value)
    session.commit()
    return receipt


def delete_receipt(session: Session, store: EncryptedFileStore, receipt_id: int) -> None:
    receipt = get_receipt(session, receipt_id)
    old_file = receipt.image_path
    session.delete(receipt)
    session.commit()
    _discard(store, old_file)


def set_image(
    session: Session, store: EncryptedFileStore, receipt_id: int, image: bytes
) -> Receipt:
    """Add or replace a receipt's photo. A bad upload raises ``ImageRejected``."""
    receipt = get_receipt(session, receipt_id)
    cleaned, _kind = clean_image(image)
    return _commit_with_image(session, store, receipt, cleaned)


def remove_image(session: Session, store: EncryptedFileStore, receipt_id: int) -> Receipt:
    receipt = get_receipt(session, receipt_id)
    old_file = receipt.image_path
    receipt.image_path = None
    session.commit()
    _discard(store, old_file)
    return receipt


def load_image(store: EncryptedFileStore, receipt: Receipt) -> tuple[bytes, ImageKind]:
    """The decrypted photo and its type (read again from its bytes, not stored anywhere)."""
    if receipt.image_path is None:
        raise ApiError(404, "no_image", "This receipt doesn't have a photo.")
    try:
        data = store.load(receipt.image_path)
    except (FileNotFoundError, ValueError) as exc:
        raise ApiError(
            404, "image_missing", "This receipt's photo file is missing from the data folder."
        ) from exc
    except DecryptionError as exc:
        raise ApiError(
            500,
            "image_unreadable",
            "This receipt's photo couldn't be decrypted. The file may have been changed or "
            "damaged.",
        ) from exc
    kind = detect_kind(data)
    if kind is None:
        raise ApiError(500, "image_unreadable", "This receipt's photo isn't in a known format.")
    return data, kind


def _commit_with_image(
    session: Session, store: EncryptedFileStore, receipt: Receipt, image: bytes | None
) -> Receipt:
    old_file = receipt.image_path
    new_file = store.save(image) if image is not None else None
    try:
        if new_file is not None:
            receipt.image_path = new_file
        session.commit()
    except BaseException:
        session.rollback()
        _discard(store, new_file)
        raise
    if new_file is not None:
        _discard(store, old_file)
    return receipt


def _discard(store: EncryptedFileStore, file_id: str | None) -> None:
    """Delete a photo file the database no longer points at. A failure only leaves a leftover."""
    if file_id is None:
        return
    try:
        store.delete(file_id)
    except (OSError, ValueError):
        logger.warning(
            "An old receipt photo file couldn't be deleted. It's encrypted, and Budget Buddy "
            "will try to remove it again the next time it starts."
        )


def remove_orphan_files(
    engine: Engine, store: EncryptedFileStore, *, min_age_seconds: int = ORPHAN_MIN_AGE_SECONDS
) -> int:
    """Delete encrypted photo files (and half-written temp files) no receipt points at.

    Conservative: only files named like the store's own files are touched, only once they're at
    least ``min_age_seconds`` old, and nothing at all is deleted if any receipt's file reference
    can't be decrypted. Returns how many files were removed.
    """
    if not store.directory.is_dir():
        return 0
    try:
        with SessionLocal(bind=engine) as session:
            referenced = set(
                session.scalars(select(Receipt.image_path).where(Receipt.image_path.is_not(None)))
            )
    except DecryptionError:
        logger.warning("Skipped cleaning up old receipt photo files: a reference couldn't be read.")
        return 0
    cutoff = time.time() - min_age_seconds
    removed = 0
    for path in store.directory.iterdir():
        if not _is_orphan(store, path.name, referenced):
            continue
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("Removed %d unused receipt photo file(s).", removed)
    return removed


def _is_orphan(store: EncryptedFileStore, name: str, referenced: set[str]) -> bool:
    if name.startswith(".") and name.endswith(".tmp"):  # a save that never finished
        return True
    if not name.endswith(FILE_SUFFIX):
        return False
    file_id = name.removesuffix(FILE_SUFFIX)
    try:
        store.path_for(file_id)  # only the store's own random-ID names
    except ValueError:
        return False
    return file_id not in referenced
