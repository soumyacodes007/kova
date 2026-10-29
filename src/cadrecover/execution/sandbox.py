"""Run miner code in a fresh sandbox container (owner: agent A).

One container per parameter set: no network, read-only root, non-root user, all
capabilities dropped, no new privileges, CPU/memory/PID caps and a hard timeout.
No wallets, tokens, ground truth or Docker socket are mounted: only the miner's
source and overrides (read-only) and an empty output folder.

This is a constrained hackathon environment, not hostile-grade isolation.
Mainnet needs disposable worker machines.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

IMAGE = "cadrecover-sandbox:build123d-0.13.0"
TIME_LIMIT_S = 60
MEMORY = "1g"
CPUS = "1"
PIDS = "64"


class SandboxUnavailable(RuntimeError):
    """Infrastructure problem (Docker down, image missing): a validator outage, not a miner failure."""


@dataclass
class BuildResult:
    ok: bool
    step: Path | None
    error_type: str | None
    error: str | None
    seconds: float


def image_ready() -> bool:
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0


def run_build(source: str, overrides: dict[str, float], work: Path, *, time_limit: int = TIME_LIMIT_S) -> BuildResult:
    if shutil.which("docker") is None or not image_ready():
        raise SandboxUnavailable(f"docker or image {IMAGE} not available (build it: docker build -t {IMAGE} images/cad-worker)")
    job, out = work / "job", work / "out"
    job.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (job / "source.py").write_text(source)
    (job / "overrides.json").write_text(json.dumps(overrides))
    name = f"cadrecover-build-{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m,mode=1777",
        "--memory", MEMORY, "--memory-swap", MEMORY, "--cpus", CPUS, "--pids-limit", PIDS,
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000",
        "-e", f"TIME_LIMIT={time_limit}",
        "-v", f"{job}:/job:ro", "-v", f"{out}:/out:rw",
        IMAGE,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 30)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return BuildResult(False, None, "timeout", f"container exceeded {time_limit + 30}s", float(time_limit + 30))
    result_file = out / "result.json"
    if not result_file.exists():
        # The runner always writes a result; no file means the container itself died (OOM kill, etc.).
        oom = proc.returncode == 137
        return BuildResult(False, None, "killed" if oom else "no_result",
                           f"container exited {proc.returncode}" + (" (memory limit)" if oom else "") +
                           (f": {proc.stderr.strip()[-300:]}" if proc.stderr.strip() else ""), 0.0)
    r = json.loads(result_file.read_text())
    step = out / "candidate.step"
    return BuildResult(r["ok"], step if r["ok"] and step.exists() else None, r.get("error_type"), r.get("error"),
                       float(r.get("seconds") or 0.0))
