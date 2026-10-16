"""The scripts import each other by file name (``import _common``), as they do when run, so put
both folders on the path."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "testing")]
