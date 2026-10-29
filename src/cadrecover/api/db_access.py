"""Read-only SQLite connections for the API (owner: agent C). The API never writes the database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open the validator's WAL database read-only; a fresh connection per request or poll is cheap."""
    path = Path(db_path).resolve()
    try:
        con = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30, check_same_thread=False)
        con.execute("SELECT 1 FROM schema_version LIMIT 1")
    except sqlite3.OperationalError:
        # a WAL database whose -shm cannot be opened read-only: fall back to a normal connection, still read-only
        con = sqlite3.connect(path, timeout=30, check_same_thread=False)
        con.execute("PRAGMA query_only=ON")
    con.row_factory = sqlite3.Row
    return con
