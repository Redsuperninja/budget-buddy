"""What goes into a backup and how it's read back (ADR-0012, docs/dev/architecture/backup.md).

A backup's contents are a tar stream, written and read without ever holding it whole:
``manifest.json`` first, then a consistent copy of ``budget.db``, ``server-id`` and every receipt
file as it is (already encrypted). Reading accepts only those names, each at most once.
"""

import io
import json
import re
import tarfile
import time
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import Engine

from app.crypto._fs import ensure_private_dir
from app.crypto.files import DEFAULT_MAX_BYTES, OVERHEAD, RECEIPTS_DIRNAME
from app.crypto.sqlcipher import is_encrypted_engine
from app.crypto.stream import (
    DAMAGED,
    DecryptingReader,
    EncryptingWriter,
    decrypted_chunks,
)
from app.db import (
    DB_FILENAME,
    FIRST_ENCRYPTED_REVISION,
    database_revision,
    make_private_file,
)
from app.services.devices.pairing_sessions import SERVER_ID_FILENAME

FORMAT = 1
MANIFEST = "manifest.json"
_RECEIPT = re.compile(rf"^{RECEIPTS_DIRNAME}/[0-9a-f]{{32}}\.bbf$")
_LIMITS = {MANIFEST: 64 * 1024, SERVER_ID_FILENAME: 1024}
_RECEIPT_LIMIT = DEFAULT_MAX_BYTES + OVERHEAD


def _clean_copy(engine: Engine, destination: Path) -> None:
    """A consistent copy with no free pages (VACUUM INTO), so text deleted long ago, or plain
    text from before encryption that wasn't scrubbed yet, can't travel in a backup."""
    with engine.connect() as connection:
        connection.exec_driver_sql("VACUUM INTO ?", (str(destination),))


def _add(tar: tarfile.TarFile, name: str, data: BinaryIO, size: int) -> None:
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = size, 0o600, int(time.time())
    tar.addfile(info, data)


def _receipt_files(data_dir: Path) -> list[Path]:
    folder = data_dir / RECEIPTS_DIRNAME
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if _RECEIPT.fullmatch(f"{RECEIPTS_DIRNAME}/{p.name}"))


# Until roadmap 25l-4 makes backups from an encrypted database, refuse instead of failing oddly.
ENCRYPTED_DATABASE_BACKUP_MESSAGE = (
    "Backups don't work yet while database encryption is turned on "
    "(BUDGET_BUDDY_DATABASE_ENCRYPTION). Turn that setting off to make a backup. "
    "Your data is safe and unchanged."
)


def write_backup(
    target: BinaryIO,
    data_dir: Path,
    engine: Engine,
    backup_key: bytes,
    fingerprint: str,
    version: str,
) -> dict:
    """Write an encrypted backup of ``data_dir`` to ``target``. Returns its manifest."""
    if is_encrypted_engine(engine):
        raise BackupError(ENCRYPTED_DATABASE_BACKUP_MESSAGE)
    copy = data_dir / f".backup-{uuid.uuid4().hex}.db"
    try:
        make_private_file(copy)  # empty and owner-only before anything is written into it
        _clean_copy(engine, copy)  # consistent, including what's still in the WAL file
        revision = database_revision(copy)
        if revision is None or (revision.isdigit() and revision < FIRST_ENCRYPTED_REVISION):
            raise BackupError(
                "Your data hasn't been updated to the encrypted format yet. Start Budget Buddy "
                "once, then make the backup."
            )
        receipts = _receipt_files(data_dir)
        manifest = {
            "format": FORMAT,
            "app_version": version,
            "database_revision": revision,
            "created": int(time.time()),
            "receipts": len(receipts),
        }
        body = json.dumps(manifest).encode("ascii")
        writer = EncryptingWriter(target, backup_key, fingerprint)
        with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            _add(tar, MANIFEST, io.BytesIO(body), len(body))
            with open(copy, "rb") as db:
                _add(tar, DB_FILENAME, db, copy.stat().st_size)
            server_id = data_dir / SERVER_ID_FILENAME
            if server_id.is_file():
                with open(server_id, "rb") as handle:
                    _add(tar, SERVER_ID_FILENAME, handle, server_id.stat().st_size)
            for receipt in receipts:
                with open(receipt, "rb") as handle:
                    _add(tar, f"{RECEIPTS_DIRNAME}/{receipt.name}", handle, receipt.stat().st_size)
        writer.close()
        return manifest
    finally:
        copy.unlink(missing_ok=True)


class BackupError(RuntimeError):
    """A backup can't be made now. The message is meant for the person."""


class BackupContentsError(ValueError):
    """The backup decrypted, but holds something a Budget Buddy backup never has."""


def _check_member(member: tarfile.TarInfo, seen: set[str]) -> None:
    name = member.name
    allowed = name in (MANIFEST, DB_FILENAME, SERVER_ID_FILENAME) or _RECEIPT.fullmatch(name)
    if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or not allowed or name in seen:
        raise BackupContentsError(DAMAGED)
    if not seen and name != MANIFEST:
        raise BackupContentsError(DAMAGED)
    limit = _LIMITS.get(name, _RECEIPT_LIMIT if name.startswith(RECEIPTS_DIRNAME) else None)
    if limit is not None and member.size > limit:
        raise BackupContentsError(DAMAGED)
    seen.add(name)


def extract_backup(
    source: BinaryIO, backup_key: bytes, salt: bytes, header: bytes, staging: Path
) -> dict:
    """Decrypt a backup (after its header) into the empty folder ``staging``. Returns the
    manifest. Raises DecryptionError or BackupContentsError; the caller deletes ``staging``."""
    reader = DecryptingReader(decrypted_chunks(source, backup_key, salt, header))
    seen: set[str] = set()
    manifest = None
    try:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for member in tar:
                _check_member(member, seen)
                data = tar.extractfile(member)
                if member.name == MANIFEST:
                    manifest = json.loads(data.read())
                    continue
                path = staging / member.name
                ensure_private_dir(path.parent)
                make_private_file(path)
                with open(path, "wb") as out:
                    while chunk := data.read(1024 * 1024):
                        out.write(chunk)
    except (tarfile.TarError, ValueError, UnicodeDecodeError) as exc:
        if isinstance(exc, BackupContentsError):
            raise
        raise BackupContentsError(DAMAGED) from exc
    reader.drain()  # the rest of the file, so a changed or extended end is caught too
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != FORMAT
        or DB_FILENAME not in seen
    ):
        raise BackupContentsError(DAMAGED)
    return manifest
