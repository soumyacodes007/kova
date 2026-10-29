"""Read-only SQL behind the API (owner: agent C).

Everything here reads SQLite and nothing else: no private challenge records, no chain calls, no invented data.
The one rule that matters: while a challenge is `active`, its hidden-edit values are ground truth, so set
values, failed-check text and reference models are withheld until the validator retires the challenge.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from cadrecover.api.models import (
    AuditOut,
    AuditStatus,
    AuditTask,
    ChallengeOut,
    CommitmentOut,
    Counts,
    EventOut,
    FailedCheckOut,
    Leaderboard,
    LeaderboardRow,
    MinerBatchAppearance,
    MinerDetail,
    MinerHistoryItem,
    MinerIdentity,
    MinerRunResult,
    ModelFile,
    ReceiptOut,
    RunDetail,
    RunSummary,
    SetResult,
    WeightBatchOut,
)
from cadrecover.protocol import QUALITY_FLOOR, PublicChallenge
from cadrecover.storage import db
from cadrecover.validator import aggregate

MODEL_NAME = re.compile(r"^s([0-3])\.(candidate|reference)\.glb$")


def _loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def _chunks(items: list, n: int = 500):
    for i in range(0, len(items), n):
        yield items[i:i + n]


# ------------------------------------------------------------------ status


def counts(con: sqlite3.Connection) -> Counts:
    def n(sql: str) -> int:
        return con.execute(sql).fetchone()[0]

    return Counts(
        challenges=n("SELECT count(*) FROM challenges"),
        active_challenges=n("SELECT count(*) FROM challenges WHERE status = 'active'"),
        runs=n("SELECT count(*) FROM runs"),
        miners=n("SELECT count(*) FROM miners"),
        assignments=n("SELECT count(*) FROM assignments"),
        evaluations=n("SELECT count(*) FROM evaluations"),
        weight_batches=n("SELECT count(*) FROM weight_batches"),
        receipts=n("SELECT count(*) FROM receipts"),
        commitments=n("SELECT count(*) FROM commitments"),
        audits=n("SELECT count(*) FROM audits"),
        events=n("SELECT count(*) FROM events"),
    )


def latest_event_id(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COALESCE(MAX(event_id), 0) FROM events").fetchone()[0]


# ------------------------------------------------------------------ challenges


def _challenge_out(row: sqlite3.Row) -> ChallengeOut | None:
    try:
        pub = PublicChallenge.model_validate_json(row["public_json"])
    except ValueError:
        return None
    return ChallengeOut(**pub.model_dump(), status=row["status"], retired_at=row["retired_at"],
                        drawing_url=f"/v1/challenges/{pub.challenge_id}/drawing.png")


def challenge(con: sqlite3.Connection, challenge_id: str) -> ChallengeOut | None:
    # only public columns are selected: private_path is never read
    row = con.execute("SELECT challenge_id, status, retired_at, public_json FROM challenges WHERE challenge_id = ?",
                      (challenge_id,)).fetchone()
    return _challenge_out(row) if row else None


def challenge_retired(con: sqlite3.Connection, challenge_id: str) -> bool:
    row = con.execute("SELECT status FROM challenges WHERE challenge_id = ?", (challenge_id,)).fetchone()
    return bool(row and row["status"] == "retired")


# ------------------------------------------------------------------ runs

_RUN_SQL = """
SELECT r.run_id, r.challenge_id, r.started_at, r.deadline_at, r.status, c.family,
  (SELECT count(*) FROM assignments a WHERE a.run_id = r.run_id) AS miners,
  (SELECT count(*) FROM assignments a JOIN evaluations e ON e.job_id = a.job_id
     WHERE a.run_id = r.run_id) AS evaluated,
  (SELECT avg(e.quality) FROM assignments a JOIN evaluations e ON e.job_id = a.job_id
     WHERE a.run_id = r.run_id) AS mean_quality,
  (SELECT max(e.quality) FROM assignments a JOIN evaluations e ON e.job_id = a.job_id
     WHERE a.run_id = r.run_id) AS best_quality,
  (SELECT a.uid FROM assignments a JOIN evaluations e ON e.job_id = a.job_id
     WHERE a.run_id = r.run_id AND e.quality IS NOT NULL ORDER BY e.quality DESC, a.uid LIMIT 1) AS best_uid
FROM runs r LEFT JOIN challenges c ON c.challenge_id = r.challenge_id
"""


def _run_summary(r: sqlite3.Row) -> RunSummary:
    return RunSummary(**{k: r[k] for k in r.keys()})


def runs(con: sqlite3.Connection, *, limit: int = 50, offset: int = 0, status: str | None = None) -> list[RunSummary]:
    where, params = ("WHERE r.status = ?", [status]) if status else ("", [])
    rows = con.execute(f"{_RUN_SQL} {where} ORDER BY r.started_at DESC, r.rowid DESC LIMIT ? OFFSET ?",
                       [*params, limit, offset]).fetchall()
    return [_run_summary(r) for r in rows]


def latest_run(con: sqlite3.Connection) -> RunSummary | None:
    found = runs(con, limit=1)
    return found[0] if found else None


def _set_results(sets: list[sqlite3.Row], values_by_index: dict[int, dict], revealed: bool) -> list[SetResult]:
    out = []
    for s in sets:
        checks = _loads(s["failed_checks"], [])
        valid, critical = bool(s["valid"]), bool(s["critical_ok"])
        out.append(SetResult(
            index=s["set_index"], valid=valid, critical_ok=critical, geometry=s["geometry"],
            dimensions=s["dimensions"], q_s=s["q"], passed=valid and critical and not checks,
            failed_check_count=len(checks),
            failed_checks=[FailedCheckOut(name=c.get("name", "?"), message=c.get("message", ""),
                                          location=c.get("location")) for c in checks] if revealed else [],
            values=values_by_index.get(s["set_index"]) if revealed else None,
            revealed=revealed,
        ))
    return out


def _model_files(runs_dir: Path, run_id: str, uid: int, evaluated: bool, revealed: bool) -> list[ModelFile]:
    """GLBs the validator wrote for this miner. Candidates appear once evaluated; references only after retirement."""
    folder = runs_dir / run_id / f"uid{uid}"
    if not evaluated or not folder.is_dir():
        return []
    out = []
    for f in sorted(folder.iterdir()):
        m = MODEL_NAME.match(f.name)
        if not m or not f.is_file():
            continue
        kind = m.group(2)
        if kind == "reference" and not revealed:
            continue
        out.append(ModelFile(set_index=int(m.group(1)), kind=kind,
                             url=f"/v1/runs/{run_id}/miners/{uid}/models/{f.name}"))
    out.sort(key=lambda m: (m.set_index, m.kind))
    return out


def run_detail(con: sqlite3.Connection, run_id: str, runs_dir: Path) -> RunDetail | None:
    row = con.execute(f"{_RUN_SQL} WHERE r.run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    summary = _run_summary(row)
    ch_row = con.execute("SELECT challenge_id, status, retired_at, public_json FROM challenges WHERE challenge_id = ?",
                         (summary.challenge_id,)).fetchone()
    revealed = bool(ch_row and ch_row["status"] == "retired")

    assignments = con.execute("""
        SELECT a.job_id, a.uid, a.miner_hotkey, a.registered_at_block, a.status, a.sent_at, m.label,
               e.quality, e.failure_class, e.failure_reason, e.evaluated_at, e.evaluation_json,
               s.received_at, s.envelope_json
        FROM assignments a
        LEFT JOIN miners m ON m.hotkey = a.miner_hotkey AND m.registered_at_block = a.registered_at_block
        LEFT JOIN evaluations e ON e.job_id = a.job_id
        LEFT JOIN submissions s ON s.job_id = a.job_id
        WHERE a.run_id = ? ORDER BY a.uid""", (run_id,)).fetchall()

    sets_by_job: dict[str, list[sqlite3.Row]] = {}
    for chunk in _chunks([a["job_id"] for a in assignments]):
        marks = ",".join("?" * len(chunk))
        for s in con.execute(f"SELECT * FROM evaluation_sets WHERE job_id IN ({marks}) ORDER BY job_id, set_index", chunk):
            sets_by_job.setdefault(s["job_id"], []).append(s)

    results = []
    for a in assignments:
        evaluated = a["evaluated_at"] is not None
        values: dict[int, dict] = {}
        if evaluated and revealed:
            for s in _loads(a["evaluation_json"], {}).get("sets", []):
                values[s.get("index")] = s.get("values", {})
        env = _loads(a["envelope_json"], {})
        results.append(MinerRunResult(
            job_id=a["job_id"], uid=a["uid"], hotkey=a["miner_hotkey"], registered_at_block=a["registered_at_block"],
            label=a["label"], assignment_status=a["status"], sent_at=a["sent_at"], evaluated=evaluated,
            evaluated_at=a["evaluated_at"], quality=a["quality"],
            failure_class=a["failure_class"], failure_reason=a["failure_reason"],
            sets=_set_results(sets_by_job.get(a["job_id"], []), values, revealed),
            source_sha256=env.get("source_sha256"), model_id=env.get("model_id"),
            strategy_version=env.get("strategy_version"), duration_s=env.get("duration_s"),
            received_at=a["received_at"],
            models=_model_files(runs_dir, run_id, a["uid"], evaluated, revealed),
        ))
    return RunDetail(run=summary, challenge=_challenge_out(ch_row) if ch_row else None, results=results)


def model_path_allowed(con: sqlite3.Connection, run_id: str, uid: int, name: str) -> bool:
    """Whether this GLB may be served now: candidates after evaluation, references after retirement."""
    m = MODEL_NAME.match(name)
    if not m:
        return False
    row = con.execute("""
        SELECT c.status, e.job_id AS evaluated FROM assignments a
        JOIN runs r ON r.run_id = a.run_id
        LEFT JOIN challenges c ON c.challenge_id = r.challenge_id
        LEFT JOIN evaluations e ON e.job_id = a.job_id
        WHERE a.run_id = ? AND a.uid = ?""", (run_id, uid)).fetchone()
    if row is None or row["evaluated"] is None:
        return False
    return m.group(2) == "candidate" or row["status"] == "retired"


# ------------------------------------------------------------------ audits and commitments


def _audit_status_map(con: sqlite3.Connection) -> dict[str, AuditOut]:
    """Newest audit run per hotkey."""
    latest: dict[str, AuditOut] = {}
    for a in audits(con, limit=10_000):  # newest first
        latest.setdefault(a.hotkey, a)
    return latest


def _identity_labels(con: sqlite3.Connection) -> dict[str, tuple[int | None, str | None]]:
    """hotkey -> (uid, label) of its newest registration."""
    out: dict[str, tuple[int | None, str | None]] = {}
    for r in con.execute("SELECT hotkey, uid, label FROM miners ORDER BY registered_at_block"):
        out[r["hotkey"]] = (r["uid"], r["label"])
    return out


def audits(con: sqlite3.Connection, *, hotkey: str | None = None, limit: int = 100) -> list[AuditOut]:
    where, params = ("WHERE miner_hotkey = ?", [hotkey]) if hotkey else ("", [])
    rows = con.execute(f"SELECT * FROM audits {where} ORDER BY at DESC, rowid DESC", params).fetchall()
    ids = _identity_labels(con)
    groups: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        d = _loads(r["detail"], {})
        groups.setdefault(d.get("audit_run") or r["audit_id"], []).append(r)
    out = []
    for run, grp in groups.items():
        first = _loads(grp[-1]["detail"], {})  # group is newest-first: [-1] is task 0 / the earliest row
        newest = grp[0]
        verdict = first.get("verdict") or ("pass" if all(g["passed"] for g in grp) else "fail")
        uid, label = ids.get(newest["miner_hotkey"], (None, None))
        tasks = []
        for g in sorted(grp, key=lambda g: g["audit_id"]):
            if g["challenge_id"] in ("", "-"):
                continue
            d = _loads(g["detail"], {})
            tasks.append(AuditTask(audit_id=g["audit_id"], task_index=d.get("task_index"),
                                   challenge_id=g["challenge_id"], quality=g["quality"],
                                   passed=bool(g["passed"]), error=d.get("error")))
        tasks.sort(key=lambda t: (t.task_index is None, t.task_index or 0))
        out.append(AuditOut(
            audit_run=run, hotkey=newest["miner_hotkey"], uid=uid, label=label, engine_digest=newest["engine_digest"],
            verdict=verdict, reason=first.get("reason"), live_mean=first.get("live_mean"),
            audit_mean=first.get("audit_mean"), margin=first.get("margin"), block=newest["block"],
            at=newest["at"], commitment=first.get("commitment"), tasks=tasks))
    return out[:limit]


def commitments(con: sqlite3.Connection, *, hotkey: str | None = None) -> list[CommitmentOut]:
    where, params = ("WHERE c.hotkey = ?", [hotkey]) if hotkey else ("", [])
    rows = con.execute(f"""
        SELECT c.*, m.uid, m.label FROM commitments c
        LEFT JOIN miners m ON m.hotkey = c.hotkey AND m.registered_at_block = c.registered_at_block
        {where} ORDER BY c.block DESC, c.rowid DESC""", params).fetchall()
    seen: set[tuple[str, int]] = set()
    out = []
    for r in rows:  # newest first, so the first row per identity is its latest commitment
        key = (r["hotkey"], r["registered_at_block"])
        out.append(CommitmentOut(hotkey=r["hotkey"], registered_at_block=r["registered_at_block"], uid=r["uid"],
                                 label=r["label"], engine_digest=r["engine_digest"],
                                 strategy_version=r["strategy_version"], block=r["block"], latest=key not in seen))
        seen.add(key)
    return out


# ------------------------------------------------------------------ weights


def _int_keys(d: Any) -> dict[int, float]:
    out: dict[int, float] = {}
    for k, v in (d or {}).items():
        try:
            out[int(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def weight_batches(con: sqlite3.Connection, *, limit: int = 50, batch_id: str | None = None) -> list[WeightBatchOut]:
    where, params = ("WHERE batch_id = ?", [batch_id]) if batch_id else ("", [])
    rows = con.execute(f"SELECT * FROM weight_batches {where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
                       [*params, limit]).fetchall()
    ids = [r["batch_id"] for r in rows]
    receipts: dict[str, list[ReceiptOut]] = {}
    for chunk in _chunks(ids):
        marks = ",".join("?" * len(chunk))
        for r in con.execute(f"SELECT * FROM receipts WHERE batch_id IN ({marks}) ORDER BY receipt_id", chunk):
            rb = _loads(r["readback"], None)
            receipts.setdefault(r["batch_id"], []).append(ReceiptOut(
                receipt_id=r["receipt_id"], state=r["state"], block=r["block"], extrinsic=r["extrinsic"],
                readback=_int_keys(rb) if isinstance(rb, dict) else None, error=r["error"], at=r["at"]))
    run_of = {}
    for e in con.execute("SELECT run_id, payload FROM events WHERE kind IN ('weights.proposed', 'weights.no_update')"):
        run_of[_loads(e["payload"], {}).get("batch_id")] = e["run_id"]
    out = []
    for r in rows:
        body = _loads(r["batch_json"], {})
        rs = receipts.get(r["batch_id"], [])
        out.append(WeightBatchOut(
            batch_id=r["batch_id"], run_id=run_of.get(r["batch_id"]), network=r["network"], netuid=r["netuid"],
            validator_hotkey=r["validator_hotkey"], floor=r["floor"], created_at=r["created_at"],
            mean_quality={k: float(v) for k, v in (body.get("mean_quality") or {}).items()},
            samples={k: int(v) for k, v in (body.get("samples") or {}).items()},
            weights=_int_keys(body.get("weights")), latest_state=rs[-1].state if rs else None, receipts=rs))
    return out


# ------------------------------------------------------------------ leaderboard and miners


def _participants(con: sqlite3.Connection, run_id: str) -> set[tuple[str, int]]:
    return {(r["miner_hotkey"], r["registered_at_block"])
            for r in con.execute("SELECT miner_hotkey, registered_at_block FROM assignments WHERE run_id = ?", (run_id,))}


def leaderboard(con: sqlite3.Connection, window: int = aggregate.WINDOW) -> Leaderboard:
    # "registered now" = the identities the validator dispatched to in its newest round (its own view of the metagraph)
    newest = runs(con, limit=1)
    current = _participants(con, newest[0].run_id) if newest else None
    table = aggregate.standings(con, window=window, current=current or None, zeroed=db.failed_audits(con))
    batches = weight_batches(con, limit=1)
    latest = batches[0] if batches else None
    in_batch_run = _participants(con, latest.run_id) if latest and latest.run_id else None

    # the same window the standings used: newest `window` non-outage evaluations per identity
    jobs: dict[tuple[str, int], list[str]] = {}
    for r in con.execute("""
            SELECT m.hotkey, m.registered_at_block AS reg, e.job_id
            FROM miners m
            JOIN assignments a ON a.miner_hotkey = m.hotkey AND a.registered_at_block = m.registered_at_block
            JOIN evaluations e ON e.job_id = a.job_id
            WHERE e.failure_class != 'validator_outage'
            ORDER BY e.evaluated_at DESC"""):
        lst = jobs.setdefault((r["hotkey"], r["reg"]), [])
        if len(lst) < window:
            lst.append(r["job_id"])
    wanted = [j for lst in jobs.values() for j in lst]
    sets: dict[str, list[sqlite3.Row]] = {}
    for chunk in _chunks(wanted):
        marks = ",".join("?" * len(chunk))
        for s in con.execute(f"SELECT job_id, set_index, valid, critical_ok, geometry, dimensions, failed_checks "
                             f"FROM evaluation_sets WHERE job_id IN ({marks})", chunk):
            sets.setdefault(s["job_id"], []).append(s)

    def passed(s: sqlite3.Row) -> bool:
        return bool(s["valid"]) and bool(s["critical_ok"]) and _loads(s["failed_checks"], []) == []

    commits = {(c.hotkey, c.registered_at_block): c.engine_digest for c in commitments(con) if c.latest}
    audit_by_hotkey = _audit_status_map(con)

    rows = []
    for rank, st in enumerate(table, start=1):
        mine = [s for j in jobs.get((st.hotkey, st.registered_at_block), []) for s in sets.get(j, [])]
        s0 = [s for s in mine if s["set_index"] == 0]
        edits = [s for s in mine if s["set_index"] > 0]
        a = audit_by_hotkey.get(st.hotkey)
        rows.append(LeaderboardRow(
            rank=rank, uid=st.uid, hotkey=st.hotkey, registered_at_block=st.registered_at_block, label=st.label,
            samples=st.samples, mean_quality=st.mean_quality, above_floor=st.above_floor, weight=st.weight,
            latest_batch_weight=(latest.weights.get(st.uid, 0.0) if latest and (
                in_batch_run is None or (st.hotkey, st.registered_at_block) in in_batch_run) else None),
            drawing_pass_rate=(sum(map(passed, s0)) / len(s0)) if s0 else None,
            edit_pass_rate=(sum(map(passed, edits)) / len(edits)) if edits else None,
            mean_geometry=(sum(s["geometry"] for s in mine) / len(mine)) if mine else None,
            mean_dimensions=(sum(s["dimensions"] for s in mine) / len(mine)) if mine else None,
            committed_engine=commits.get((st.hotkey, st.registered_at_block)),
            audit=AuditStatus(audit_run=a.audit_run, verdict=a.verdict, at=a.at, block=a.block,
                              engine_digest=a.engine_digest, live_mean=a.live_mean, audit_mean=a.audit_mean,
                              reason=a.reason) if a else None,
        ))
    return Leaderboard(quality_floor=QUALITY_FLOOR, window=window, min_samples=aggregate.MIN_SAMPLES,
                       latest_batch_id=latest.batch_id if latest else None, rows=rows)


def miner_detail(con: sqlite3.Connection, hotkey: str, history_limit: int = 200) -> MinerDetail | None:
    idents = con.execute("SELECT * FROM miners WHERE hotkey = ? ORDER BY registered_at_block DESC", (hotkey,)).fetchall()
    if not idents:
        return None
    board = leaderboard(con)
    standing = next((r for r in board.rows if r.hotkey == hotkey), None)

    hist_rows = con.execute("""
        SELECT a.job_id, a.run_id, a.status, e.challenge_id, e.evaluated_at, e.quality, e.failure_class,
               e.failure_reason
        FROM assignments a JOIN evaluations e ON e.job_id = a.job_id
        WHERE a.miner_hotkey = ? ORDER BY e.evaluated_at DESC, a.rowid DESC LIMIT ?""", (hotkey, history_limit)).fetchall()
    set_q: dict[str, dict[int, float]] = {}
    for chunk in _chunks([h["job_id"] for h in hist_rows]):
        marks = ",".join("?" * len(chunk))
        for s in con.execute(f"SELECT job_id, set_index, q FROM evaluation_sets WHERE job_id IN ({marks})", chunk):
            set_q.setdefault(s["job_id"], {})[s["set_index"]] = s["q"]
    history = [MinerHistoryItem(
        job_id=h["job_id"], run_id=h["run_id"], challenge_id=h["challenge_id"], evaluated_at=h["evaluated_at"],
        assignment_status=h["status"], quality=h["quality"], failure_class=h["failure_class"],
        failure_reason=h["failure_reason"], set_q=[v for _, v in sorted(set_q.get(h["job_id"], {}).items())])
        for h in hist_rows]

    batches = []
    states = {b.batch_id: b.latest_state for b in weight_batches(con, limit=200)}
    for b in con.execute("SELECT batch_id, created_at, batch_json FROM weight_batches ORDER BY created_at DESC, rowid DESC LIMIT 200"):
        body = _loads(b["batch_json"], {})
        if hotkey in (body.get("mean_quality") or {}):
            batches.append(MinerBatchAppearance(
                batch_id=b["batch_id"], created_at=b["created_at"], mean_quality=float(body["mean_quality"][hotkey]),
                samples=int((body.get("samples") or {}).get(hotkey, 0)), latest_state=states.get(b["batch_id"])))

    return MinerDetail(
        hotkey=hotkey,
        identities=[MinerIdentity(hotkey=i["hotkey"], registered_at_block=i["registered_at_block"], uid=i["uid"],
                                  label=i["label"], first_seen=i["first_seen"]) for i in idents],
        standing=standing, history=history, commitments=commitments(con, hotkey=hotkey),
        audits=audits(con, hotkey=hotkey), batches=batches)


# ------------------------------------------------------------------ events


def events(con: sqlite3.Connection, *, after: int = 0, limit: int = 200, run_id: str | None = None,
           kind: str | None = None) -> list[EventOut]:
    sql, params = "SELECT * FROM events WHERE event_id > ?", [after]
    if run_id is not None:
        sql, params = sql + " AND run_id = ?", [*params, run_id]
    if kind:
        sql, params = sql + " AND (kind = ? OR kind LIKE ? ESCAPE '\\')", [*params, kind, _like_prefix(kind)]
    rows = con.execute(sql + " ORDER BY event_id LIMIT ?", [*params, limit]).fetchall()
    return [EventOut(event_id=r["event_id"], at=r["at"], kind=r["kind"], run_id=r["run_id"],
                     payload=_loads(r["payload"], {})) for r in rows]


def _like_prefix(kind: str) -> str:
    """`weights` also matches `weights.committed`: a dotted prefix, with LIKE wildcards escaped."""
    esc = kind.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return esc + ".%"
