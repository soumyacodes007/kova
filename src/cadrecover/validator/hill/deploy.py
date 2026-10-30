"""Reviewable custom-model deployment plans; live deployment is off by default.

Official Chutes docs show a vision template example, but the current SDK's
ChatMessage.content is typed as str. Image-array acceptance must be verified
before enabling custom vision deployments. The SDK README also requires a $50
balance to build images. Neither requirement affects catalog inference.
"""

from __future__ import annotations

import math
import os
import re
import shlex
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from cadrecover.validator.hill.budget import BudgetGuard


class DeployUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DeploymentPlan:
    repo: str
    revision: str
    username: str
    hourly_rate_usd: float
    max_runtime_s: int = 600

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*", self.repo):
            raise ValueError("A valid public owner/repo is required")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", self.revision):
            raise ValueError("Revision must be a full 40-hex commit")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.username):
            raise ValueError("A valid Chutes username is required")
        if not math.isfinite(self.hourly_rate_usd) or self.hourly_rate_usd <= 0:
            raise ValueError("A verified positive GPU hourly rate is required")
        if type(self.max_runtime_s) is not int or not 1 <= self.max_runtime_s <= 3600:
            raise ValueError("Runtime limit must be between 1 and 3600 seconds")

    @property
    def fee_usd(self) -> float:
        return 3 * self.hourly_rate_usd

    @property
    def reservation_usd(self) -> float:
        return self.fee_usd + self.hourly_rate_usd * self.max_runtime_s / 3600

    @property
    def endpoint(self) -> str:
        slug = re.sub(r"[^a-z0-9-]", "-", self.repo.lower())
        return f"https://{self.username}-{slug}.chutes.ai/v1/chat/completions"

    @property
    def source(self) -> str:
        # Source contains only reviewed deployment configuration, no API key.
        return (
            "from chutes.chute import NodeSelector\n"
            "from chutes.chute.template.vllm import build_vllm_chute\n\n"
            "chute = build_vllm_chute(\n"
            f"    username={self.username!r}, model_name={self.repo!r},\n"
            f"    revision={self.revision!r},\n"
            "    node_selector=NodeSelector(gpu_count=1, min_vram_gb_per_gpu=24),\n"
            "    concurrency=4, max_instances=1, shutdown_after_seconds=60,\n"
            "    allow_external_egress=False,\n"
            ")\n"
        )

    @property
    def commands(self) -> list[list[str]]:
        # SDK builder uses model_name as the chute's actual registered name.
        return [["chutes", "build", "hill_chute:chute", "--wait"],
                ["chutes", "deploy", "hill_chute:chute", "--accept-fee"],
                ["chutes", "chutes", "delete", self.repo]]

    def dry_run(self) -> str:
        return (self.source + "\n" + "\n".join(shlex.join(c) for c in self.commands)
                + f"\nEstimated fee ${self.fee_usd:.6f}; fee + runtime reservation "
                + f"${self.reservation_usd:.6f}; no deployment executed.\n")


@dataclass
class DeploymentLease:
    endpoint: str
    expires_at: float

    def check_active(self) -> None:
        if time.monotonic() >= self.expires_at:
            raise DeployUnavailable("Deployment runtime limit reached")


@contextmanager
def deployed(plan: DeploymentPlan, budget: BudgetGuard, match_id: str, workdir: Path, *,
             allow_live: bool = False, verified_balance_usd: float | None = None,
             vision_verified: bool = False, billing_bound_verified: bool = False,
             run: Callable = subprocess.run) -> Iterator[DeploymentLease]:
    """Future opt-in executor. No caller may treat a refused deployment as scored.

    Live operation additionally requires evidence of image-array support and a
    provider billing bound covering deletion latency/minimum billing increments.
    Those facts are presently unverified. The local deletion watchdog is an
    extra guard, and cannot establish a remote provider's billing guarantee.
    Unknown actual fees/runtime keep the full reservation in the shared ledger.
    """
    if os.environ.get("CHUTES_DEPLOY_ENABLED", "0") != "1":
        raise DeployUnavailable("deploy disabled on this network")
    if not allow_live:
        raise DeployUnavailable("Live deployment requires the user's explicit OK")
    if verified_balance_usd is None or not math.isfinite(verified_balance_usd) or verified_balance_usd < 50:
        raise DeployUnavailable("Chutes image builds require a verified balance of at least $50")
    if not vision_verified:
        raise DeployUnavailable("Custom vLLM image-array support is unverified")
    if not billing_bound_verified:
        raise DeployUnavailable("Provider runtime billing bound is unverified")
    spend_id = budget.reserve(match_id, plan.repo, plan.reservation_usd, kind="deployment")
    workdir = Path(workdir)
    commands = plan.commands
    cleanup_lock = threading.Lock()
    deleted = False
    cleanup_failed = False
    timer = None

    def invoke(command: list[str], timeout: float) -> None:
        run(command, cwd=workdir, timeout=timeout, capture_output=True, text=True, check=True)

    def cleanup() -> None:
        nonlocal deleted, cleanup_failed
        with cleanup_lock:
            if deleted:
                return
            try:
                invoke(commands[2], 30)
                deleted = True
                cleanup_failed = False
            except Exception:
                cleanup_failed = True

    try:
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "hill_chute.py").write_text(plan.source, encoding="utf-8", newline="\n")
        invoke(commands[0], 600)
        deadline = time.monotonic() + plan.max_runtime_s
        timer = threading.Timer(plan.max_runtime_s, cleanup)
        timer.daemon = True
        timer.start()
        invoke(commands[1], plan.max_runtime_s)
        lease = DeploymentLease(plan.endpoint, deadline)
        lease.check_active()
        yield lease
    except (subprocess.SubprocessError, OSError):
        # Do not expose subprocess output; CLI output can contain credentials.
        raise DeployUnavailable("Chutes build/deploy command failed") from None
    finally:
        if timer is not None:
            timer.cancel()
        cleanup()
        budget.mark_unknown(spend_id)
        if cleanup_failed:
            raise DeployUnavailable("Chutes deletion failed; deployment may remain active and charge is reserved")
