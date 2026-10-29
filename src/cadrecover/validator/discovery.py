"""Which miners to query (owner: agent B).

Phase 5 uses a static list (`~/.cadrecover/miners.json`, written by
`scripts/run-miners.sh`) so the round loop can be built and tested before the
chain is wired. Phase 6 replaces it with the metagraph (axon "ip:port").
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cadrecover import paths

MINERS_FILE = paths.HOME / "miners.json"


@dataclass(frozen=True)
class MinerEndpoint:
    hotkey: str
    uid: int
    registered_at_block: int
    url: str
    label: str | None = None


def static_miners() -> list[MinerEndpoint]:
    if not MINERS_FILE.exists():
        raise FileNotFoundError(f"{MINERS_FILE} not found: start miners with scripts/run-miners.sh")
    return [MinerEndpoint(**m) for m in json.loads(MINERS_FILE.read_text())]
