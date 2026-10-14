"""Phone receipt uploads: ``POST /api/sync/receipts`` (sync contract §3.7, §6).

Each item in a batch is checked and saved on its own, so one bad photo never fails the rest.
Nothing here logs receipt details, amounts, or photo bytes; rejections use fixed plain text.
"""

import datetime as dt
import re

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.crypto.b64url import b64u_decode
from app.models import Category, Receipt
from app.money import MAX_ABS_CENTS
from app.schemas.devices.receipts import ReceiptCreate
from app.services.devices import envelope
from app.services.devices import phones as device_service
from app.services.devices.envelope import bad_data
from app.services.devices.receipt_images import MAX_IMAGE_BYTES, ImageRejected, jpeg_size
from app.services.devices.receipts import create_receipt
from app.services.devices.sync_context import SyncContext

MAX_RECEIPTS_PER_BATCH = 5
MAX_PIXELS = 16_000_000
MAX_SIDE = 4096
# Longest base64url text a 3 MiB image can have; longer is refused before decoding it.
MAX_IMAGE_TEXT = (MAX_IMAGE_BYTES * 4 + 2) // 3 + 1

_UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_DEDUCTION_KINDS = ("donation", "medical", "business", "other")
DEFAULT_MERCHANT = "Receipt from phone"


class _Rejected(Exception):
    def __init__(self, reason: str, message: str) -> None:
        self.reason, self.message = reason, message


def _invalid_field(message: str = "Some details on this receipt couldn't be read.") -> _Rejected:
    return _Rejected("invalid_field", message)


def receipts_endpoint(ctx: SyncContext, data: object) -> dict:
    """Save a batch of up to five receipts. Each item gets its own result (§6.3)."""
    items = data.get("receipts") if isinstance(data, dict) else None
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_RECEIPTS_PER_BATCH:
        raise bad_data()
    for item in items:
        client_id = item.get("client_id") if isinstance(item, dict) else None
        if not isinstance(client_id, str) or not _UUID4.fullmatch(client_id):
            raise bad_data()  # without an ID there is nothing to answer about
    return {"results": [_save_one(ctx, item) for item in items]}


def _save_one(ctx: SyncContext, item: dict) -> dict:
    client_id = item["client_id"]
    session = ctx.session
    known = _already_saved(ctx, client_id)
    if known is not None:
        return known
    try:
        values, image = _read_upload(item)
        warnings: list[str] = []
        if (
            values["category_id"] is not None
            and session.get(Category, values["category_id"]) is None
        ):
            values["category_id"] = None
            warnings.append("unknown_category")
        try:
            create = ReceiptCreate(**values["create"] | {"category_id": values["category_id"]})
        except ValidationError:
            raise _invalid_field() from None
        try:
            receipt = create_receipt(
                session,
                ctx.store,
                create,
                image,
                client_id=client_id,
                deduction_kind=values["deduction_kind"],
                device_id=ctx.device.id,
                # A phone removed mid-batch stops here (plaintext 401). Receipts saved earlier in
                # the same batch stay: they were accepted while the phone was still paired.
                before_commit=lambda: device_service.ensure_active(session, ctx.device.id),
            )
        except ImageRejected as exc:
            raise _Rejected(exc.reason, exc.message) from None
        except IntegrityError:  # the same ID arrived a moment ago from somewhere else
            session.rollback()
            known = _already_saved(ctx, client_id)
            if known is None:
                raise
            return known
    except _Rejected as rejected:
        return {
            "client_id": client_id,
            "status": "rejected",
            "reason": rejected.reason,
            "message": rejected.message,
        }
    result = {"client_id": client_id, "status": "accepted", "receipt_id": receipt.id}
    if warnings:
        result["warnings"] = warnings
    return result


def _already_saved(ctx: SyncContext, client_id: str) -> dict | None:
    """The answer for an ID the Home Base has seen, or ``None`` if it's new.

    The same phone gets ``duplicate`` (first upload wins, even if the details differ). Another
    phone using the ID gets a plain ``rejected`` and learns nothing about the receipt.
    """
    row = ctx.session.execute(
        select(Receipt.id, Receipt.device_id).where(Receipt.client_id == client_id)
    ).first()
    if row is None:
        return None
    if row.device_id == ctx.device.id:
        return {"client_id": client_id, "status": "duplicate", "receipt_id": row.id}
    rejected = _invalid_field()
    return {
        "client_id": client_id,
        "status": "rejected",
        "reason": rejected.reason,
        "message": rejected.message,
    }


def _text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise _invalid_field()
    return value.strip() or None


def _read_upload(item: dict) -> tuple[dict, bytes]:
    """Check one ReceiptUpload's fields and photo. Raises ``_Rejected`` for a bad item."""
    captured = item.get("captured_at")
    try:
        moment = dt.datetime.fromisoformat(captured) if isinstance(captured, str) else None
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:  # the contract wants a Z or an offset
        raise _invalid_field()

    total = item.get("total_cents")
    if total is not None and (not envelope.is_int(total) or not 0 <= total < MAX_ABS_CENTS):
        raise _invalid_field()
    category_id = item.get("category_id")
    if category_id is not None and (not envelope.is_int(category_id) or category_id < 1):
        raise _invalid_field()
    deductible = item.get("tax_deductible", False)
    kind = item.get("deduction_kind")
    if not isinstance(deductible, bool) or (kind is not None and kind not in _DEDUCTION_KINDS):
        raise _invalid_field()

    merchant = _text(item.get("merchant"), 100)
    values = {
        "category_id": category_id,
        "deduction_kind": (kind or "other") if deductible else None,
        "create": {
            "date": moment.date(),  # the day shown on the phone when the photo was taken
            "merchant": merchant or DEFAULT_MERCHANT,
            "total_cents": 0 if total is None else total,
            "tax_deductible": deductible,
            "notes": _text(item.get("note"), 500),
        },
    }
    return values, _read_image(item.get("image"))


def _read_image(image: object) -> bytes:
    """The photo's bytes, after the checks that don't need the whole picture (§6.1)."""
    too_big = _Rejected("image_too_large", "This photo is too big to send. Please take it again.")
    bad = _Rejected("image_invalid", "This photo couldn't be read. Please take it again.")
    if not isinstance(image, dict) or image.get("mime") != "image/jpeg":
        raise bad
    text = image.get("data")
    if not isinstance(text, str):
        raise bad
    if len(text) > MAX_IMAGE_TEXT:
        raise too_big
    try:
        photo = b64u_decode(text)
    except ValueError:
        raise bad from None
    if len(photo) > MAX_IMAGE_BYTES:
        raise too_big
    if not photo.startswith(b"\xff\xd8\xff"):
        raise bad
    size = jpeg_size(photo)
    if size is None:
        raise bad
    width, height = size
    if width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
        raise too_big
    return photo
