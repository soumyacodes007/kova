"""Wafer chuck family: parameters, sampling, edit rules, critical features.

Pure Python (no build123d), so the services, CAD and drawing environments all
share one definition. Geometry lives in families/wafer_chuck.py (CAD env).

Part: a round chuck plate (diameter, thickness) pierced by small through-holes laid out on concentric
circles, listed here from the centre outward:

  1. a lift-pin circle: PIN_COUNT (3) larger holes at 120 degrees
  2. vacuum ring 1: ring1_count small vacuum holes
  3. vacuum ring 2 (optional): ring2_count small vacuum holes
  4. a mounting circle (optional): MOUNT_COUNT (4) bolt holes

Every circle has its own diameter parameter: nothing is derived from the plate diameter.
Frame: origin at the centre of the plate's bottom face, Z up the axis; hole 1 of every circle lies
on +X and the others follow counter-clockwise, evenly spaced.

`ring1_count` and `ring2_count` are structural: part of `values` (the reference is built from them) but
never edited and never published as parameters; miners count the holes on the drawing. The pin and
mounting counts are fixed (3 and 4) and stated in the frame.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple

from cadrecover.protocol import CriticalFeatureSpec, ParameterSpec

FAMILY = "wafer_chuck"
SIZE_TOL = 0.1  # mm, diameters
POSITION_TOL = 0.1  # mm, centres
MIN_WALL = 3.0  # mm of material between a hole and its neighbour (other circles too) or the plate's edge
PIN_COUNT = 3
MOUNT_COUNT = 4
RING1_COUNTS = (6, 8, 12)
RING2_COUNTS = (12, 16)
MAX_HOLES = 30  # keeps measuring, drawing and the sandbox fast
MIN_CIRCLE_CHANGE = 4.0  # mm of ring1_diameter every hidden edit moves it by at least, and keeps off proportional scaling

FRAME = ("Origin at the centre of the chuck plate's bottom face. Z runs up the axis, through the thickness. "
         f"The holes sit on concentric circles about the origin: {PIN_COUNT} lift-pin holes at 120 degrees, "
         "one or two rings of small vacuum holes (count them on the drawing), and, if drawn, "
         f"{MOUNT_COUNT} mounting holes. Hole 1 of every circle lies on the +X axis; the others follow "
         "counter-clockwise, evenly spaced. All holes go through the full thickness.")

RANGES = {
    "plate_diameter": (110.0, 260.0),
    "thickness": (6.0, 20.0),
    "vacuum_hole_diameter": (2.0, 5.0),
    "pin_hole_diameter": (4.0, 8.0),
    "pin_circle_diameter": (24.0, 90.0),
    "ring1_diameter": (50.0, 150.0),
    "ring2_diameter": (90.0, 210.0),
    "mount_hole_diameter": (5.0, 9.0),
    "mount_circle_diameter": (100.0, 245.0),
    "ring1_count": (float(RING1_COUNTS[0]), float(RING1_COUNTS[-1])),
    "ring2_count": (float(RING2_COUNTS[0]), float(RING2_COUNTS[-1])),
}
DESCRIPTIONS = {
    "plate_diameter": "Outer diameter of the chuck plate",
    "thickness": "Thickness of the plate along Z",
    "vacuum_hole_diameter": "Diameter of every vacuum hole (all vacuum rings)",
    "pin_hole_diameter": "Diameter of each lift-pin hole",
    "pin_circle_diameter": "Diameter of the circle through the centres of the lift-pin holes",
    "ring1_diameter": "Diameter of the circle through the centres of the first (inner) ring of vacuum holes",
    "ring2_diameter": "Diameter of the circle through the centres of the second (outer) ring of vacuum holes",
    "mount_hole_diameter": "Diameter of each mounting hole",
    "mount_circle_diameter": "Diameter of the circle through the centres of the mounting holes",
}
EDIT_RULES = [
    "Each hole circle keeps its hole count and its even spacing, hole 1 on +X, whatever its diameter is.",
    "Changing plate_diameter changes the plate only; it does not move any hole circle. Every circle "
    "diameter is an independent parameter and may change in an edit, whether or not the plate diameter does.",
    "All vacuum holes (every ring) share one diameter (vacuum_hole_diameter).",
    "Every hole goes through the full thickness of the plate; the plate is centred on the origin.",
]

# draftwright's requirement ledger reports the plain disc's height as "missing" even though the thickness is
# dimensioned (same false negative as the flange disc). Waived here, and only here; the thickness is still
# enforced by required_labels(), and every hole pattern's ledger entries (count, size, bolt circle) are
# never waived.
LEDGER_WAIVERS = ["bosses:boss_height.length"]


class Circle(NamedTuple):
    prefix: str  # critical feature name prefix
    circle: str  # parameter: diameter of the circle through the hole centres
    hole: str  # parameter: diameter of each hole
    count: int


def _q(x: float) -> float:
    """Drawing-friendly values: 0.5 mm steps."""
    return round(x * 2) / 2


def _ceil_q(x: float) -> float:
    return math.ceil(x * 2) / 2


def _floor_q(x: float) -> float:
    return math.floor(x * 2) / 2


def has_ring2(params: dict[str, float]) -> bool:
    return "ring2_count" in params


def has_mount(params: dict[str, float]) -> bool:
    return "mount_hole_diameter" in params


def circles(params: dict[str, float]) -> list[Circle]:
    """The hole circles, centre outward. Only the structure of `params` (presence, counts) is used."""
    out = [Circle("pin", "pin_circle_diameter", "pin_hole_diameter", PIN_COUNT),
           Circle("vac1", "ring1_diameter", "vacuum_hole_diameter", int(params["ring1_count"]))]
    if has_ring2(params):
        out.append(Circle("vac2", "ring2_diameter", "vacuum_hole_diameter", int(params["ring2_count"])))
    if has_mount(params):
        out.append(Circle("mount", "mount_circle_diameter", "mount_hole_diameter", MOUNT_COUNT))
    return out


def hole_count(params: dict[str, float]) -> int:
    return sum(c.count for c in circles(params))


def _chord_min(params: dict[str, float], c: Circle) -> float:
    """Smallest circle diameter that leaves MIN_WALL between neighbouring holes of the same circle."""
    return (params[c.hole] + MIN_WALL) / math.sin(math.pi / c.count)


def _gap(params: dict[str, float], inner: Circle, outer: Circle) -> float:
    """Smallest difference of circle diameters that leaves MIN_WALL between holes of adjacent circles."""
    return params[inner.hole] + params[outer.hole] + 2 * MIN_WALL


def circle_bounds(params: dict[str, float]) -> dict[str, tuple[float, float]]:
    """(lowest, highest) diameter each circle can take for the other parameters (hole sizes, counts, plate
    diameter) so that a full inner-to-outer chain still fits; lo > hi = no room.

    The circle diameters in `params` are ignored. Pick the circles inner to outer, each at least
    `_gap` above the previous one and within its bounds, and the layout is valid."""
    cs = circles(params)
    lo, hi = [], [0.0] * len(cs)
    for i, c in enumerate(cs):
        v = max(RANGES[c.circle][0], _chord_min(params, c))
        if i:
            v = max(v, lo[i - 1] + _gap(params, cs[i - 1], c))
        lo.append(v)
    for i in reversed(range(len(cs))):
        c = cs[i]
        v = RANGES[c.circle][1]
        if i == len(cs) - 1:
            v = min(v, params["plate_diameter"] - params[c.hole] - 2 * MIN_WALL)  # clear of the rim
        else:
            v = min(v, hi[i + 1] - _gap(params, c, cs[i + 1]))
        hi[i] = v
    return {c.circle: (lo[i], hi[i]) for i, c in enumerate(cs)}


def is_valid(params: dict[str, float]) -> bool:
    """Every parameter in range and every hole has MIN_WALL around it (used by sampling and by edits)."""
    for name, value in params.items():
        if name not in RANGES or not RANGES[name][0] <= value <= RANGES[name][1]:
            return False
    required = {"plate_diameter", "thickness", "vacuum_hole_diameter", "pin_hole_diameter", "pin_circle_diameter",
                "ring1_diameter", "ring1_count"}
    if not required <= set(params) or params["ring1_count"] not in RING1_COUNTS:
        return False
    if has_ring2(params) != ("ring2_diameter" in params) or (has_ring2(params) and params["ring2_count"] not in RING2_COUNTS):
        return False
    if has_mount(params) != ("mount_circle_diameter" in params):
        return False
    if hole_count(params) > MAX_HOLES:
        return False
    cs = circles(params)
    for i, c in enumerate(cs):
        if params[c.circle] < _chord_min(params, c) - 1e-9:
            return False
        if i and params[c.circle] - params[cs[i - 1].circle] < _gap(params, cs[i - 1], c) - 1e-9:
            return False
    last = cs[-1]
    return params[last.circle] <= params["plate_diameter"] - params[last.hole] - 2 * MIN_WALL + 1e-9


def _pick_circles(params: dict[str, float], rng: random.Random) -> bool:
    """Choose every circle diameter (0.5 mm steps), inner to outer, uniformly in what the chain allows.
    Writes them into `params`; False = this combination of sizes has no room."""
    bounds = circle_bounds(params)
    cs = circles(params)
    prev = None
    for i, c in enumerate(cs):
        lo, hi = bounds[c.circle]
        if prev is not None:
            lo = max(lo, params[prev.circle] + _gap(params, prev, c))
        lo, hi = _ceil_q(lo), _floor_q(hi)
        if lo > hi:
            return False
        params[c.circle] = _q(rng.uniform(lo, hi))
        prev = c
    return True


def sample(seed: int) -> dict[str, float]:
    """Deterministic: the same private seed always gives the same part."""
    rng = random.Random(seed)
    while True:
        params = {
            "plate_diameter": _q(rng.uniform(*RANGES["plate_diameter"])),
            "thickness": _q(rng.uniform(*RANGES["thickness"])),
            "vacuum_hole_diameter": _q(rng.uniform(*RANGES["vacuum_hole_diameter"])),
            "pin_hole_diameter": _q(rng.uniform(*RANGES["pin_hole_diameter"])),
            "ring1_count": float(rng.choice(RING1_COUNTS)),
        }
        if rng.random() < 0.5:
            params["ring2_count"] = float(rng.choice(RING2_COUNTS))
        if rng.random() < 0.5:
            params["mount_hole_diameter"] = _q(rng.uniform(*RANGES["mount_hole_diameter"]))
        if hole_count(params) > MAX_HOLES:
            continue
        if not _pick_circles(params, rng):
            continue
        if is_valid(params):
            return params


def _proportional(base: dict[str, float], new_plate: float, name: str) -> float:
    return base[name] * new_plate / base["plate_diameter"]


def edit_candidate(base: dict[str, float], rng: random.Random) -> dict[str, float] | None:
    """A proposed hidden edit: the plate diameter changes by 15-40% and every hole circle is re-chosen
    independently of it, so neither "the pattern scales with the plate" nor "ignore the edit" survives:
    ring1_diameter ends up at least MIN_CIRCLE_CHANGE away from both its base value and its proportional
    value. Sometimes the thickness or a hole size changes too. The counts never do.
    The CAD worker keeps it only if it passes the discriminative rules."""
    new = dict(base)
    new["plate_diameter"] = _q(base["plate_diameter"] * (1 + rng.uniform(0.15, 0.40) * rng.choice((-1, 1))))
    if rng.random() < 0.4:
        new["thickness"] = _q(base["thickness"] * (1 + rng.uniform(0.1, 0.4) * rng.choice((-1, 1))))
    if rng.random() < 0.4:
        new["vacuum_hole_diameter"] = _q(base["vacuum_hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(0.5, 1.5))
    if rng.random() < 0.3:
        new["pin_hole_diameter"] = _q(base["pin_hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(1, 2))
    if has_mount(base) and rng.random() < 0.3:
        new["mount_hole_diameter"] = _q(base["mount_hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(1, 2))
    if any(k in RANGES and not RANGES[k][0] <= v <= RANGES[k][1] for k, v in new.items()):
        return None
    if not _pick_circles(new, rng):
        return None
    ring1 = new["ring1_diameter"]
    if (abs(ring1 - base["ring1_diameter"]) < MIN_CIRCLE_CHANGE
            or abs(ring1 - _proportional(base, new["plate_diameter"], "ring1_diameter")) < MIN_CIRCLE_CHANGE):
        return None  # ring1 must visibly move (>= 2 mm radius), well past 5x the position tolerance
    return new if new != base and is_valid(new) else None


def overrides(base: dict[str, float], edited: dict[str, float]) -> dict[str, float]:
    """What build_part receives for an edit: only the parameters that changed."""
    return {k: v for k, v in edited.items() if base.get(k) != v}


def hole_centers(params: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Centre (x, y) of every hole, named <prefix>_<k>: pin_1.., vac1_1.., vac2_1.., mount_1.."""
    out = {}
    for c in circles(params):
        r = params[c.circle] / 2
        for k in range(c.count):
            a = 2 * math.pi * k / c.count
            out[f"{c.prefix}_{k + 1}"] = (r * math.cos(a), r * math.sin(a))
    return out


def hole_diameters(params: dict[str, float]) -> dict[str, float]:
    return {f"{c.prefix}_{k + 1}": params[c.hole] for c in circles(params) for k in range(c.count)}


def max_feature_shift(a: dict[str, float], b: dict[str, float]) -> float:
    """Largest move of any critical feature's centre between two parameter sets."""
    ca, cb = hole_centers(a), hole_centers(b)
    return max(math.dist(ca[n], cb[n]) for n in ca)


def parameter_specs(params: dict[str, float]) -> list[ParameterSpec]:
    """Published parameters: everything but the structural ring counts (read off the drawing)."""
    return [ParameterSpec(name=n, description=DESCRIPTIONS[n], min=RANGES[n][0], max=RANGES[n][1])
            for n in params if not n.endswith("_count")]


_KIND_TEXT = {
    "pin": f"lift-pin hole ({PIN_COUNT} at 120 degrees on the lift-pin circle, hole 1 on +X)",
    "vac1": "vacuum hole on the inner ring (evenly spaced, hole 1 on +X, counter-clockwise)",
    "vac2": "vacuum hole on the outer ring (evenly spaced, hole 1 on +X, counter-clockwise)",
    "mount": f"mounting hole ({MOUNT_COUNT} evenly spaced on the mounting circle, hole 1 on +X)",
}


def critical_feature_specs(params: dict[str, float]) -> list[CriticalFeatureSpec]:
    prefix_of = {name: name.rsplit("_", 1)[0] for name in hole_centers(params)}
    return [CriticalFeatureSpec(name=name, kind="hole", description=_KIND_TEXT[prefix_of[name]],
                                size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL)
            for name in hole_centers(params)]


def required_labels(params: dict[str, float]) -> list[str]:
    """Text that must appear in the drawing's dimension labels, or the drawing is rejected."""
    labels = [f"⌀{params['plate_diameter']:g}", f"{params['thickness']:g}"]
    for c in circles(params):
        labels += [f"⌀{params[c.circle]:g}", f"⌀{params[c.hole]:g}"]
    return list(dict.fromkeys(labels))
