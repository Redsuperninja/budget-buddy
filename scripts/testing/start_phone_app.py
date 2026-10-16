"""Start the phone app for testing with Expo Go.

Put the Expo Go app on your phone (App Store / Google Play), be on the same Wi-Fi as this computer,
then scan the QR code this window shows. Press Ctrl+C to stop.

    python3 scripts/testing/start_phone_app.py      (on Windows, type py instead of python3)
"""

import argparse
import shutil
import subprocess

from _test_settings import SET_UP

from _common import MOBILE_DIR, say, stop


def main() -> int:
    argparse.ArgumentParser(description="Start the phone app for Expo Go.").parse_args()
    npx = shutil.which("npx")
    if not npx or not (MOBILE_DIR / "node_modules").is_dir():
        stop(f"The phone app tools aren't installed yet. Run {SET_UP} first.")
    say("Starting the phone app. Scan the QR code below with:", "cyan")
    say("  iPhone:  the Camera app      Android:  the Expo Go app")
    say()
    try:
        return subprocess.run([npx, "expo", "start", "--lan"], cwd=MOBILE_DIR).returncode
    except KeyboardInterrupt:  # Expo got the Ctrl+C too and stops by itself
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
