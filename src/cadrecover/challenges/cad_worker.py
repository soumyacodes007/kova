"""CAD worker entry point (CAD env). Prints one JSON object on stdout.

  python -m cadrecover.challenges.cad_worker sample --family plate --seed N
  python -m cadrecover.challenges.cad_worker build --family plate --params '{...}' --out DIR --name s0

`build` refuses to write a reference that fails its self-test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from build123d import export_step

from cadrecover.challenges.families import plate, plate_spec

FAMILIES = {"plate": (plate_spec, plate)}


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
    a = p.parse_args(argv)

    fam_spec, fam_geom = FAMILIES[a.family]
    if a.cmd == "sample":
        print(json.dumps({"params": fam_spec.sample(a.seed)}))
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
