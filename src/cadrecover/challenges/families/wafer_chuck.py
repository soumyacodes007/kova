"""Wafer chuck geometry and reference self-test (CAD worker env, build123d 0.13)."""

from __future__ import annotations

import math

from build123d import Align, Compound, Cylinder, Part, Pos

from cadrecover.challenges.families import wafer_chuck_spec as spec
from cadrecover.challenges.measure import measure
from cadrecover.protocol import FeatureMeasurement

_TIGHT = 1e-6  # a reference must match its own spec exactly (numerically)


def build(params: dict[str, float]) -> Part:
    t = params["thickness"]
    part = Cylinder(params["plate_diameter"] / 2, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    diameters = spec.hole_diameters(params)
    cutters = [Pos(x, y, t / 2) * Cylinder(diameters[name] / 2, 3 * t) for name, (x, y) in spec.hole_centers(params).items()]
    part = part - Compound(cutters)  # one boolean for all holes
    return part.clean() if hasattr(part, "clean") else part


def expected_volume(params: dict[str, float]) -> float:
    t = params["thickness"]
    disc = lambda d: math.pi * (d / 2) ** 2  # noqa: E731 - circle area
    return disc(params["plate_diameter"]) * t - sum(disc(d) for d in spec.hole_diameters(params).values()) * t


def expected_features(params: dict[str, float]) -> list[FeatureMeasurement]:
    t = params["thickness"]
    feats = [
        FeatureMeasurement(name="width", kind="length", length=params["plate_diameter"]),
        FeatureMeasurement(name="length", kind="length", length=params["plate_diameter"]),
        FeatureMeasurement(name="thickness", kind="length", length=t),
    ]
    diameters = spec.hole_diameters(params)
    for name, (x, y) in spec.hole_centers(params).items():
        feats.append(FeatureMeasurement(name=name, kind="hole", center=(x, y, t), axis=(0.0, 0.0, 1.0),
                                        diameter=diameters[name]))
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


def iou(a: Part, b: Part) -> float:
    """Solid intersection-over-union via CAD booleans."""
    va, vb = a.volume, b.volume
    inter = a.intersect(b)  # build123d 0.13 returns a ShapeList (possibly empty)
    if inter is None:
        vi = 0.0
    elif hasattr(inter, "volume"):
        vi = inter.volume
    else:
        vi = sum(s.volume for s in inter)
    union = va + vb - vi
    return vi / union if union > 0 else 0.0


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
