#!/usr/bin/env bash
# Run (on Linux) to start Budget Buddy: ./launch/start-budget-buddy.sh  Press Ctrl+C or close the window to stop it.
exec "$(dirname "$0")/../scripts/run-python.sh" scripts/start.py "$@"
