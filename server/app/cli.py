"""Command-line tools: ``python -m app recovery-phrase show|restore``, ``backup make|restore``."""

import argparse
import getpass
import sys
from collections.abc import Callable
from pathlib import Path

from app.backup.restore import RestoreError
from app.config import Settings
from app.crypto import (
    EncryptionError,
    RecoveryPhraseError,
    get_key_store,
    key_name_for,
    master_key_to_phrase,
    phrase_to_master_key,
)
from app.crypto.keys import (
    WRONG_KEY_MESSAGE,
    fingerprint,
    load_master_key,
    matches_fingerprint,
    read_fingerprint,
    write_fingerprint,
)
from app.db import DatabaseUpgradeError

Output = Callable[[str], None]
Input = Callable[[str], str]

SHOW_WARNING = """\
YOUR RECOVERY PHRASE

This phrase is the key to all of your Budget Buddy data. With it, you can get your data back
if this computer's password vault is lost (for example after reinstalling Windows).

  * Write it on paper, or save it in a password manager.
  * Keep it private: anyone with this phrase AND a copy of your data folder can read your data.
  * Don't save it in the Budget Buddy data folder, and don't email or text it.
  * Budget Buddy can't show it to anyone else or reset it for you.
"""

RESTORE_INTRO = """\
RESTORE FROM RECOVERY PHRASE

This puts your saved recovery phrase back into this computer's password vault, so Budget Buddy
can read your data folder again:

  {data_dir}

Type the phrase exactly as you saved it (16 groups of 4 letters and numbers). Dashes, spaces,
and lowercase are fine. For privacy, what you type won't appear on the screen.
"""

NOT_A_TERMINAL_MESSAGE = (
    "The recovery phrase is only shown in a terminal window, so it doesn't end up saved in a "
    "file or a log. Run this command directly in a terminal, without redirecting its output. "
    "(If you really want it written to a file, add --force.)"
)


def _stdout_is_terminal() -> bool:
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):  # replaced or closed stdout
        return False


def _read_hidden(prompt: str) -> str:
    """Read the phrase without echoing it, so it doesn't stay in the terminal's scrollback."""
    return getpass.getpass(prompt)


def show_phrase(
    settings: Settings, output: Output = print, ask: Input = input, force: bool = False
) -> int:
    if not force and not _stdout_is_terminal():
        output(NOT_A_TERMINAL_MESSAGE)
        return 1
    store = get_key_store(settings.key_store)
    key = load_master_key(store, settings.data_dir)
    if key is None:
        output(
            f"There's no encryption key yet for {settings.data_dir}. Start Budget Buddy once "
            "(python -m app) and then run this again."
        )
        return 1
    if matches_fingerprint(settings.data_dir, key) is False:
        # Don't let anyone write down a phrase that won't open their data.
        output(WRONG_KEY_MESSAGE.format(data_dir=settings.data_dir))
        return 1
    output(SHOW_WARNING)
    answer = ask(
        "Make sure nobody else can see your screen. Type SHOW to display your recovery phrase, "
        "or press Enter to cancel: "
    )
    if answer.strip() != "SHOW":  # only an exact SHOW; anything else (even "yes") cancels
        output("Cancelled. Nothing was shown.")
        return 1
    output("")
    output("    " + master_key_to_phrase(key))
    output("")
    output("When you've saved it, clear this window (or close it).")
    return 0


def restore_phrase(
    settings: Settings,
    output: Output = print,
    ask: Input = input,
    ask_secret: Input | None = None,
) -> int:
    data_dir = settings.data_dir
    output(RESTORE_INTRO.format(data_dir=data_dir))
    ask_secret = ask_secret or _read_hidden
    try:
        key = phrase_to_master_key(ask_secret("Recovery phrase: "))
    except RecoveryPhraseError as exc:
        output(str(exc))
        return 1

    saved = read_fingerprint(data_dir)
    if saved is not None and saved != fingerprint(key):
        output(
            "That recovery phrase is valid, but it isn't the one for this data folder, so "
            "nothing was changed. If your data is in a different folder, set "
            "BUDGET_BUDDY_DATA_DIR to that folder and try again."
        )
        return 1

    store = get_key_store(settings.key_store)
    current = load_master_key(store, data_dir)
    if current == key:
        output("This computer already has that key. Nothing needed to change.")
        return 0
    if current is not None:
        output(
            "WARNING: this computer already has a different key for this folder. Replacing it "
            "means anything encrypted with the current key can't be read any more."
        )
        if ask("Type REPLACE to replace it, or press Enter to cancel: ").strip() != "REPLACE":
            output("Cancelled. Nothing was changed.")
            return 1

    from app.main import ensure_data_dir

    ensure_data_dir(data_dir)
    store.set(key_name_for(data_dir), key)
    if saved is None:
        write_fingerprint(data_dir, key)
    output("Done. Your key is back in this computer's password vault. Start Budget Buddy as usual.")
    return 0


def main(
    argv: list[str] | None = None,
    output: Output = print,
    ask: Input = input,
    ask_secret: Input | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="Budget Buddy Home Base")
    commands = parser.add_subparsers(dest="command")
    recovery = commands.add_parser(
        "recovery-phrase", help="Show or restore the recovery phrase for your encryption key."
    )
    recovery.add_argument("action", choices=["show", "restore"])
    recovery.add_argument(
        "--force",
        action="store_true",
        help="show: print the phrase even when the output isn't a terminal (e.g. into a file).",
    )
    backup = commands.add_parser("backup", help="Make an encrypted backup, or restore one.")
    backup_actions = backup.add_subparsers(dest="action", required=True)
    make = backup_actions.add_parser("make", help="Save a backup file of all your data.")
    make.add_argument("--to", type=Path, help="the folder to save it in (default: Documents)")
    restore = backup_actions.add_parser(
        "restore", help="Restore a backup file (Budget Buddy closed)."
    )
    restore.add_argument("file", type=Path, help="the .bbbackup file")
    args = parser.parse_args(argv)

    try:
        if args.command is None:
            from app.__main__ import serve

            serve()
            return 0
        settings = Settings()
        if args.command == "backup":
            from app.cli_backup import make_backup, restore_backup

            if args.action == "make":
                return make_backup(settings, args.to, output)
            return restore_backup(settings, args.file, output, ask, ask_secret or _read_hidden)
        if args.action == "show":
            return show_phrase(settings, output, ask, force=args.force)
        return restore_phrase(settings, output, ask, ask_secret)
    except (EncryptionError, DatabaseUpgradeError, RestoreError) as exc:
        output(str(exc))
        return 1
    except (KeyboardInterrupt, EOFError):
        output("\nCancelled. Nothing was changed.")
        return 1
