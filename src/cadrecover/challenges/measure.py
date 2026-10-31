"""Measure features off a solid's B-rep (CAD worker env).

Shared by the reference self-test (Phase 2) and the evaluator (Phase 3), so a
reference and a miner's candidate are measured the same way.

Holes and slot ends are read from circular edges: a full concave circle is a
hole; two half-circle arcs of equal radius on one line are a slot.

Circles whose axis is not Z (a vacuum chamber's radial ports and their flange bolt holes) are read the same
way, with the axis reported (oriented away from the Z axis, so opposite ports differ). A full concave circle
with a larger circle around it on the same axis (the flange rim) is a port bore (kind "port"); the others are holes.
"""

from __future__ import annotations

import math
from collections import defaultdict

from build123d import Face, GeomType, Part, Vector

from cadrecover.protocol import FeatureMeasurement

_EPS = 1e-4
_PROBE = 1e-2  # mm, how far off an edge to look for material
_Z_AXIS_TOL = 1e-6  # |axis . Z| within this of 1 = a Z-axis circle (the plate/flange/chuck path, unchanged)


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


def _is_hole_edge(amap, edge, c: tuple[float, float, float]) -> bool:
    """A circle edge of any orientation bounds a hole when a cylindrical face meeting it has its outward normal
    pointing at the circle's axis. Read from the face topology: a point probe (_is_hole) is far too slow on a solid
    with many saddle-shaped faces."""
    from OCP.TopoDS import TopoDS

    cast_face = getattr(TopoDS, "Face_s", None) or TopoDS.Face  # OCP 7 / OCP 8 spellings
    faces = amap.FindFromKey(edge.wrapped)
    p = edge.position_at(0.5)
    for shape in faces:
        face = Face(cast_face(shape))
        if face.geom_type != GeomType.CYLINDER:
            continue
        nrm = face.normal_at(p)
        if nrm.X * (c[0] - p.X) + nrm.Y * (c[1] - p.Y) + nrm.Z * (c[2] - p.Z) > 0:
            return True
    return False


def _canonical(n: tuple[float, float, float]) -> tuple[float, float, float]:
    """The sign of an unoriented axis fixed (first non-negligible component positive), for grouping equal circles."""
    for x in n:
        if abs(x) > 1e-6:
            return n if x > 0 else (-n[0], -n[1], -n[2])
    return n


def _skew_circles(part: Part, edges: list[tuple]) -> list[FeatureMeasurement]:
    """Holes and ports from full circles whose axis is not Z. `edges` holds (centre, axis, radius, swept angle, edge)."""
    if not edges:
        return []
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    try:  # OCP 8 (the CAD worker and sandbox) names the map class differently from OCP 7
        from OCP.collections import IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as ancestor_map
    except ImportError:
        from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape as ancestor_map
    amap = ancestor_map()
    TopExp.MapShapesAndAncestors_s(part.wrapped, TopAbs_EDGE, TopAbs_FACE, amap)
    groups: dict[tuple, list] = defaultdict(lambda: [0.0, None])  # key -> [swept angle, (c, n, r, edge)]
    for c, n, r, angle, edge in edges:
        n = _canonical(n)
        key = (tuple(round(x, 4) for x in c), tuple(round(x, 5) for x in n), round(r, 4))
        groups[key][0] += angle
        groups[key][1] = groups[key][1] or (c, n, r, edge)
    full = [v[1] for v in groups.values() if abs(v[0] - 2 * math.pi) < 1e-3]
    found: dict[tuple, tuple[float, FeatureMeasurement]] = {}  # one entry per feature: its outermost circle
    for c, n, r, edge in full:
        if not _is_hole_edge(amap, edge, c):
            continue
        radial = (c[0], c[1], 0.0)
        out = n if sum(radial[i] * n[i] for i in range(3)) >= 0 else (-n[0], -n[1], -n[2])  # outward from the Z axis
        rim = any(r2 > r + _EPS and math.dist(c, c2) < 1e-3 and abs(sum(n[i] * n2[i] for i in range(3))) > 1 - 1e-9
                  for c2, n2, r2, _ in full)
        along = sum(c[i] * out[i] for i in range(3))
        lateral = tuple(round(c[i] - along * out[i], 3) for i in range(3))
        key = (lateral, tuple(round(x, 4) for x in out), round(r, 4))
        kind = "port" if rim else "hole"
        m = FeatureMeasurement(name=f"{kind}@{c[0]:.3f},{c[1]:.3f},{c[2]:.3f}", kind=kind, center=c, axis=out, diameter=2 * r)
        if key not in found or along > found[key][0]:
            found[key] = (along, m)
    return [m for _, m in found.values()]


def circular_features(part: Part) -> list[FeatureMeasurement]:
    """Holes (full concave circles) and slots (paired half circles), read from circular edges at any height.

    A through feature shows its circle on both faces; it is reported once, at its highest edge.
    Convex circles (a disc's rim, a hub) are not holes."""
    arcs: dict[tuple[float, float, float, float], float] = defaultdict(float)  # (cx, cy, r, z) -> swept angle
    exact: dict[tuple[float, float, float, float], tuple[float, float, float, float]] = {}  # key -> unrounded values
    skew: list[tuple] = []  # circles with a non-Z axis: (centre, axis, radius, swept angle, edge)
    for edge in part.edges():
        if edge.geom_type != GeomType.CIRCLE:
            continue
        c = edge.arc_center
        r = edge.radius
        nrm = edge.normal()
        if abs(abs(nrm.Z) - 1.0) > _Z_AXIS_TOL:
            skew.append(((c.X, c.Y, c.Z), (nrm.X, nrm.Y, nrm.Z), r, edge.length / r, edge))
            continue
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
    return list(found.values()) + _skew_circles(part, skew)


def measure(part: Part) -> list[FeatureMeasurement]:
    return envelope(part) + circular_features(part)
