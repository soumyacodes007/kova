"""Multi-port vacuum chamber geometry and reference self-test (CAD worker env, build123d 0.13).

The body is a hollow cylinder; every port is built once as a tube stub plus flange disc (bolt holes cut in the
small solid first), placed at its angle, fused to the body, and then its bore is cut through flange, stub and
wall. That keeps the boolean count low enough for a few-second build.
"""

from __future__ import annotations

import math

from build123d import Align, Cylinder, Part, Pos, Rot

from cadrecover.challenges.families import vacuum_chamber_spec as spec
from cadrecover.challenges.measure import measure
from cadrecover.evaluation.checks import axis_gap, offset, through_axis
from cadrecover.protocol import FeatureMeasurement

_TIGHT = 1e-5  # a reference must match its own spec to this (numerically)
_VOL_TOL = 5e-5  # relative: OCC integrates the saddle-shaped stub surfaces numerically


def _along_x(radius: float, length: float, x_centre: float, u: float = 0.0, v: float = 0.0) -> Part:
    """A cylinder of the given size whose axis is +X, centred at (x_centre, u, v)."""
    return Pos(x_centre, u, v) * Rot(0, 90, 0) * Cylinder(radius, length)


def _port(params: dict[str, float]) -> Part:
    """One port in its own frame: axis along +X from the Z axis, centred on z = 0; bolt holes cut."""
    r, ft, fd = params["port_reach"], params["flange_thickness"], params["flange_diameter"]
    x0 = params["body_bore_diameter"] / 4  # starts inside the hollow body; the body bore cut removes that part
    x1 = r - ft
    port = _along_x(spec.stub_diameter(params) / 2, x1 - x0, (x0 + x1) / 2) + _along_x(fd / 2, ft, r - ft / 2)
    n, bc, bd = spec.bolt_count(params), params["port_bolt_circle_diameter"] / 2, params["port_bolt_hole_diameter"]
    for j in range(n):
        phi = math.pi / 2 + 2 * math.pi * j / n  # hole 1 straight up, then counter-clockwise around the axis
        port -= _along_x(bd / 2, 2 * ft, r - ft / 2, bc * math.cos(phi), bc * math.sin(phi))
    return port


def build(params: dict[str, float]) -> Part:
    d, db, h = params["body_diameter"], params["body_bore_diameter"], params["body_height"]
    part = Cylinder(d / 2, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    port = _port(params)
    angles = spec.port_angles(params)
    for ang in angles:
        part += Pos(0, 0, h / 2) * Rot(0, 0, ang) * port
    part -= Pos(0, 0, h / 2) * Cylinder(db / 2, 3 * h)  # the hollow body (also trims the stubs' inner ends)
    r, ft = params["port_reach"], params["flange_thickness"]
    bore_from = db / 4
    for ang in angles:
        part -= Pos(0, 0, h / 2) * Rot(0, 0, ang) * _along_x(params["port_diameter"] / 2, r + ft - bore_from,
                                                            (bore_from + r + ft) / 2)
    return part.clean() if hasattr(part, "clean") else part


def _integral(a: float, f) -> float:
    """integral over |u| <= a of f(u) * 2 sqrt(a^2 - u^2) du: the volume of a column of cross-section pi a^2
    whose height at tangential offset u is f(u). Substituting u = a sin t makes the integrand smooth."""
    steps = 4000
    total = 0.0
    for k in range(steps):  # midpoint rule in t: error ~ 1e-9 relative
        t = -math.pi / 2 + (k + 0.5) * math.pi / steps
        total += f(a * math.sin(t)) * 2 * a * a * math.cos(t) ** 2
    return total * math.pi / steps


def expected_volume(params: dict[str, float]) -> float:
    """Volume of the reference from its spec alone. Exact for the body and flanges; the stubs and bores meet the
    cylindrical body along saddle curves, so those columns are integrated across the port axis."""
    d, db, h = params["body_diameter"], params["body_bore_diameter"], params["body_height"]
    p, s, r, ft = params["port_diameter"], spec.stub_diameter(params), params["port_reach"], params["flange_thickness"]
    area = lambda x: math.pi * (x / 2) ** 2  # noqa: E731 - circle area
    outer = lambda u: math.sqrt(d * d / 4 - u * u)  # noqa: E731 - the body's outer surface at offset u
    inner = lambda u: math.sqrt(db * db / 4 - u * u)  # noqa: E731 - the cavity's surface
    flange = (area(params["flange_diameter"]) - spec.bolt_count(params) * area(params["port_bolt_hole_diameter"])) * ft
    stub = _integral(s / 2, lambda u: r - ft - outer(u))  # stub outside the body, bore not yet cut
    bore = _integral(p / 2, lambda u: r - inner(u))  # the bore removes the whole column, cavity to flange face
    return (area(d) - area(db)) * h + spec.port_count(params) * (flange + stub - bore)


def expected_features(params: dict[str, float]) -> list[FeatureMeasurement]:
    r, h = params["port_reach"], params["body_height"]
    feats = [
        FeatureMeasurement(name="width", kind="length", length=2 * r),  # ports on +X and -X
        FeatureMeasurement(name="length", kind="length", length=2 * r),  # ports on +Y and -Y
        FeatureMeasurement(name="thickness", kind="length", length=h),
        # the body bore is measured like any hole; it is told apart by being centred
        FeatureMeasurement(name="body_bore", kind="hole", center=(0.0, 0.0, h), axis=(0.0, 0.0, 1.0),
                           diameter=params["body_bore_diameter"]),
    ]
    for f in spec.port_features(params):
        feats.append(FeatureMeasurement(name=f["name"], kind=f["kind"], center=f["center"], axis=f["axis"],
                                        diameter=f["diameter"]))
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
                ok = (offset(m.center, e.center, through_axis(e)) <= tol and abs(m.diameter - e.diameter) <= tol
                      and axis_gap(m, e) <= tol / 50 and abs(sum((m.center[i] - e.center[i]) * through_axis(e)[i]
                                                                  for i in range(3))) <= tol)
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
    part = build(params) if part is None else part  # (`part or ...` would evaluate the solid's truthiness: slow)
    checks: dict[str, bool | str] = {}
    is_valid = part.is_valid() if callable(part.is_valid) else part.is_valid
    checks["valid_solid"] = bool(is_valid)
    checks["single_solid"] = len(part.solids()) == 1
    vol, exp = part.volume, expected_volume(params)
    checks["volume"] = abs(vol - exp) <= max(_VOL_TOL * exp, _TIGHT)
    measured = measure(part)
    problems = match(expected_features(params), measured, _TIGHT)
    checks["features"] = not problems
    ok = all(v is True for v in checks.values())
    return {"ok": ok, "checks": checks, "volume": vol, "expected_volume": exp,
            "feature_problems": problems, "measurements": [m.model_dump() for m in measured]}
