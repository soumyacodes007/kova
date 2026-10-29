"""Measure features off a solid's B-rep (CAD worker env).

Shared by the reference self-test (Phase 2) and the evaluator (Phase 3), so a
reference and a miner's candidate are measured the same way.

Holes and slot ends are read from circular edges on the top face: a full
circle is a hole; two half-circle arcs of equal radius on one line are a slot.
"""

from __future__ import annotations

import math
from collections import defaultdict

from build123d import GeomType, Part

from cadrecover.protocol import FeatureMeasurement

_EPS = 1e-4


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


def circular_features(part: Part) -> list[FeatureMeasurement]:
    """Holes (full circles) and slots (paired half circles) on the top face."""
    z = top_z(part)
    arcs: dict[tuple[float, float, float], float] = defaultdict(float)  # (cx, cy, r) -> swept angle
    for edge in part.edges():
        if edge.geom_type != GeomType.CIRCLE:
            continue
        c = edge.arc_center
        if abs(c.Z - z) > _EPS:
            continue
        r = edge.radius
        key = (round(c.X, 4), round(c.Y, 4), round(r, 4))
        arcs[key] += edge.length / r

    out: list[FeatureMeasurement] = []
    halves: list[tuple[float, float, float]] = []
    for (x, y, r), angle in arcs.items():
        if abs(angle - 2 * math.pi) < 1e-3:
            out.append(FeatureMeasurement(name=f"hole@{x:.3f},{y:.3f}", kind="hole", center=(x, y, z),
                                          axis=(0.0, 0.0, 1.0), diameter=2 * r))
        elif abs(angle - math.pi) < 1e-3:
            halves.append((x, y, r))

    used: set[int] = set()
    for i, (x1, y1, r1) in enumerate(halves):
        for j in range(i + 1, len(halves)):
            x2, y2, r2 = halves[j]
            if i in used or j in used or abs(r1 - r2) > _EPS:
                continue
            used |= {i, j}
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            out.append(FeatureMeasurement(
                name=f"slot@{cx:.3f},{cy:.3f}", kind="slot", center=(cx, cy, z),
                axis=(x2 - x1, y2 - y1, 0.0), diameter=2 * r1, length=math.dist((x1, y1), (x2, y2)) + 2 * r1,
            ))
    return out


def measure(part: Part) -> list[FeatureMeasurement]:
    return envelope(part) + circular_features(part)
