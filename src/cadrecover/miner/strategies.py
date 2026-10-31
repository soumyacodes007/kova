"""Miner strategies (owner: agent C).

Until a vision-model API key is configured, honest strategies are MOCKS that stand
in for "reading the drawing": they look up the true drawn values in the local
private record. That only works on the validator's own machine, only with
CADRECOVER_DEV_ORACLE=1, and every result is labelled `mock`. They exist so the
whole loop (signed jobs, sandbox, scoring, weights) can run end to end today.

  mock-oracle        reads perfectly                               (honest mock)
  mock-noisy         sometimes misreads a dimension (seeded/job)    (honest mock)
  diag-constant      ignores overrides                              (diagnostic, expect 25)
  diag-proportional  holes scale with the part (plate edge offset / flange bolt circle)  (diagnostic, expect 25)
  diag-wrong-holes   hole diameter +30%                             (diagnostic, expect 0)
  diag-crash         forbidden import                               (diagnostic, expect 0)
  claude-vision      real VLM strategy; needs ANTHROPIC_API_KEY     (not wired yet)
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass

from cadrecover import paths
from cadrecover.miner.templates import SOURCES, source_for
from cadrecover.protocol import PublicChallenge


class StrategyUnavailable(RuntimeError):
    pass


@dataclass
class Solution:
    source: str
    model_id: str
    strategy_version: str
    notes: str = ""


class Strategy:
    name = "base"
    version = "0.1.0"
    kind = "honest"  # honest | mock | diagnostic

    def solve(self, challenge: PublicChallenge, drawing_png: bytes, job_id: str) -> Solution:
        raise NotImplementedError


def _oracle_read(challenge: PublicChallenge) -> dict[str, float]:
    """Mock 'reading': the true drawn values from the local private record. Dev only."""
    if os.environ.get("CADRECOVER_DEV_ORACLE") != "1":
        raise StrategyUnavailable("mock strategies need CADRECOVER_DEV_ORACLE=1 (local development only)")
    record = paths.PRIVATE / challenge.challenge_id / "private.json"
    if not record.exists():
        raise StrategyUnavailable("mock oracle only works on the validator's own machine")
    return json.loads(record.read_text())["sets"][0]["values"]


def _require_family(challenge: PublicChallenge) -> None:
    if challenge.family not in SOURCES:
        raise StrategyUnavailable(f"no template for family {challenge.family!r} yet")


class MockOracle(Strategy):
    name, kind = "mock-oracle", "mock"
    mode = "honest"

    def solve(self, challenge, drawing_png, job_id):
        _require_family(challenge)
        drawn = _oracle_read(challenge)
        return Solution(source_for(challenge.family, drawn, self.mode, label=self.name), model_id="mock:oracle",
                        strategy_version=self.version)


class MockNoisy(Strategy):
    """Like a real reader that sometimes slips: misreads thickness (costs G and D) or hole size (fails C)."""

    name, kind = "mock-noisy", "mock"

    def solve(self, challenge, drawing_png, job_id):
        _require_family(challenge)
        drawn = dict(_oracle_read(challenge))
        rng = random.Random(int(hashlib.sha256(job_id.encode()).hexdigest(), 16))
        hole_key = {"flange": "bolt_hole_diameter", "wafer_chuck": "vacuum_hole_diameter",
                    "vacuum_chamber": "port_bolt_hole_diameter"}.get(challenge.family, "hole_diameter")
        height_key = "flange_thickness" if challenge.family == "vacuum_chamber" else "thickness"  # a slip that costs only G and D
        roll, notes = rng.random(), "read cleanly"
        if roll < 0.15:
            drawn[hole_key] += 0.5
            notes = "misread hole diameter by +0.5 mm"
        elif roll < 0.50:
            drawn[height_key] += rng.choice((-1.0, 1.0))
            notes = "misread thickness by 1 mm"
        return Solution(source_for(challenge.family, drawn, "honest", label=self.name), model_id="mock:noisy",
                        strategy_version=self.version, notes=notes)


def _diagnostic(name: str, mode: str):
    class Diagnostic(MockOracle):
        pass

    Diagnostic.name, Diagnostic.kind, Diagnostic.mode = name, "diagnostic", mode
    Diagnostic.__name__ = f"Diag_{mode}"
    return Diagnostic


class ClaudeVision(Strategy):
    name, kind = "claude-vision", "honest"

    def solve(self, challenge, drawing_png, job_id):
        raise StrategyUnavailable("claude-vision is not wired yet: set ANTHROPIC_API_KEY and implement "
                                  "cadrecover.miner.strategies.ClaudeVision (see notes/agent-c.md)")


STRATEGIES: dict[str, type[Strategy]] = {
    "mock-oracle": MockOracle,
    "mock-noisy": MockNoisy,
    "diag-constant": _diagnostic("diag-constant", "constant"),
    "diag-proportional": _diagnostic("diag-proportional", "proportional"),
    "diag-wrong-holes": _diagnostic("diag-wrong-holes", "wrong_holes"),
    "diag-crash": _diagnostic("diag-crash", "crash"),
    "claude-vision": ClaudeVision,
}


def get(name: str) -> Strategy:
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}; choose from {sorted(STRATEGIES)}")
    return STRATEGIES[name]()
