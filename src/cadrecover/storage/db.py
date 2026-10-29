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


def retire_challenge(con: sqlite3.Connection, challenge_id: str, reason: str) -> None:
    con.execute("UPDATE challenges SET status = 'retired', retired_at = ? WHERE challenge_id = ?", (_now(), challenge_id))
    con.commit()
    add_event(con, "challenge.retired", {"challenge_id": challenge_id, "reason": reason})


# ---------------------------------------------------------------- rounds (agent B, phase 5)


def upsert_miner(con: sqlite3.Connection, hotkey: str, registered_at_block: int, uid: int, label: str | None) -> None:
    con.execute(
        "INSERT INTO miners (hotkey, registered_at_block, uid, first_seen, label) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (hotkey, registered_at_block) DO UPDATE SET uid = excluded.uid, label = excluded.label",
        (hotkey, registered_at_block, uid, _now(), label),
    )
    con.commit()


def create_run(con: sqlite3.Connection, run_id: str, challenge_id: str, deadline_at: datetime) -> None:
    con.execute("INSERT INTO runs (run_id, challenge_id, started_at, deadline_at, status) VALUES (?, ?, ?, ?, 'dispatching')",
                (run_id, challenge_id, _now(), deadline_at.isoformat()))
    con.commit()


def set_run_status(con: sqlite3.Connection, run_id: str, status: str) -> None:
    con.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
    con.commit()


def add_assignment(con: sqlite3.Connection, job_id: str, run_id: str, hotkey: str, registered_at_block: int,
                   uid: int) -> None:
    con.execute("INSERT INTO assignments (job_id, run_id, miner_hotkey, registered_at_block, uid, status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')", (job_id, run_id, hotkey, registered_at_block, uid))
    con.commit()


def set_assignment(con: sqlite3.Connection, job_id: str, status: str) -> None:
    con.execute("UPDATE assignments SET status = ?, sent_at = COALESCE(sent_at, ?) WHERE job_id = ?",
                (status, _now(), job_id))
    con.commit()


def save_submission(con: sqlite3.Connection, job_id: str, envelope_json: str, source_sha256: str) -> None:
    con.execute("INSERT OR IGNORE INTO submissions (job_id, received_at, source_sha256, envelope_json) VALUES (?, ?, ?, ?)",
                (job_id, _now(), source_sha256, envelope_json))
    con.commit()


def save_evaluation(con: sqlite3.Connection, ev) -> None:
    """Store an Evaluation and its four per-set rows. A validator outage has no quality (NULL)."""
    quality = None if ev.failure_class == "validator_outage" else ev.quality
    con.execute(
        "INSERT OR REPLACE INTO evaluations (job_id, challenge_id, miner_hotkey, quality, failure_class, failure_reason, "
        "evaluation_json, evaluated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ev.job_id, ev.challenge_id, ev.miner_hotkey, quality, ev.failure_class, ev.failure_reason,
         ev.model_dump_json(), _now()),
    )
    con.execute("DELETE FROM evaluation_sets WHERE job_id = ?", (ev.job_id,))
    con.executemany(
        "INSERT INTO evaluation_sets (job_id, set_index, valid, critical_ok, geometry, dimensions, q, failed_checks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(ev.job_id, s.index, int(s.valid), int(s.critical_ok), s.geometry, s.dimensions, s.q,
          json.dumps([f.model_dump() for f in s.failed_checks])) for s in ev.sets],
    )
    con.commit()


def save_weight_batch(con: sqlite3.Connection, batch, state: str, error: str | None = None) -> None:
    con.execute("INSERT INTO weight_batches (batch_id, network, netuid, validator_hotkey, floor, batch_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch.batch_id, batch.network, batch.netuid, batch.validator_hotkey, batch.floor,
                 batch.model_dump_json(), _now()))
    con.execute("INSERT INTO receipts (batch_id, state, error, at) VALUES (?, ?, ?, ?)",
                (batch.batch_id, state, error, _now()))
    con.commit()


def add_receipt(con: sqlite3.Connection, batch_id: str, state: str, *, block: int | None = None,
                extrinsic: str | None = None, readback: dict | None = None, error: str | None = None) -> None:
    con.execute("INSERT INTO receipts (batch_id, state, block, extrinsic, readback, error, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch_id, state, block, extrinsic, json.dumps(readback) if readback is not None else None, error, _now()))
    con.commit()


def receipts(con: sqlite3.Connection, batch_id: str) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM receipts WHERE batch_id = ? ORDER BY receipt_id", (batch_id,))]


def save_commitment(con: sqlite3.Connection, hotkey: str, registered_at_block: int, engine_digest: str,
                    strategy_version: str | None, block: int) -> None:
    con.execute("INSERT OR IGNORE INTO commitments (hotkey, registered_at_block, engine_digest, strategy_version, block) "
                "VALUES (?, ?, ?, ?, ?)", (hotkey, registered_at_block, engine_digest, strategy_version, block))
    con.commit()


def save_audit(con: sqlite3.Connection, audit_id: str, hotkey: str, engine_digest: str, challenge_id: str,
               quality: float | None, passed: bool, block: int | None, detail: dict) -> None:
    con.execute("INSERT INTO audits (audit_id, miner_hotkey, engine_digest, challenge_id, quality, passed, block, at, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (audit_id, hotkey, engine_digest, challenge_id, quality, int(passed), block, _now(), json.dumps(detail)))
    con.commit()


def failed_audits(con: sqlite3.Connection) -> set[str]:
    """Hotkeys whose latest audit verdict is a failure (weight 0 until a clean audit)."""
    rows = con.execute("""
        SELECT miner_hotkey, json_extract(detail, '$.verdict') AS verdict, at FROM audits
        WHERE json_extract(detail, '$.verdict') IS NOT NULL ORDER BY at""").fetchall()
    latest: dict[str, str] = {}
    for r in rows:
        latest[r["miner_hotkey"]] = r["verdict"]
    return {h for h, v in latest.items() if v == "fail"}
