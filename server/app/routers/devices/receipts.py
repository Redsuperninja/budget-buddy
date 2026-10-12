from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.crypto import EncryptedFileStore
from app.deps import Offset, PathId, SessionDep
from app.errors import ApiError
from app.schemas.devices.receipts import ReceiptCreate, ReceiptOut, ReceiptPage, ReceiptUpdate
from app.services.devices import receipts as service
from app.services.devices.receipt_images import MAX_IMAGE_BYTES, ImageRejected, too_large

router = APIRouter(prefix="/api/local/receipts", tags=["receipts"])


def _store(request: Request) -> EncryptedFileStore:
    return request.app.state.receipt_store


StoreDep = Annotated[EncryptedFileStore, Depends(_store)]


async def _image_body(request: Request) -> bytes:
    """The raw request body, read in pieces and cut off as soon as it's over the limit."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise _rejected(too_large())
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_IMAGE_BYTES:
            raise _rejected(too_large())
    return bytes(body)


def _rejected(exc: ImageRejected) -> ApiError:
    return ApiError(413 if exc.reason == "image_too_large" else 422, exc.reason, exc.message)


@router.get("")
def list_receipts(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> ReceiptPage:
    return service.list_receipts(session, limit, offset)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_receipt(data: ReceiptCreate, session: SessionDep, store: StoreDep) -> ReceiptOut:
    return service.create_receipt(session, store, data)


@router.get("/{receipt_id}")
def get_receipt(receipt_id: PathId, session: SessionDep) -> ReceiptOut:
    return service.get_receipt(session, receipt_id)


@router.patch("/{receipt_id}")
def update_receipt(receipt_id: PathId, data: ReceiptUpdate, session: SessionDep) -> ReceiptOut:
    return service.update_receipt(session, receipt_id, data)


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(receipt_id: PathId, session: SessionDep, store: StoreDep) -> None:
    service.delete_receipt(session, store, receipt_id)


@router.put("/{receipt_id}/image")
def put_image(
    receipt_id: PathId,
    image: Annotated[bytes, Depends(_image_body)],
    session: SessionDep,
    store: StoreDep,
) -> ReceiptOut:
    """Send the photo's bytes as the request body (not a form). JPEG, PNG or HEIC, up to 3 MB."""
    try:
        return service.set_image(session, store, receipt_id, image)
    except ImageRejected as exc:
        raise _rejected(exc) from None


@router.get("/{receipt_id}/image")
def get_image(
    receipt_id: PathId, session: SessionDep, store: StoreDep, download: bool = False
) -> Response:
    data, kind = service.load_image(store, service.get_receipt(session, receipt_id))
    # The name is built from the ID only: no shop name, and nothing a user typed.
    disposition = "attachment" if download else "inline"
    filename = f"receipt-{receipt_id}.{kind.extension}"
    return Response(
        content=data,
        media_type=kind.mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/{receipt_id}/image")
def delete_image(receipt_id: PathId, session: SessionDep, store: StoreDep) -> ReceiptOut:
    return service.remove_image(session, store, receipt_id)
