"""Engine audits (owner: agent A). PRD §Audit loop, REVIEW #5.

Each miner commits its engine's image ID on-chain. The auditor:
  1. reads the commitment for a top miner and finds exactly that image (by digest; a missing
     image fails: we never run "something similar")
  2. runs it in a locked-down container (no network, read-only, no capabilities, uid 1000)
     on PASS_TASKS fresh hidden tasks that no miner has seen
  3. scores each output with the same sandboxed evaluator as live answers
  4. pass rule: mean audit Q >= live mean Q - PASS_MARGIN. One-sided: an engine that does
     better than its live answers is not hiding anything; one that does worse means the live
     answers came from somewhere else (a hand solver, a bigger model, a copied answer)
  5. a fail zeroes the miner's weight until a clean audit (aggregate.standings `zeroed`)

LLM engines don't reproduce exactly, hence a margin over several tasks, not an exact match.
Mock engines read the task's private record, as they do live; that record is mounted only when
CADRECOVER_DEV_ORACLE=1 (local development), never for a real engine.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid

from cadrecover import paths
from cadrecover.challenges.pipeline import new_challenge
from cadrecover.evaluation.score import score_source
from cadrecover.storage import db

PASS_TASKS = 3
PASS_MARGIN = 10.0
ENGINE_TIMEOUT_S = 120


def image_present(digest: str) -> bool:
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", digest], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == digest


def engine_command(digest: str, task_dir, challenge_id: str, job_id: str, dev_oracle: bool) -> list[str]:
    cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", "1g", "--cpus", "1",
           "--user", "1000:1000", "-e", f"JOB_ID={job_id}", "-v", f"{task_dir}:/task:ro"]
    if dev_oracle:  # mock engines only; see module docstring
        private = paths.PRIVATE / challenge_id / "private.json"
        cmd += ["-e", "CADRECOVER_DEV_ORACLE=1", "-e", "CADRECOVER_HOME=/cr",
                "-v", f"{private}:/cr/runtime/private/{challenge_id}/private.json:ro"]
    return cmd + [digest]


def run_engine(digest: str, challenge_id: str, job_id: str) -> dict:
    """Run the committed engine image on one task. Returns its JSON output or {"error": ...}."""
    pub = db.get_public_challenge(db.connect(), challenge_id)
    task = paths.RUNTIME / "audits" / job_id
    task.mkdir(parents=True, exist_ok=True)
    (task / "challenge.json").write_text(pub.model_dump_json())
    shutil.copy(paths.PUBLIC / pub.drawing.path, task / "drawing.png")
    for f in task.iterdir():
        f.chmod(0o644)
    task.chmod(0o755)
    cmd = engine_command(digest, task, challenge_id, job_id, os.environ.get("CADRECOVER_DEV_ORACLE") == "1")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=ENGINE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"error": f"engine timed out after {ENGINE_TIMEOUT_S}s"}
    finally:
        shutil.rmtree(task, ignore_errors=True)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("{")]
    if not lines:
        return {"error": f"engine exit {r.returncode}, no output: {r.stderr.strip()[-300:]}"}
    try:
        return json.loads(lines[-1])
    except ValueError:
        return {"error": "engine output is not JSON"}


def verdict(audit_qs: list[float], live_mean: float, margin: float = PASS_MARGIN) -> tuple[bool, float]:
    """The pass rule: mean audit Q over the tasks is at least live mean Q - margin."""
    mean = sum(audit_qs) / len(audit_qs)
    return mean >= live_mean - margin, mean


def audit_miner(hotkey: str, live_mean: float, *, network: str = "local", family: str = "plate",
                tasks: int = PASS_TASKS, margin: float = PASS_MARGIN, log=print) -> dict:
    import bittensor as bt

    from cadrecover.chain.commitments import read_commitment
    from cadrecover.chain.setup import network_url

    con = db.connect()
    audit_run = "audit_" + uuid.uuid4().hex[:10]
    with bt.Subtensor(network_url(network)) as sub:
        block = sub.block
    c = read_commitment(hotkey, network)
    row = con.execute("SELECT registered_at_block FROM miners WHERE hotkey = ? ORDER BY registered_at_block DESC",
                      (hotkey,)).fetchone()
    detail = {"audit_run": audit_run, "live_mean": round(live_mean, 2), "margin": margin, "tasks": tasks}

    def finish(result: str, digest: str, qs: list, reason: str | None) -> dict:
        audit_mean = sum(q or 0.0 for _, q, _ in qs) / len(qs) if qs else None
        d = {**detail, "verdict": result, "reason": reason, "commitment": c,
             "audit_mean": None if audit_mean is None else round(audit_mean, 2)}
        for i, (cid, q, err) in enumerate(qs or [("-", None, reason)]):
            db.save_audit(con, f"{audit_run}-{i}", hotkey, digest, cid, q, result == "pass", block,
                          {**d, "task_index": i, "error": err})
        db.add_event(con, f"audit.{result}", {"hotkey": hotkey, "audit_run": audit_run, "engine": digest,
                                              "live_mean": d["live_mean"], "audit_mean": d["audit_mean"],
                                              "reason": reason, "block": block})
        short = digest[7:19] if digest.startswith("sha256:") else digest
        log(f"[audit] {hotkey[:10]}… engine {short} live {live_mean:.1f} "
            f"audit {'—' if audit_mean is None else f'{audit_mean:.1f}'} -> {result.upper()}"
            + (f" ({reason})" if reason else ""))
        return {"hotkey": hotkey, "verdict": result, "engine": digest, "strategy": (c or {}).get("s"),
                "live_mean": live_mean, "audit_mean": audit_mean, "reason": reason, "block": block,
                "audit_run": audit_run, "tasks": [{"challenge_id": cid, "quality": q, "error": e} for cid, q, e in qs]}

    if c is None:
        return finish("fail", "none", [], "no engine commitment on chain")
    digest = c["e"]
    if row is not None and c.get("block") is not None:
        db.save_commitment(con, hotkey, row["registered_at_block"], digest, c.get("s"), c["block"])
    if not image_present(digest):
        return finish("fail", digest, [], "committed engine image not available")

    qs = []
    for i in range(tasks):
        cid = new_challenge(family=family)["challenge_id"]
        out = run_engine(digest, cid, f"{audit_run}-t{i}")
        if "source" in out:
            ev = score_source(cid, out["source"], job_id=f"{audit_run}-t{i}", miner_hotkey=hotkey)
            if ev.failure_class == "validator_outage":
                db.retire_challenge(con, cid, "audit task (validator outage)")
                return finish("inconclusive", digest, qs, f"validator outage: {ev.failure_reason}")
            qs.append((cid, ev.quality, None))
        else:
            qs.append((cid, 0.0, out.get("error")))
        db.retire_challenge(con, cid, "audit task finished")
        log(f"  task {i + 1}/{tasks} {cid}: Q {qs[-1][1]:.1f}" + (f" ({qs[-1][2]})" if qs[-1][2] else ""))
    passed, audit_mean = verdict([q for _, q, _ in qs], live_mean, margin)
    return finish("pass" if passed else "fail", digest, qs,
                  None if passed else f"audit mean {audit_mean:.1f} < live {live_mean:.1f} - {margin:g}")


def run_audits(*, network: str = "local", top: int = 2, family: str = "plate", hotkeys: list[str] | None = None,
               log=print) -> list[dict]:
    """Audit the top miners that currently earn weight (PRD: 'the top miners'), or the given hotkeys."""
    from cadrecover.chain.bootstrap import load_state
    from cadrecover.chain.neurons import metagraph_miners
    from cadrecover.validator.aggregate import standings

    state = load_state()
    miners = metagraph_miners(network, exclude_hotkeys={state["neurons"]["validator"]["hotkey"]})
    current = {(m.hotkey, m.registered_at_block) for m in miners}
    table = standings(db.connect(), current=current)
    picked = [s for s in table if s.hotkey in hotkeys] if hotkeys else [s for s in table if s.weight > 0][:top]
    if not picked:
        log("[audit] nobody earns weight: nothing to audit")
    return [audit_miner(s.hotkey, s.mean_quality, network=network, family=family, log=log) for s in picked]
