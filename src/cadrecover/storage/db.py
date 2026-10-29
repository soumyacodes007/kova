"""SQLite access (owner: agent B). One file, WAL mode, foreign keys on."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cadrecover import paths
from cadrecover.protocol import PublicChallenge

SCHEMA_VERSION = 1
_SCHEMA = Path(__file__).with_name("schema.sql")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(db_path or paths.DB)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(_SCHEMA.read_text())
    if con.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 0:
        con.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    con.commit()
    return con


def add_event(con: sqlite3.Connection, kind: str, payload: dict | None = None, run_id: str | None = None) -> int:
    cur = con.execute("INSERT INTO events (at, kind, run_id, payload) VALUES (?, ?, ?, ?)",
                      (_now(), kind, run_id, json.dumps(payload or {}, default=str)))
    con.commit()
    return cur.lastrowid


def save_challenge(con: sqlite3.Connection, public: PublicChallenge, private_path: Path) -> None:
    con.execute(
        "INSERT INTO challenges (challenge_id, family, created_at, status, public_json, private_path) "
        "VALUES (?, ?, ?, 'active', ?, ?)",
        (public.challenge_id, public.family, public.created_at.isoformat(), public.model_dump_json(), str(private_path)),
    )
    con.commit()
    add_event(con, "challenge.created", {"challenge_id": public.challenge_id, "family": public.family})


def get_public_challenge(con: sqlite3.Connection, challenge_id: str) -> PublicChallenge | None:
    row = con.execute("SELECT public_json FROM challenges WHERE challenge_id = ?", (challenge_id,)).fetchone()
    return PublicChallenge.model_validate_json(row["public_json"]) if row else None
