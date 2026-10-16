#!/usr/bin/env bash
# Run a Budget Buddy script with Python 3.12 or newer, on macOS or Linux. The double-click files in launch/ use it:
#   scripts/run-python.sh scripts/start.py [arguments]
# Paths are relative to the Budget Buddy folder, wherever this is run from.

cd "$(dirname "$0")/.." || exit 1
for python in python3.14 python3.13 python3.12 python3 python; do
    if command -v "$python" >/dev/null 2>&1 &&
        "$python" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
        exec "$python" "$@"
    fi
done
echo "Budget Buddy needs Python 3.12 or newer. Install it from https://www.python.org/downloads/"
echo "(or your system's package manager), then try again."
exit 1
