"""CAD worker entry point (CAD env). Prints one JSON object on stdout.

  python -m cadrecover.challenges.cad_worker sample --family plate --seed N
  python -m cadrecover.challenges.cad_worker build --family plate --params '{...}' --out DIR --name s0
  python -m cadrecover.challenges.cad_worker edits --family plate --params '{...}' --seed N --out DIR

`build` refuses to write a reference that fails its self-test; `edits` writes
s1-s3 references for three discriminative hidden edits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from build123d import export_step

from cadrecover.challenges.families import flange, flange_spec, plate, plate_spec, wafer_chuck, wafer_chuck_spec
from cadrecover.challenges.families import vacuum_chamber, vacuum_chamber_spec

FAMILIES = {"plate": (plate_spec, plate), "flange": (flange_spec, flange),
            "wafer_chuck": (wafer_chuck_spec, wafer_chuck),
            "vacuum_chamber": (vacuum_chamber_spec, vacuum_chamber)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--family", required=True, choices=sorted(FAMILIES))
    s.add_argument("--seed", type=int, required=True)
    b = sub.add_parser("build")
    b.add_argument("--family", required=True, choices=sorted(FAMILIES))
    b.add_argument("--params", required=True)
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--name", default="s0")
    e = sub.add_parser("edits")
    e.add_argument("--family", required=True, choices=sorted(FAMILIES))
    e.add_argument("--params", required=True)
    e.add_argument("--seed", type=int, required=True)
    e.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)

    fam_spec, fam_geom = FAMILIES[a.family]
    if a.cmd == "sample":
        print(json.dumps({"params": fam_spec.sample(a.seed)}))
        return 0

    if a.cmd == "edits":
        from cadrecover.challenges.edits import sample_edits
        from cadrecover.challenges.measure import measure

        a.out.mkdir(parents=True, exist_ok=True)
        sets = []
        for i, ed in enumerate(sample_edits(fam_spec, fam_geom, json.loads(a.params), a.seed), start=1):
            step = a.out / f"s{i}.step"
            export_step(ed["part"], str(step))
            sets.append({"index": i, "values": ed["values"], "overrides": ed["overrides"], "step": str(step),
                         "sha256": _sha256(step), "volume": ed["part"].volume,
                         "measurements": [m.model_dump() for m in measure(ed["part"])],
                         "max_feature_shift_mm": ed["max_feature_shift_mm"],
                         "reference_self_iou": ed["reference_self_iou"]})
        print(json.dumps({"ok": True, "sets": sets}))
        return 0

    params = json.loads(a.params)
    if not fam_spec.is_valid(params):
        print(json.dumps({"ok": False, "error": "parameters out of range or no room for features"}))
        return 2
    part = fam_geom.build(params)
    test = fam_geom.self_test(params, part)
    if not test["ok"]:
        print(json.dumps({"ok": False, "error": "reference failed its self-test", "self_test": test}))
        return 3
    a.out.mkdir(parents=True, exist_ok=True)
    step = a.out / f"{a.name}.step"
    export_step(part, str(step))
    print(json.dumps({"ok": True, "step": str(step), "sha256": _sha256(step), "volume": test["volume"],
                      "measurements": test["measurements"], "self_test": test["checks"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
