"""Drawing worker entry point (drawing env: draftwright, AGPL; validator-side only).

  python -m cadrecover.challenges.drawing_worker draw --step REF.step --out DIR \
      --title T --number N --require '["120", "⌀6.5", ...]' [--waive '["holes:bore.through"]'] --seed S [--clean]

Reads the reference STEP, draws it with draftwright, and checks coverage:
1. draftwright's own requirement ledger: every recognised requirement is placed, except the few a
   family explicitly waives (draftwright false negatives on a centred bore; each is still reported)
2. the task's required values each appear in a rendered dimension/callout label
Then rasterizes the SVG to PNG and (unless --clean) adds a seeded scan look.
Prints one JSON object; `coverage.ok` false means the caller must reject it.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import pymupdf
from build123d import import_step
from draftwright import build_drawing
from PIL import Image, ImageFilter

DPI = 150


def labels(dwg) -> list[str]:
    out = []
    for name in dwg.annotations():
        label = getattr(dwg.get_annotation(name), "label", None)
        if isinstance(label, str) and label.strip():
            out.append(label.strip())
    return out


def coverage(dwg, required: list[str], waive: list[str] | None = None) -> dict:
    report = dwg.report()
    reqs = (report.get("recognition") or {}).get("requirements") or []
    waive = set(waive or [])
    unplaced, waived = [], []
    for r in reqs:
        if r.get("state") == "placed":
            continue
        entry = f"{r.get('family')}:{r.get('parameter_id')} ({r.get('state')})"
        (waived if f"{r.get('family')}:{r.get('parameter_id')}" in waive else unplaced).append(entry)
    rendered = labels(dwg)
    tokens = set()
    for text in rendered:
        text = text.replace("ø", "⌀")  # draftwright writes diameters as both "ø" and "⌀"
        tokens.add(text)
        tokens.update(text.replace("×", " ").replace("THRU", " ").split())
    missing = [want for want in required if want not in tokens]
    return {"ok": not unplaced and not missing, "ledger_requirements": len(reqs), "unplaced": unplaced, "waived": waived,
            "required": required, "missing_required": missing, "labels": rendered}


def scan_look(png: Path, seed: int) -> None:
    """Old-scan feel: slight rotation, blur, paper tint and noise. Seeded, so reproducible."""
    rng = random.Random(seed)
    img = Image.open(png).convert("L")
    img = img.rotate(rng.uniform(-0.6, 0.6), resample=Image.BICUBIC, expand=False, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 0.8)))
    arr = np.asarray(img, dtype=np.float32)
    noise = np.random.default_rng(seed).normal(0, 6, arr.shape)
    arr = np.clip(arr * 0.93 + noise + 8, 0, 255)
    tint = np.stack([arr * 1.0, arr * 0.985, arr * 0.94], axis=-1)  # warm paper
    Image.fromarray(np.clip(tint, 0, 255).astype(np.uint8), "RGB").save(png, optimize=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--step", type=Path, required=True)
    d.add_argument("--out", type=Path, required=True)
    d.add_argument("--title", default="Part")
    d.add_argument("--number", default="DWG-0001")
    d.add_argument("--require", default="[]")
    d.add_argument("--waive", default="[]", help="JSON list of ledger ids (family:parameter_id) a family may leave unplaced")
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--clean", action="store_true")
    a = p.parse_args(argv)

    a.out.mkdir(parents=True, exist_ok=True)
    part = import_step(str(a.step))
    dwg = build_drawing(part, title=a.title, number=a.number)
    lint = dwg.lint_summary()
    cov = coverage(dwg, json.loads(a.require), json.loads(a.waive))
    svg = Path(dwg.export(str(a.out / "drawing"), formats=("svg",))["svg"])
    png = a.out / "drawing.png"
    pymupdf.open(str(svg))[0].get_pixmap(dpi=DPI).save(str(png))
    if not a.clean:
        scan_look(png, a.seed)
    print(json.dumps({
        "svg": str(svg), "png": str(png), "coverage": cov,
        "lint": {k: lint.get(k) for k in ("passed", "score", "errors", "warnings")},
    }, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
