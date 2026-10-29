"""Per-set checks: V, C, G, D (CAD worker env). Owner: agent A.

Scores one candidate solid against the reference at the same parameter values.
The score itself always comes from cadrecover.protocol.evaluation (one formula).
"""

from __future__ import annotations

import math

from build123d import Part

from cadrecover.challenges.measure import measure
from cadrecover.protocol import FailedCheck, FeatureMeasurement, SetScore

MAX_SIZE_MM = 10_000.0


def validity(part: Part | None) -> tuple[bool, list[FailedCheck]]:
    if part is None:
        return False, [FailedCheck(name="build", message="no solid was produced")]
    problems = []
    solids = part.solids()
    if len(solids) != 1:
        problems.append(f"expected exactly 1 solid, got {len(solids)}")
    is_valid = part.is_valid() if callable(part.is_valid) else part.is_valid
    if not is_valid:
        problems.append("solid is not valid (OCC check failed)")
    vol = part.volume
    if not (math.isfinite(vol) and vol > 1e-6):
        problems.append(f"volume {vol} is not positive and finite")
    size = part.bounding_box().size
    if not all(math.isfinite(s) and 0 < s < MAX_SIZE_MM for s in (size.X, size.Y, size.Z)):
        problems.append("bounding box is empty, infinite or implausibly large")
    return not problems, [FailedCheck(name="validity", message=p) for p in problems]


THROUGH_AXIS = (0.0, 0.0, 1.0)  # through-features of the plate/flange/chuck families run along Z


def offset(a: tuple, b: tuple, axis: tuple = THROUGH_AXIS) -> float:
    """Distance between two feature centres measured across the through-axis.

    A through-hole's position is where it pierces the part, not how high its
    measured edge sits: a misread thickness moves the top face (and so the
    measured centre) along Z, but must not count as a misplaced hole; it is
    charged to geometry and dimensions instead. (Phase 7: features with their
    own axes, like chamber ports, will pass their axis here.)
    """
    d = [a[i] - b[i] for i in range(3)]
    along = sum(d[i] * axis[i] for i in range(3))
    return math.sqrt(max(0.0, sum(x * x for x in d) - along * along))


CRITICAL_KINDS = ("hole", "slot", "bore", "port")


def _nearest(e: FeatureMeasurement, measured: list[FeatureMeasurement]) -> FeatureMeasurement | None:
    pool = [m for m in measured if m.kind == e.kind and m.center is not None]
    return min(pool, key=lambda m: offset(m.center, e.center), default=None)


def critical(expected: list[FeatureMeasurement], measured: list[FeatureMeasurement],
             size_tol: float, pos_tol: float) -> tuple[bool, list[FailedCheck]]:
    """Every critical feature (holes, slots) present and placed within tolerance, and no extra ones:
    a hole the drawing doesn't show is a wrong part (it would also let a superset of guesses pass)."""
    failed = []
    crit = [f for f in expected if f.kind in CRITICAL_KINDS]
    matched = {id(_nearest(e, measured)) for e in crit}
    for m in measured:
        if m.kind in CRITICAL_KINDS and m.center is not None and id(m) not in matched:
            failed.append(FailedCheck(name=f"extra_{m.kind}", message=f"{m.kind} not on the drawing", location=m.center))
    for e in crit:
        m = _nearest(e, measured)
        if m is None:
            failed.append(FailedCheck(name=f"{e.name}.missing", message=f"no {e.kind} found", location=e.center))
            continue
        off = offset(m.center, e.center)
        if off > pos_tol:
            failed.append(FailedCheck(name=f"{e.name}.position",
                                      message=f"{e.kind} centre off by {off:.3f} mm (tolerance {pos_tol})",
                                      location=e.center))
        elif abs(m.diameter - e.diameter) > size_tol:
            failed.append(FailedCheck(name=f"{e.name}.size",
                                      message=f"diameter/width {m.diameter:.3f} vs {e.diameter:.3f} mm",
                                      location=e.center))
        elif e.length is not None and (m.length is None or abs(m.length - e.length) > size_tol):
            failed.append(FailedCheck(name=f"{e.name}.length",
                                      message=f"length {m.length} vs {e.length:.3f} mm", location=e.center))
    return not failed, failed


def dimensions(expected: list[FeatureMeasurement], measured: list[FeatureMeasurement],
               size_tol: float) -> tuple[float, list[FailedCheck]]:
    """Fraction of dimensions within tolerance: envelope lengths, feature diameters and lengths."""
    checks: list[tuple[str, float | None, float, tuple | None]] = []
    by_name = {m.name: m for m in measured if m.kind == "length"}
    for e in expected:
        if e.kind == "length":
            m = by_name.get(e.name)
            checks.append((e.name, m.length if m else None, e.length, None))
        else:
            m = _nearest(e, measured)
            checks.append((f"{e.name}.diameter", m.diameter if m else None, e.diameter, e.center))
            if e.length is not None:
                checks.append((f"{e.name}.length", m.length if m else None, e.length, e.center))
    failed = [FailedCheck(name=name, message=f"measured {got} vs {want:.3f} mm", location=loc)
              for name, got, want, loc in checks if got is None or abs(got - want) > size_tol]
    return (len(checks) - len(failed)) / len(checks), failed


def score_set(index: int, values: dict[str, float], reference: Part, candidate: Part | None,
              expected: list[FeatureMeasurement], *, iou_fn, size_tol: float, pos_tol: float) -> SetScore:
    valid, v_failed = validity(candidate)
    if not valid:
        return SetScore(index=index, values=values, valid=False, critical_ok=False, geometry=0.0, dimensions=0.0,
                        failed_checks=v_failed)
    measured = measure(candidate)
    c_ok, c_failed = critical(expected, measured, size_tol, pos_tol)
    d, d_failed = dimensions(expected, measured, size_tol)
    g = max(0.0, min(1.0, iou_fn(reference, candidate)))
    return SetScore(index=index, values=values, valid=True, critical_ok=c_ok, geometry=g, dimensions=d,
                    failed_checks=c_failed + d_failed)
