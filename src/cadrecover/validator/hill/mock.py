"""Scripted demo miner for the hill (localnet only). Not a model and never presented as one.

It reuses Track A's labelled mock strategies: they read the drawn values from the
validator's private record and emit template build123d code. The source is then
scored exactly like a catalog reply (same sandbox, same evaluator). No Chutes call,
no spend. Everything else is delegated to the real Chutes runner.
"""

from __future__ import annotations

import hashlib
import os
import time

from cadrecover.validator.hill.chutes import Generation

MOCK_PREFIX = "mock:"
MOCK_STRATEGIES = ("mock-noisy", "mock-oracle")


def mock_fingerprint(strategy: str, hotkey: str) -> str:
    return hashlib.sha256(f"mock-strategy:{strategy}:{hotkey}".encode()).hexdigest()


class HillRunner:
    """Routes `mock:<strategy>` ids to the scripted miner and everything else to Chutes."""

    def __init__(self, chutes):
        self.chutes = chutes
        self.budget = chutes.budget

    @property
    def _catalog(self):
        return self.chutes._catalog

    def catalog(self):
        return self.chutes.catalog()

    def close(self):
        self.chutes.close()

    def generate(self, model_id, public, png_bytes, match_id, harness=None):
        if not model_id.startswith(MOCK_PREFIX):
            return self.chutes.generate(model_id, public, png_bytes, match_id,
                                        *(() if harness is None else (harness,)))
        from cadrecover.miner import strategies
        strategy = model_id[len(MOCK_PREFIX):]
        if strategy not in MOCK_STRATEGIES:
            raise ValueError(f"unknown mock strategy {strategy!r}")
        os.environ["CADRECOVER_DEV_ORACLE"] = "1"  # the strategies refuse to read private values otherwise
        started = time.monotonic()
        solution = strategies.get(strategy).solve(public, png_bytes, f"{match_id}-{public.challenge_id}")
        return Generation(solution.source, None, time.monotonic() - started, None, None, 0.0)
