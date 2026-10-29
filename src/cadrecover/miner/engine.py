"""A miner's engine as a standalone program (owner: agent C), packaged as a Docker image whose
image ID the miner commits on-chain. The auditor runs that exact image with no network on a
hidden task and scores the output like any live answer.

  docker run --network none -v <task>:/task:ro <engine>  ->  JSON {source, model_id, strategy_version}

/task holds challenge.json (public record) and drawing.png. The baked-in strategy is
CADRECOVER_ENGINE_STRATEGY. Mock strategies also need the task's private record mounted
(dev only, labelled mock), exactly as they need it when serving live.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cadrecover.miner import strategies
from cadrecover.protocol import PublicChallenge


def main(task_dir: str = "/task") -> int:
    task = Path(task_dir)
    name = os.environ.get("CADRECOVER_ENGINE_STRATEGY", "")
    try:
        strategy = strategies.get(name)
        challenge = PublicChallenge.model_validate_json((task / "challenge.json").read_text())
        sol = strategy.solve(challenge, (task / "drawing.png").read_bytes(), job_id=os.environ.get("JOB_ID", "audit"))
    except Exception as e:  # noqa: BLE001 - report, the auditor scores a failure as 0
        print(json.dumps({"error": f"{type(e).__name__}: {e}", "strategy": name}))
        return 1
    print(json.dumps({"source": sol.source, "model_id": sol.model_id, "strategy": strategy.name,
                      "strategy_version": sol.strategy_version}))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
