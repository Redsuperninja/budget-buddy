"""One-time setup for testing Budget Buddy: installs the Home Base (with developer tools) and the
phone app's tools (Node.js). Safe to run again. Everyday use doesn't need this: Start Budget Buddy
sets itself up.

    python3 scripts/testing/set_up.py          (on Windows, type py instead of python3)
"""

import argparse
import shutil

from _test_settings import START_TEST_SERVER

from _common import MOBILE_DIR, command_for, install_home_base, run, say, stop


def main() -> int:
    argparse.ArgumentParser(description="Set up Budget Buddy for testing.").parse_args()
    say("Setting up Budget Buddy for testing...", "cyan")
    npm = shutil.which("npm")
    if not npm:
        stop(
            "Node.js isn't installed. Install the LTS version from https://nodejs.org/, "
            "then run this again."
        )

    say("1/2  Home Base...")
    install_home_base(dev=True)
    say("2/2  Phone app tools...")
    run(
        [npm, "ci", "--no-audit", "--no-fund", "--loglevel=error"],
        MOBILE_DIR,
        "Installing the phone app tools failed.",
    )

    say()
    say("All set. Next:", "green")
    say(f"  1. {START_TEST_SERVER}   (leave that window open)")
    say(f"  2. {command_for('scripts/testing/load_demo_data.py')}   (fills it with made-up data)")
    say("See docs/testing/set-up-for-testing.md for the full walkthrough.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
