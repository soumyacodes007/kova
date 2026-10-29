"""Scores to weights (owner: agent B). PRD §"From scores to weights":

- identity is hotkey + registration block (a recycled UID starts fresh)
- rolling mean of Q over each identity's last WINDOW completed tasks; validator
  outages (quality NULL) are excluded for everyone; timeouts and failures count as 0
- an identity needs MIN_SAMPLES tasks before it can earn
- weight = max(0, mean Q - floor), normalized; nobody above the floor -> no update
- only identities registered now can earn (`current`); a failed engine audit zeroes a hotkey (`zeroed`)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from cadrecover.protocol import QUALITY_FLOOR

WINDOW = 20
MIN_SAMPLES = 1  # demo setting; raise for real runs (PRD: minimum sample count before rewards)


@dataclass
class Standing:
    hotkey: str
    registered_at_block: int
    uid: int
    label: str | None
    samples: int
    mean_quality: float
    above_floor: float
    weight: float = 0.0


def standings(con: sqlite3.Connection, *, window: int = WINDOW, min_samples: int = MIN_SAMPLES,
              floor: float = QUALITY_FLOOR, current: set[tuple[str, int]] | None = None,
              zeroed: set[str] | None = None) -> list[Standing]:
    rows = con.execute("""
        SELECT m.hotkey, m.registered_at_block, m.uid, m.label, e.quality
        FROM miners m
        JOIN assignments a ON a.miner_hotkey = m.hotkey AND a.registered_at_block = m.registered_at_block
        JOIN evaluations e ON e.job_id = a.job_id
        WHERE e.failure_class != 'validator_outage'
        ORDER BY e.evaluated_at DESC
    """).fetchall()
    per: dict[tuple[str, int], list] = {}
    meta: dict[tuple[str, int], tuple[int, str | None]] = {}
    for r in rows:
        key = (r["hotkey"], r["registered_at_block"])
        per.setdefault(key, [])
        meta[key] = (r["uid"], r["label"])
        if len(per[key]) < window:
            per[key].append(r["quality"] or 0.0)
    out = []
    for key, qs in per.items():
        mean = sum(qs) / len(qs)
        eligible = (len(qs) >= min_samples and (current is None or key in current)
                    and key[0] not in (zeroed or set()))
        out.append(Standing(key[0], key[1], meta[key][0], meta[key][1], len(qs), mean,
                            max(0.0, mean - floor) if eligible else 0.0))
    total = sum(s.above_floor for s in out)
    for s in out:
        s.weight = s.above_floor / total if total > 0 else 0.0
    return sorted(out, key=lambda s: -s.mean_quality)
