"""Score one submission end to end (services env). Owner: agent A.

For each of the 4 parameter sets: rebuild the miner's source in a fresh sandbox
container with that set's overrides, then hand all candidate STEP files to the
evaluator (CAD env, separate process) and build the Evaluation.

Sandbox infrastructure failures are validator outages (excluded for everyone);
anything the miner's code does wrong is a miner failure.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from cadrecover import paths
from cadrecover.execution import sandbox
from cadrecover.protocol import Evaluation, PrivateChallenge, SetScore


def load_private(challenge_id: str) -> PrivateChallenge:
    return PrivateChallenge.model_validate_json((paths.PRIVATE / challenge_id / "private.json").read_text())


def _blank_sets(private: PrivateChallenge) -> list[SetScore]:
    return [SetScore(index=s.index, values=s.values, valid=False, critical_ok=False, geometry=0, dimensions=0)
            for s in private.sets]


def score_source(challenge_id: str, source: str, *, job_id: str, miner_hotkey: str,
                 workdir: Path | None = None, glb_dir: Path | None = None) -> Evaluation:
    private = load_private(challenge_id)
    workdir = Path(workdir or tempfile.mkdtemp(prefix=f"score-{job_id}-"))
    candidates = []
    try:
        for ps in private.sets:
            r = sandbox.run_build(source, ps.overrides, workdir / f"s{ps.index}")
            candidates.append({"index": ps.index, "step": str(r.step) if r.step else None,
                               "error": None if r.ok else f"{r.error_type}: {r.error}"})
    except sandbox.SandboxUnavailable as e:
        return Evaluation(challenge_id=challenge_id, job_id=job_id, miner_hotkey=miner_hotkey,
                          sets=_blank_sets(private), failure_class="validator_outage", failure_reason=str(e))

    cmd = [str(paths.env_python("cad")), "-m", "cadrecover.evaluation.evaluator",
           "--private", str(paths.PRIVATE / challenge_id / "private.json"), "--candidates", json.dumps(candidates)]
    if glb_dir is not None:
        cmd += ["--glb-dir", str(glb_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=paths.HOME)
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    if proc.returncode != 0 or not lines:
        return Evaluation(challenge_id=challenge_id, job_id=job_id, miner_hotkey=miner_hotkey,
                          sets=_blank_sets(private), failure_class="validator_outage",
                          failure_reason=f"evaluator failed ({proc.returncode}): {proc.stderr[-500:]}")
    sets = [SetScore(**s) for s in json.loads(lines[-1])["sets"]]
    all_failed = all(c["step"] is None for c in candidates)
    return Evaluation(challenge_id=challenge_id, job_id=job_id, miner_hotkey=miner_hotkey, sets=sets,
                      failure_class="miner" if all_failed else "none",
                      failure_reason=candidates[0]["error"] if all_failed else None)
