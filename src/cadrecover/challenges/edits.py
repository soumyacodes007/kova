"""Discriminative hidden-edit sampler (CAD worker env). PRD v2.1:

1. at least one critical feature moves more than 5x its positional tolerance vs s0
2. the reference's overlap with itself across the edit, IoU(ref s0, ref sk), is below 0.85

Together they guarantee a model that ignores overrides misplaces features at every
hidden set (C_s = 0) and can't hide behind high overlap, so it tops out at 25.
"""

from __future__ import annotations

import random

from build123d import Part

SHIFT_FACTOR = 5.0
MAX_SELF_IOU = 0.85


def sample_edits(spec, geom, base: dict[str, float], seed: int, n: int = 3, max_tries: int = 400) -> list[dict]:
    rng = random.Random(seed ^ 0x5EED)
    ref0: Part = geom.build(base)
    min_shift = SHIFT_FACTOR * spec.POSITION_TOL
    accepted: list[dict] = []
    for _ in range(max_tries):
        if len(accepted) == n:
            return accepted
        cand = spec.edit_candidate(base, rng)
        if cand is None or any(cand == a["values"] for a in accepted):
            continue
        shift = spec.max_feature_shift(base, cand)
        if shift <= min_shift:
            continue
        part = geom.build(cand)
        if not geom.self_test(cand, part)["ok"]:
            continue
        self_iou = geom.iou(ref0, part)
        if self_iou >= MAX_SELF_IOU:
            continue
        accepted.append({"values": cand, "overrides": spec.overrides(base, cand), "part": part,
                         "max_feature_shift_mm": shift, "reference_self_iou": self_iou})
    raise RuntimeError(f"found only {len(accepted)} discriminative edits in {max_tries} tries")
