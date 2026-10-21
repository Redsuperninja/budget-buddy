"""Backups in the dashboard (roadmap 24b, ADR-0012): status, download, and a restore that
finishes at the next start. This computer only: not on the other-computers allow-list."""

import asyncio
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.backup import pending, uploads
from app.crypto import get_key_store, load_master_key, master_key_to_phrase
from app.crypto.keys import matches_fingerprint, read_fingerprint
from app.errors import ApiError
from app.schemas.backup import BackupStatus, PendingRestore, RecoveryPhrase

router = APIRouter(prefix="/api/local/backup", tags=["backup"])
_one_upload = asyncio.Lock()  # a restore upload can be gigabytes: one at a time


@router.get("")
def backup_status(request: Request) -> BackupStatus:
    data_dir = request.app.state.settings.data_dir
    restored = request.app.state.restored_from
    return BackupStatus(
        key_fingerprint=read_fingerprint(data_dir),
        pending=pending.pending(data_dir),
        restored_from=str(restored) if restored else None,
    )


@router.get("/file")
def download_backup(
    request: Request, sec_fetch_site: Annotated[str | None, Header()] = None
) -> StreamingResponse:
    # A GET has no CSRF token, so another website could ask for backups over and over: only
    # this dashboard (or the address typed in) may. Browsers always send this header.
    if sec_fetch_site not in (None, "same-origin", "none"):
        raise ApiError(403, "cross_site", "Download backups from the Budget Buddy dashboard.")
    state = request.app.state
    path = uploads.make_download(state.settings.data_dir, state.engine, state.keys)
    name = uploads.download_name(dt.date.today())  # noqa: DTZ011 (this computer's own date)
    return StreamingResponse(
        uploads.send_and_delete(path, engine=state.engine),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/restore")
async def start_restore(
    request: Request,
    x_recovery_phrase: Annotated[str | None, Header(max_length=200)] = None,
) -> PendingRestore:
    state = request.app.state
    data_dir = state.settings.data_dir
    if _one_upload.locked():
        raise ApiError(409, "restore_busy", "A backup is already being checked. Please wait.")
    async with _one_upload:
        upload = await uploads.receive_upload(request, data_dir)
        store = get_key_store(state.settings.key_store)
        info = await run_in_threadpool(
            uploads.check_upload, upload, data_dir, state.keys, store, x_recovery_phrase
        )
    return PendingRestore(**info)


@router.delete("/restore", status_code=status.HTTP_204_NO_CONTENT)
def cancel_restore(request: Request) -> Response:
    settings = request.app.state.settings
    pending.cancel(settings.data_dir, get_key_store(settings.key_store))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/recovery-phrase")
def show_recovery_phrase(request: Request, response: Response) -> RecoveryPhrase:
    """The phrase for this folder's key, read from the vault each time (roadmap 24c). A POST, so
    it needs the page's CSRF token; never cached, logged or kept in the running Home Base."""
    settings = request.app.state.settings
    key = load_master_key(get_key_store(settings.key_store), settings.data_dir)
    if key is None or matches_fingerprint(settings.data_dir, key) is False:
        raise ApiError(
            409,
            "no_recovery_phrase",
            "Budget Buddy can't find the right key in this computer's password vault, so it "
            "can't show a recovery phrase. Nothing was changed.",
        )
    response.headers["Cache-Control"] = "no-store"
    return RecoveryPhrase(phrase=master_key_to_phrase(key))
