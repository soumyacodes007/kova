"""Mounting plate geometry and reference self-test (CAD worker env, build123d 0.13)."""

from __future__ import annotations

import math

from build123d import Align, Box, Cylinder, Part, Pos

from cadrecover.challenges.families import plate_spec as spec
from cadrecover.challenges.measure import measure
from cadrecover.protocol import FeatureMeasurement

_TIGHT = 1e-6  # a reference must match its own spec exactly (numerically)


def build(params: dict[str, float]) -> Part:
    w, l, t = params["width"], params["length"], params["thickness"]
    part = Box(w, l, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cutter_h = 3 * t
    for x, y in spec.hole_centers(params).values():
        part -= Pos(x, y, t / 2) * Cylinder(params["hole_diameter"] / 2, cutter_h)
    if spec.has_slot(params):
        sl, sw = params["slot_length"], params["slot_width"]
        straight = sl - sw
        slot = Pos(0, 0, t / 2) * Box(straight, sw, cutter_h)
        slot += Pos(-straight / 2, 0, t / 2) * Cylinder(sw / 2, cutter_h)
        slot += Pos(straight / 2, 0, t / 2) * Cylinder(sw / 2, cutter_h)
        part -= slot
    return part


def expected_volume(params: dict[str, float]) -> float:
    w, l, t, d = params["width"], params["length"], params["thickness"], params["hole_diameter"]
    v = w * l * t - 4 * math.pi * (d / 2) ** 2 * t
    if spec.has_slot(params):
        sl, sw = params["slot_length"], params["slot_width"]
        v -= ((sl - sw) * sw + math.pi * (sw / 2) ** 2) * t
    return v


def expected_features(params: dict[str, float]) -> list[FeatureMeasurement]:
    t = params["thickness"]
    feats = [
        FeatureMeasurement(name="width", kind="length", length=params["width"]),
        FeatureMeasurement(name="length", kind="length", length=params["length"]),
        FeatureMeasurement(name="thickness", kind="length", length=t),
    ]
    for name, (x, y) in spec.hole_centers(params).items():
        feats.append(FeatureMeasurement(name=name, kind="hole", center=(x, y, t), axis=(0.0, 0.0, 1.0),
                                        diameter=params["hole_diameter"]))
    if spec.has_slot(params):
        feats.append(FeatureMeasurement(name="slot", kind="slot", center=(0.0, 0.0, t), axis=(1.0, 0.0, 0.0),
                                        diameter=params["slot_width"], length=params["slot_length"]))
    return feats


def match(expected: list[FeatureMeasurement], measured: list[FeatureMeasurement], tol: float) -> list[str]:
    """Names of expected features with no measured counterpart within `tol` (empty = all matched)."""
    missing = []
    pool = list(measured)
    for e in expected:
        hit = None
        for m in pool:
            if m.kind != e.kind:
                continue
            if e.kind == "length":
                ok = m.name == e.name and abs(m.length - e.length) <= tol
            else:
                ok = (math.dist(m.center, e.center) <= tol and abs(m.diameter - e.diameter) <= tol
                      and (e.length is None or abs(m.length - e.length) <= tol))
            if ok:
                hit = m
                break
        if hit is None:
            missing.append(e.name)
        else:
            pool.remove(hit)
    extra = [m.name for m in pool if m.kind != "length"]
    return missing + [f"unexpected:{n}" for n in extra]


def self_test(params: dict[str, float], part: Part | None = None) -> dict:
    """The reference must be a single valid solid with exactly the specified geometry."""
    part = part or build(params)
    checks: dict[str, bool | str] = {}
    is_valid = part.is_valid() if callable(part.is_valid) else part.is_valid
    checks["valid_solid"] = bool(is_valid)
    checks["single_solid"] = len(part.solids()) == 1
    vol, exp = part.volume, expected_volume(params)
    checks["volume"] = abs(vol - exp) <= max(_TIGHT, 1e-9 * exp)
    measured = measure(part)
    problems = match(expected_features(params), measured, 1e-5)
    checks["features"] = not problems
    ok = all(v is True for v in checks.values())
    return {"ok": ok, "checks": checks, "volume": vol, "expected_volume": exp, "feature_problems": problems,
            "measurements": [m.model_dump() for m in measured]}
