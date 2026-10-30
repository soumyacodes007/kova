"""Read-only Track B queries with the same disclosure boundary as Track A."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from cadrecover.api import queries
from cadrecover.api.models import FailedCheckOut, ModelFile, SetResult
from cadrecover.protocol.hill import Entry, LineageEntry, MatchSummary, MatchTask, Model, ModelStatus
from cadrecover.protocol.evaluation import set_quality
from cadrecover.protocol.challenge import Family


class StatusEvent(BaseModel):
    status: ModelStatus
    at: str
    block: int | None
    detail: str | None


class Hill(BaseModel):
    margin: float
    tasks_per_match: int
    families: list[Family]
    champion: Model | None
    lineage: list[LineageEntry]
    live_match: MatchSummary | None
    queue: list[Model]


class ModelDetail(BaseModel):
    model: Model
    matches: list[MatchSummary]
    events: list[StatusEvent]


class MatchDetail(BaseModel):
    match: MatchSummary
    tasks: list[MatchTask]


def models(con: sqlite3.Connection, network: str = "local") -> list[Model]:
    found = [Model.model_validate_json(r["model_json"]) for r in con.execute(
        "SELECT model_json FROM models WHERE network = ?", (network,))]
    return sorted(found, key=lambda m: (-(m.mean_quality if m.mean_quality is not None else -1),
                                       m.submitted_at, m.fingerprint))


def matches(con: sqlite3.Connection, network: str = "local") -> list[MatchSummary]:
    return [_public_summary(con, r["summary_json"])
            for r in con.execute("SELECT summary_json FROM matches WHERE network = ? ORDER BY rowid DESC", (network,))]


def _public_summary(con: sqlite3.Connection, raw: str) -> MatchSummary:
    summary = MatchSummary.model_validate_json(raw)
    retired = con.execute("SELECT count(*) FROM match_tasks t JOIN challenges c ON c.challenge_id=t.challenge_id "
                          "WHERE t.match_id=? AND c.status='retired'", (summary.match_id,)).fetchone()[0]
    if summary.status != "decided" or retired != summary.tasks_total:
        summary.seed = None
    return summary


def hill(con: sqlite3.Connection, network: str = "local") -> Hill:
    entries = models(con, network)
    history = [LineageEntry.model_validate_json(r["entry_json"])
               for r in con.execute("SELECT entry_json FROM lineage WHERE network = ? ORDER BY rowid", (network,))]
    rounds = matches(con, network)
    latest = rounds[0] if rounds else None
    stored = {r["key"]: json.loads(r["value_json"]) for r in con.execute("SELECT * FROM hill_settings")}
    settings = {key: stored.get(f"{network}.{key}", stored.get(key))
                for key in ("margin", "tasks_per_match", "families")
                if f"{network}.{key}" in stored or key in stored}
    return Hill(margin=settings.get("margin", latest.margin if latest else 2.0),
                tasks_per_match=settings.get("tasks_per_match", latest.tasks_total if latest else 10),
                families=settings.get("families", ["plate", "flange", "wafer_chuck"]),
                champion=next((m for m in entries if m.status == "champion"), None), lineage=history,
                live_match=next((m for m in rounds if m.status == "running"), None),
                queue=sorted((m for m in entries if m.status in ("prechecked", "queued")),
                             key=lambda m: (m.commit_block if m.commit_block is not None else -1, m.submitted_at)))


def model_detail(con: sqlite3.Connection, fingerprint: str, network: str = "local") -> ModelDetail | None:
    row = con.execute("SELECT model_json FROM models WHERE fingerprint = ? AND network = ?",
                      (fingerprint, network)).fetchone()
    if row is None:
        return None
    model = Model.model_validate_json(row["model_json"])
    events = []
    for event in con.execute("SELECT at, payload FROM events WHERE kind = 'model.status' "
                             "AND json_extract(payload, '$.fingerprint') = ? ORDER BY event_id", (fingerprint,)):
        p = json.loads(event["payload"])
        if p.get("network", "local") != network:
            continue
        if p.get("hotkey") is not None and (p["hotkey"] != model.hotkey or p.get("block") != model.commit_block):
            continue
        events.append(StatusEvent(status=p["status"], at=event["at"], block=p.get("block"), detail=p.get("detail")))
    history = [m for m in matches(con, network) if m.challenger.fingerprint == fingerprint or
               (m.champion is not None and m.champion.fingerprint == fingerprint)]
    return ModelDetail(model=model, matches=history, events=events)


def _entry(raw: dict | None, evaluation: str | None, *, revealed: bool, folder: Path,
           url: str) -> Entry | None:
    if raw is None:
        return None
    body = dict(raw)
    sets = []
    # Private evaluator JSON stays in storage; never return it directly.
    ev = json.loads(evaluation) if evaluation else None
    scored = ev.get("sets", []) if ev else body.get("sets", [])
    for s in scored:
        checks = s.get("failed_checks", [])
        valid, critical = bool(s["valid"]), bool(s["critical_ok"])
        sets.append(SetResult(index=s["index"], valid=valid, critical_ok=critical,
                              geometry=s["geometry"], dimensions=s["dimensions"],
                              q_s=s.get("q_s", s.get("q", set_quality(valid, critical, s["geometry"], s["dimensions"]))),
                              passed=valid and critical and not checks,
                              failed_check_count=s.get("failed_check_count", len(checks)),
                              failed_checks=[FailedCheckOut.model_validate(c) for c in checks] if revealed else [],
                              values=s.get("values") if revealed else None, revealed=revealed))
    files = []
    if (evaluation or sets or body.get("quality") is not None) and folder.is_dir():
        for f in sorted(folder.iterdir()):
            m = queries.MODEL_NAME.fullmatch(f.name)
            if m and f.is_file() and (m.group(2) == "candidate" or revealed):
                files.append(ModelFile(set_index=int(m.group(1)), kind=m.group(2), url=f"{url}/{f.name}"))
    error = body.get("error")
    if error and not revealed:
        error = "model failed; details withheld until retirement"
    if ev and ev.get("failure_reason"):
        error = ev["failure_reason"] if revealed else "evaluation failed; details withheld until retirement"
    return Entry(quality=body.get("quality"), latency_s=body.get("latency_s"), error=error, sets=sets, models=files)


def match_detail(con: sqlite3.Connection, match_id: str, root: Path, network: str = "local") -> MatchDetail | None:
    row = con.execute("SELECT summary_json FROM matches WHERE match_id = ? AND network = ?", (match_id, network)).fetchone()
    if row is None:
        return None
    summary = _public_summary(con, row["summary_json"])
    tasks = []
    for r in con.execute("SELECT * FROM match_tasks WHERE match_id = ? ORDER BY task_index", (match_id,)):
        task = json.loads(r["task_json"])
        index, cid = r["task_index"], r["challenge_id"]
        revealed = queries.challenge_retired(con, cid)
        entries = {}
        for side in ("challenger", "champion"):
            entries[side] = _entry(task.get(side), r[f"{side}_evaluation_json"], revealed=revealed,
                                  folder=root / match_id / f"task{index}" / side,
                                  url=f"/v1/matches/{match_id}/tasks/{index}/{side}/models")
        tasks.append(MatchTask(index=index, challenge_id=cid, family=task["family"],
                               drawing_url=f"/v1/challenges/{cid}/drawing.png", **entries))
    return MatchDetail(match=summary, tasks=tasks)


def model_path_allowed(con: sqlite3.Connection, match_id: str, index: int, side: str, name: str,
                       network: str = "local") -> bool:
    m = queries.MODEL_NAME.fullmatch(name)
    if not m or side not in ("challenger", "champion") or index < 0:
        return False
    row = con.execute("SELECT t.* FROM match_tasks t JOIN matches m ON m.match_id = t.match_id "
                      "WHERE t.match_id = ? AND t.task_index = ? AND m.network = ?", (match_id, index, network)).fetchone()
    if row is None:
        return False
    task = json.loads(row["task_json"])
    entry = task.get(side)
    if entry is None or not (row[f"{side}_evaluation_json"] or entry.get("sets") or entry.get("quality") is not None):
        return False
    return m.group(2) == "candidate" or queries.challenge_retired(con, row["challenge_id"])
