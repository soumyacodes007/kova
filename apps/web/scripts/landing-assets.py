"""Rebuild the landing-page 3D assets from the real pipeline (run in the CAD env, WSL).

    ~/.cadrecover/envs/cad/bin/python apps/web/scripts/landing-assets.py ~/landing-assets

Not a challenge: nothing touches the DB. Builds one flange reference (first seed from 1000 with a hub and
6 bolts), a candidate whose bolt circle is 0.8 mm too large (every hole 0.4 mm out), scores the candidate
with the real checker, and writes GLBs plus a marker GLB at each failed hole. Prints the scores as JSON
(these are the numbers in lib/landing-data.ts).

The drawing images come from the drawing worker on the reference STEP, then a crop to WebP:

    envs/drawing/bin/python -m cadrecover.challenges.drawing_worker draw --step ~/landing-assets/flange.step \
        --out ~/landing-assets/scan --title "Vacuum flange" --number LEGACY-1987-1000 \
        --require "$(required labels of flange_spec.sample(1000))" --waive "$(flange_spec.LEDGER_WAIVERS)" --seed 1000
    crop (210, 400, 3465, 2450) -> public/assets/flange-drawing.webp (1800 px wide)
    crop (367, 472, 1560, 1640) -> public/assets/flange-drawing-top.webp (900 px)
"""

import json
import sys
from pathlib import Path

from build123d import Cylinder, Pos, export_gltf, export_step

from cadrecover.challenges.families import flange, flange_spec as spec
from cadrecover.challenges.measure import measure
from cadrecover.evaluation.checks import critical, dimensions

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

seed = next(s for s in range(1000, 5000)
            if spec.has_hub(p := spec.sample(s)) and spec.bolt_count(p) == 6)
params = spec.sample(seed)
ref = flange.build(params)
export_step(ref, str(out / "flange.step"))
export_gltf(ref, str(out / "flange-reference.glb"), binary=True)

wrong = dict(params, bolt_circle_diameter=params["bolt_circle_diameter"] + 0.8)
cand = flange.build(wrong)
export_gltf(cand, str(out / "flange-candidate.glb"), binary=True)

expected = flange.expected_features(params)
measured = measure(cand)
ok, failed = critical(expected, measured, spec.SIZE_TOL, spec.POSITION_TOL)
d, d_failed = dimensions(expected, measured, spec.SIZE_TOL)
iou = flange.iou(ref, cand)

# one ring per failed hole, at the candidate's hole, so the browser can light it up in the same frame
rings = None
t = params["thickness"]
for x, y in spec.bolt_centers(wrong).values():
    r = params["bolt_hole_diameter"] / 2
    ring = Pos(x, y, t / 2) * (Cylinder(r + 1.2, t + 0.6) - Cylinder(r + 0.15, t + 1.0))
    rings = ring if rings is None else rings + ring
export_gltf(rings, str(out / "flange-markers.glb"), binary=True)

print(json.dumps({
    "seed": seed, "params": params, "wrong_params": wrong,
    "critical_ok": ok, "geometry_iou": iou, "dimensions": d,
    "failed": [{"name": f.name, "message": f.message} for f in failed + d_failed],
}, indent=1, default=str))
