"""Evaluator entry point (CAD worker env): candidate STEP files in, per-set scores out.

  python -m cadrecover.evaluation.evaluator --private PRIVATE.json \
      --candidates '[{"index": 0, "step": "/path/s0.step"}, {"index": 1, "step": null, "error": "..."}, ...]' \
      [--glb-dir DIR]

This process never sees miner code: it only imports the STEP files the sandbox
produced (the PRD's "second constrained process"). Prints one JSON object.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build123d import export_gltf, import_step

from cadrecover import paths
from cadrecover.challenges.families import plate, plate_spec
from cadrecover.evaluation.checks import score_set
from cadrecover.protocol import FailedCheck, PrivateChallenge, SetScore

FAMILIES = {"plate": (plate_spec, plate)}


def _load(step: str | None):
    if not step:
        return None, None
    try:
        return import_step(step), None
    except Exception as e:  # noqa: BLE001 - an unreadable STEP is a miner failure for that set
        return None, f"could not import candidate STEP: {e}"


def evaluate(private: PrivateChallenge, candidates: list[dict], glb_dir: Path | None = None) -> list[SetScore]:
    spec, geom = FAMILIES[private.family]
    by_index = {c["index"]: c for c in candidates}
    scores = []
    for ps in private.sets:
        cand = by_index.get(ps.index, {})
        reference = import_step(str(paths.PRIVATE / ps.reference.path))
        part, load_error = _load(cand.get("step"))
        s = score_set(ps.index, ps.values, reference, part, geom.expected_features(ps.values),
                      iou_fn=geom.iou, size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
        notes = [m for m in (cand.get("error"), load_error) if m]
        if notes:
            s.failed_checks = [FailedCheck(name="build", message="; ".join(notes))] + s.failed_checks
        if glb_dir is not None:
            glb_dir.mkdir(parents=True, exist_ok=True)
            export_gltf(reference, str(glb_dir / f"s{ps.index}.reference.glb"), binary=True)
            if part is not None:
                export_gltf(part, str(glb_dir / f"s{ps.index}.candidate.glb"), binary=True)
        scores.append(s)
    return scores


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--private", type=Path, required=True)
    p.add_argument("--candidates", required=True)
    p.add_argument("--glb-dir", type=Path, default=None)
    a = p.parse_args(argv)
    private = PrivateChallenge.model_validate_json(a.private.read_text())
    if len(private.sets) != 4:
        print(json.dumps({"ok": False, "error": f"challenge has {len(private.sets)} parameter sets, expected 4"}))
        return 2
    scores = evaluate(private, json.loads(a.candidates), a.glb_dir)
    print(json.dumps({"ok": True, "sets": [s.model_dump(mode="json") for s in scores]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
