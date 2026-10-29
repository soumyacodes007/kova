"""Measure features off a solid's B-rep (CAD worker env).

Shared by the reference self-test (Phase 2) and the evaluator (Phase 3), so a
reference and a miner's candidate are measured the same way.

Holes and slot ends are read from circular edges: a full concave circle is a
hole; two half-circle arcs of equal radius on one line are a slot.
"""

from __future__ import annotations

import math
from collections import defaultdict

from build123d import GeomType, Part, Vector

from cadrecover.protocol import FeatureMeasurement

_EPS = 1e-4
_PROBE = 1e-2  # mm, how far off an edge to look for material


def top_z(part: Part) -> float:
    return part.bounding_box().max.Z


def envelope(part: Part) -> list[FeatureMeasurement]:
    bb = part.bounding_box()
    size = bb.size
    return [
        FeatureMeasurement(name="width", kind="length", length=size.X),
        FeatureMeasurement(name="length", kind="length", length=size.Y),
        FeatureMeasurement(name="thickness", kind="length", length=size.Z),
    ]


def _is_hole(part: Part, x: float, y: float, r: float, z: float) -> bool:
    """A full circle edge bounds a hole (not a boss or the outer rim) when just inside it, a hair above
    and below its plane, there is no material in any direction."""
    for ang in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        for dz in (-_PROBE, _PROBE):
            p = Vector(x + (r - _PROBE) * math.cos(ang), y + (r - _PROBE) * math.sin(ang), z + dz)
            if part.is_inside(p):
                return False
    return True


def circular_features(part: Part) -> list[FeatureMeasurement]:
    """Holes (full concave circles) and slots (paired half circles), read from circular edges at any height.

    A through feature shows its circle on both faces; it is reported once, at its highest edge.
    Convex circles (a disc's rim, a hub) are not holes."""
    arcs: dict[tuple[float, float, float, float], float] = defaultdict(float)  # (cx, cy, r, z) -> swept angle
    exact: dict[tuple[float, float, float, float], tuple[float, float, float, float]] = {}  # key -> unrounded values
    for edge in part.edges():
        if edge.geom_type != GeomType.CIRCLE:
            continue
        c = edge.arc_center
        r = edge.radius
        key = (round(c.X, 4), round(c.Y, 4), round(r, 4), round(c.Z, 4))  # rounded only to group the edges
        exact.setdefault(key, (c.X, c.Y, r, c.Z))
        arcs[key] += edge.length / r

    found: dict[tuple, FeatureMeasurement] = {}  # one entry per feature, keeping the highest z

    def keep(key: tuple, m: FeatureMeasurement) -> None:
        if key not in found or m.center[2] > found[key].center[2]:
            found[key] = m

    halves: dict[float, list[tuple[float, float, float]]] = defaultdict(list)
    for key, angle in arcs.items():
        x, y, r, z = exact[key]
        if abs(angle - 2 * math.pi) < 1e-3:
            if _is_hole(part, x, y, r, z):
                keep(("hole",) + key[:3], FeatureMeasurement(name=f"hole@{x:.3f},{y:.3f}", kind="hole",
                                                           center=(x, y, z), axis=(0.0, 0.0, 1.0), diameter=2 * r))
        elif abs(angle - math.pi) < 1e-3:
            halves[key[3]].append((x, y, r))

    for z, hs in halves.items():
        used: set[int] = set()
        for i, (x1, y1, r1) in enumerate(hs):
            for j in range(i + 1, len(hs)):
                x2, y2, r2 = hs[j]
                if i in used or j in used or abs(r1 - r2) > _EPS:
                    continue
                used |= {i, j}
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                length = math.dist((x1, y1), (x2, y2)) + 2 * r1
                keep(("slot", round(cx, 3), round(cy, 3), round(r1, 4), round(length, 3)), FeatureMeasurement(
                    name=f"slot@{cx:.3f},{cy:.3f}", kind="slot", center=(cx, cy, z),
                    axis=(x2 - x1, y2 - y1, 0.0), diameter=2 * r1, length=length))
    return list(found.values())


def measure(part: Part) -> list[FeatureMeasurement]:
    return envelope(part) + circular_features(part)
