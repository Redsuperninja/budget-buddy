#!/usr/bin/env bash
# Double-click (on a Mac) to start Budget Buddy. Close the window that opens to stop it.
exec "$(dirname "$0")/../scripts/run-python.sh" scripts/start.py "$@"
