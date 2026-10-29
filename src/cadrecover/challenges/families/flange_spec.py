"""Vacuum flange family: parameters, sampling, edit rules, critical features.

Pure Python (no build123d), so the services, CAD and drawing environments all
share one definition. Geometry lives in families/flange.py (CAD env).

Part: a round flange disc with a centre bore and BOLT_COUNT through-holes evenly
spaced on a bolt circle, optionally with a raised hub (a centred cylinder on the
top face; the bore runs through disc and hub).
Frame: origin at the centre of the disc's bottom face, Z up the axis, X toward bolt hole 1.

`bolt_count` (4, 6 or 8) is structural: it is part of `values` (the reference is built from it)
but it is never edited and never published as a parameter; miners count the holes on the drawing.
"""

from __future__ import annotations

import math
import random

from cadrecover.protocol import CriticalFeatureSpec, ParameterSpec

FAMILY = "flange"
SIZE_TOL = 0.1  # mm, diameters
POSITION_TOL = 0.1  # mm, centres
MIN_WALL = 3.0  # mm of material between a bolt hole and the bore, hub, outer edge or its neighbour
HUB_WALL = 4.0  # mm of material between the bore and the hub's outer wall
BOLT_COUNTS = (4, 6, 8)
MIN_CIRCLE_CHANGE = 4.0  # mm of bolt_circle_diameter every hidden edit moves it by at least

FRAME = ("Origin at the centre of the flange disc's bottom face. Z runs up the axis of the bore, through the "
         "thickness. Bolt hole 1 lies on the +X axis; the others follow counter-clockwise, evenly spaced. "
         "A hub, if drawn, stands on the disc's top face.")

RANGES = {
    "outer_diameter": (90.0, 200.0),
    "thickness": (8.0, 24.0),
    "bore_diameter": (20.0, 56.0),
    "bolt_circle_diameter": (60.0, 170.0),
    "bolt_hole_diameter": (6.0, 14.0),
    "hub_diameter": (36.0, 90.0),
    "hub_height": (6.0, 30.0),
    "bolt_count": (float(BOLT_COUNTS[0]), float(BOLT_COUNTS[-1])),
}
DESCRIPTIONS = {
    "outer_diameter": "Outer diameter of the flange disc",
    "thickness": "Thickness of the flange disc along Z (a hub, if any, stands on top of it)",
    "bore_diameter": "Diameter of the centre bore, through the disc and the hub",
    "bolt_circle_diameter": "Diameter of the circle through the centres of the bolt holes",
    "bolt_hole_diameter": "Diameter of every bolt hole",
    "hub_diameter": "Outer diameter of the raised hub",
    "hub_height": "Height of the hub above the disc's top face",
}
EDIT_RULES = [
    "The bolt holes (their number is fixed, as drawn) stay evenly spaced on the bolt circle, hole 1 on +X, "
    "whatever bolt_circle_diameter is.",
    "Changing outer_diameter changes the disc only; it does not move the bolt circle.",
    "The bore is centred and goes through the full height (disc and hub); all bolt holes go through the disc "
    "and share one diameter (bolt_hole_diameter).",
    "If present, the hub is centred, stands on the disc's top face (z = thickness) and rises hub_height.",
]


# draftwright's requirement ledger reports the centred bore (and, on a plain disc, the disc height) as
# "missing" even though their dimensions are drawn. Waived here, and only here; the bore diameter, thickness
# and hub values are still enforced by required_labels(), and the bolt circle's ledger entries are not waived.
LEDGER_WAIVERS = [
    "holes:bore.diameter", "holes:bore.through", "holes:location.location.x", "holes:location.location.y",
    "bosses:boss_height.length",
]


def _q(x: float) -> float:
    """Drawing-friendly values: 0.5 mm steps."""
    return round(x * 2) / 2


def has_hub(params: dict[str, float]) -> bool:
    return "hub_diameter" in params


def bolt_count(params: dict[str, float]) -> int:
    return int(params["bolt_count"])


def total_height(params: dict[str, float]) -> float:
    return params["thickness"] + (params["hub_height"] if has_hub(params) else 0.0)


def bolt_circle_bounds(params: dict[str, float]) -> tuple[float, float]:
    """(lowest, highest) bolt_circle_diameter that leaves MIN_WALL around every bolt hole; lo > hi = no room.

    Only the other parameters of `params` are used; its own bolt_circle_diameter is ignored."""
    d, n = params["bolt_hole_diameter"], bolt_count(params)
    inner_r = params["hub_diameter"] / 2 if has_hub(params) else params["bore_diameter"] / 2
    lo = max(2 * (inner_r + MIN_WALL) + d,  # clear of the bore / hub
             (d + MIN_WALL) / math.sin(math.pi / n),  # clear of the neighbouring hole (chord >= d + wall)
             RANGES["bolt_circle_diameter"][0])
    hi = min(params["outer_diameter"] - d - 2 * MIN_WALL,  # clear of the outer edge
             RANGES["bolt_circle_diameter"][1])
    return lo, hi


def is_valid(params: dict[str, float]) -> bool:
    """Every parameter in range and the geometry has room (used by sampling and by edits)."""
    for name, value in params.items():
        lo, hi = RANGES[name]
        if not lo <= value <= hi:
            return False
    if params["bolt_count"] not in BOLT_COUNTS or ("hub_diameter" in params) != ("hub_height" in params):
        return False
    if params["bore_diameter"] > params["outer_diameter"] - 2 * (MIN_WALL + params["bolt_hole_diameter"]):
        return False
    if has_hub(params):
        if params["hub_diameter"] < params["bore_diameter"] + 2 * HUB_WALL:
            return False
        if params["hub_diameter"] > params["outer_diameter"]:
            return False
    lo, hi = bolt_circle_bounds(params)
    return lo <= params["bolt_circle_diameter"] <= hi


def sample(seed: int) -> dict[str, float]:
    """Deterministic: the same private seed always gives the same part."""
    rng = random.Random(seed)
    while True:
        params = {
            "outer_diameter": _q(rng.uniform(*RANGES["outer_diameter"])),
            "thickness": _q(rng.uniform(*RANGES["thickness"])),
            "bore_diameter": _q(rng.uniform(*RANGES["bore_diameter"])),
            "bolt_hole_diameter": _q(rng.uniform(*RANGES["bolt_hole_diameter"])),
            "bolt_count": float(rng.choice(BOLT_COUNTS)),
        }
        if rng.random() < 0.5:
            params["hub_diameter"] = _q(rng.uniform(params["bore_diameter"] + 2 * HUB_WALL + 2, RANGES["hub_diameter"][1]))
            params["hub_height"] = _q(rng.uniform(*RANGES["hub_height"]))
        lo, hi = bolt_circle_bounds(params)
        if lo > hi:
            continue
        params["bolt_circle_diameter"] = _q(rng.uniform(math.ceil(lo * 2) / 2, math.floor(hi * 2) / 2))
        if is_valid(params):
            return params


def edit_candidate(base: dict[str, float], rng: random.Random) -> dict[str, float] | None:
    """A proposed hidden edit: the outer diameter changes by 15-40% and the bolt circle moves
    independently of it (so neither "holes scale with the disc" nor "ignore the edit" survives);
    sometimes the bore, bolt hole size, thickness or hub change too. The bolt count never does.
    The CAD worker keeps it only if it passes the discriminative rules."""
    new = dict(base)
    new["outer_diameter"] = _q(base["outer_diameter"] * (1 + rng.uniform(0.15, 0.40) * rng.choice((-1, 1))))
    if rng.random() < 0.4:
        new["bore_diameter"] = _q(base["bore_diameter"] + rng.choice((-1, 1)) * rng.uniform(2, 8))
    if rng.random() < 0.3:
        new["bolt_hole_diameter"] = _q(base["bolt_hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(1, 3))
    if rng.random() < 0.4:
        new["thickness"] = _q(base["thickness"] * (1 + rng.uniform(0.1, 0.4) * rng.choice((-1, 1))))
    if has_hub(base):
        if rng.random() < 0.5:
            new["hub_diameter"] = _q(base["hub_diameter"] + rng.choice((-1, 1)) * rng.uniform(4, 16))
        if rng.random() < 0.5:
            new["hub_height"] = _q(base["hub_height"] * (1 + rng.uniform(0.15, 0.5) * rng.choice((-1, 1))))
    if any(not RANGES[k][0] <= new[k] <= RANGES[k][1] for k in new):
        return None
    lo, hi = bolt_circle_bounds(new)
    if math.ceil(lo * 2) / 2 > math.floor(hi * 2) / 2:
        return None
    new["bolt_circle_diameter"] = _q(rng.uniform(math.ceil(lo * 2) / 2, math.floor(hi * 2) / 2))
    if abs(new["bolt_circle_diameter"] - base["bolt_circle_diameter"]) < MIN_CIRCLE_CHANGE:
        return None  # the bolt holes must visibly move (>= 2 mm), well past 5x the position tolerance
    return new if new != base and is_valid(new) else None


def overrides(base: dict[str, float], edited: dict[str, float]) -> dict[str, float]:
    """What build_part receives for an edit: only the parameters that changed."""
    return {k: v for k, v in edited.items() if base.get(k) != v}


def max_feature_shift(a: dict[str, float], b: dict[str, float]) -> float:
    """Largest move of any critical feature's centre between two parameter sets (the bore stays centred)."""
    ca, cb = bolt_centers(a), bolt_centers(b)
    return max(math.dist(ca[n], cb[n]) for n in ca)


def bolt_centers(params: dict[str, float]) -> dict[str, tuple[float, float]]:
    n, r = bolt_count(params), params["bolt_circle_diameter"] / 2
    return {f"bolt_{k + 1}": (r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n)) for k in range(n)}


def parameter_specs(params: dict[str, float]) -> list[ParameterSpec]:
    """Published parameters: everything but the structural bolt count (read off the drawing)."""
    return [ParameterSpec(name=n, description=DESCRIPTIONS[n], min=RANGES[n][0], max=RANGES[n][1])
            for n in params if n != "bolt_count"]


def critical_feature_specs(params: dict[str, float]) -> list[CriticalFeatureSpec]:
    specs = [CriticalFeatureSpec(name="bore", kind="bore", description="centred through-bore",
                                 size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL)]
    specs += [CriticalFeatureSpec(name=name, kind="hole",
                                  description=f"bolt hole on the bolt circle ({bolt_count(params)} evenly spaced, "
                                              "hole 1 on +X, counter-clockwise)",
                                  size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL)
              for name in bolt_centers(params)]
    return specs


def required_labels(params: dict[str, float]) -> list[str]:
    """Text that must appear in the drawing's dimension labels, or the drawing is rejected."""
    labels = [f"⌀{params['outer_diameter']:g}", f"{params['thickness']:g}", f"⌀{params['bore_diameter']:g}",
              f"⌀{params['bolt_circle_diameter']:g}", f"⌀{params['bolt_hole_diameter']:g}"]
    if has_hub(params):
        labels += [f"⌀{params['hub_diameter']:g}", f"{params['hub_height']:g}"]
    return labels
