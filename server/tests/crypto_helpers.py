"""Shared by the encryption tests: fake keys and a look at the SQLite file below the models."""

import sqlite3

from app.db import database_path

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))


def raw_rows(data_dir, sql):
    """Run ``sql`` on the data folder's database without the app, so values are as stored."""
    conn = sqlite3.connect(database_path(data_dir))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()
