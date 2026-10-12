"""What every ``/api/sync/*`` endpoint is handed once its request has been opened and checked."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.crypto import EncryptedFileStore
from app.models import Device


@dataclass
class SyncContext:
    session: Session
    device: Device
    store: EncryptedFileStore
    now: int
    server_id: str


# An endpoint gets the context and the request's decrypted ``data``; it returns the reply's data.
Endpoint = Callable[[SyncContext, object], dict]
