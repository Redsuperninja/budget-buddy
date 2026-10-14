"""Start pairing on the TEST Home Base and show the QR code for the phone to scan.

Run it via scripts/testing/pair-phone.ps1. The code works once, for 10 minutes. It is a secret while it's
valid, so it is only shown on screen and in a temporary picture that is deleted when you press
Enter or the code expires, whichever comes first.
"""

import argparse
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

from _local_api import ApiError, LocalApi, NotRunning
from _testguard import refuse_unless_test_server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    port = parser.parse_args().port
    reason = refuse_unless_test_server(port)
    if reason:
        print(reason)
        return 2
    api = LocalApi(f"http://127.0.0.1:{port}")
    try:
        started = api.call("POST", "/api/local/pairing")
    except NotRunning:
        print(f"The test Home Base isn't running on port {port}.")
        print("Start it first with scripts\\testing\\start-test-server.ps1 (in its own window).")
        return 1
    except ApiError as exc:
        print(exc)
        return 1

    if not started.get("phone_can_connect", False):
        print(
            started.get("message") or "Your phone can't reach this computer right now."
        )
        return 1

    try:
        import segno
    except ImportError:
        print("The QR code tool isn't installed. Run scripts\\testing\\setup.ps1 again.")
        return 1

    qr = segno.make(started["payload_text"], error="m")
    print(
        "On your phone: open Budget Buddy > Settings > Connect, then scan this code.\n"
    )
    try:
        qr.terminal()  # uses console colors, so it works in any Windows console
    except (UnicodeEncodeError, OSError):
        print("(This window can't draw the code; use the picture window instead.)")
    seconds_left = max(0, started["expires_at"] - time.time())
    print(
        f"\nThe code works once and for about {max(1, round(seconds_left / 60))} minutes."
    )
    show_bigger_copy(qr, seconds_left)
    return 0


def show_bigger_copy(qr, seconds_left: float) -> None:
    """Open a bigger picture of the code; delete it on Enter or when the code expires."""
    fd, name = tempfile.mkstemp(prefix="budget-buddy-pair-", suffix=".png")
    os.close(fd)
    picture = Path(name)
    try:
        qr.save(picture, scale=8)
        os.startfile(picture)  # Windows: opens it in the picture viewer
        print("A bigger copy is open in a picture window.")
        done = threading.Event()
        threading.Thread(
            target=lambda: (
                input("Press Enter once your phone is connected... "),
                done.set(),
            ),
            daemon=True,
        ).start()
        if not done.wait(seconds_left):
            print("\nThe code has expired. Run this again for a new one.")
    except (OSError, AttributeError):
        print("(Couldn't open a picture window; scan the code above.)")
    finally:
        try:
            picture.unlink(missing_ok=True)
        except OSError:
            print(
                f"Couldn't delete {picture}. You can delete it yourself; the code no longer works."
            )


if __name__ == "__main__":
    sys.exit(main())
