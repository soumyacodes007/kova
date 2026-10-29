"""Mounting plate family: parameters, sampling, edit rules, critical features.

Pure Python (no build123d), so the services, CAD and drawing environments all
share one definition. Geometry lives in families/plate.py (CAD env).

Part: a rectangular plate, 4 through-holes each EDGE_OFFSET from the two nearest
edges, and optionally a through-slot centred on the plate running along X.
Frame: origin at the centre of the bottom face, X along width, Y along length, Z up.
"""

from __future__ import annotations

import random

from cadrecover.protocol import CriticalFeatureSpec, ParameterSpec

FAMILY = "plate"
EDGE_OFFSET = 10.0  # holes keep this offset from the nearest edges (the edit rule)
SIZE_TOL = 0.1  # mm, diameters and widths
POSITION_TOL = 0.1  # mm, centres
MIN_WALL = 3.0  # mm of material between a hole/slot and anything else

FRAME = ("Origin at the centre of the plate's bottom face. X runs along the width, "
         "Y along the length, Z up through the thickness.")

RANGES = {
    "width": (80.0, 200.0),
    "length": (50.0, 150.0),
    "thickness": (4.0, 16.0),
    "hole_diameter": (4.0, 10.0),
    "slot_length": (20.0, 60.0),
    "slot_width": (6.0, 12.0),
}
DESCRIPTIONS = {
    "width": "Overall plate size along X",
    "length": "Overall plate size along Y",
    "thickness": "Plate thickness along Z",
    "hole_diameter": "Diameter of the 4 through-holes",
    "slot_length": "Overall length of the centred through-slot (along X, end to end)",
    "slot_width": "Width of the centred through-slot",
}
EDIT_RULES = [
    f"Each of the 4 holes stays {EDGE_OFFSET:g} mm from the two nearest outer edges when width or length changes.",
    "All 4 holes go through the full thickness and share one diameter (hole_diameter).",
    "If present, the slot stays centred on the plate, runs along X and goes through the full thickness.",
]


def _q(x: float) -> float:
    """Drawing-friendly values: 0.5 mm steps."""
    return round(x * 2) / 2


def has_slot(params: dict[str, float]) -> bool:
    return "slot_length" in params


def slot_bounds(width: float, length: float, hole_diameter: float) -> tuple[float, float] | None:
    """Largest slot (length, width) that keeps MIN_WALL clear of the holes and edges; None if no room."""
    hole_inner_x = width / 2 - EDGE_OFFSET - hole_diameter / 2
    max_len = min(RANGES["slot_length"][1], 2 * (hole_inner_x - MIN_WALL))
    hole_inner_y = length / 2 - EDGE_OFFSET - hole_diameter / 2
    max_w = min(RANGES["slot_width"][1], 2 * (hole_inner_y - MIN_WALL))
    if max_len < RANGES["slot_length"][0] or max_w < RANGES["slot_width"][0]:
        return None
    return max_len, max_w


def is_valid(params: dict[str, float]) -> bool:
    """Every parameter in range and the geometry has room (used by sampling and, later, by edits)."""
    for name, value in params.items():
        lo, hi = RANGES[name]
        if not lo <= value <= hi:
            return False
    if params["length"] > params["width"]:
        return False
    if params["hole_diameter"] / 2 + MIN_WALL > EDGE_OFFSET:
        return False
    if has_slot(params):
        b = slot_bounds(params["width"], params["length"], params["hole_diameter"])
        if b is None or params["slot_length"] > b[0] or params["slot_width"] > b[1]:
            return False
        if params["slot_width"] >= params["slot_length"]:
            return False
    return True


def sample(seed: int) -> dict[str, float]:
    """Deterministic: the same private seed always gives the same part."""
    rng = random.Random(seed)
    while True:
        width = _q(rng.uniform(*RANGES["width"]))
        length = _q(rng.uniform(RANGES["length"][0], min(RANGES["length"][1], width)))
        params = {
            "width": width,
            "length": length,
            "thickness": _q(rng.uniform(*RANGES["thickness"])),
            "hole_diameter": _q(rng.uniform(*RANGES["hole_diameter"])),
        }
        if rng.random() < 0.5:
            b = slot_bounds(width, length, params["hole_diameter"])
            if b is not None:
                params["slot_length"] = _q(rng.uniform(RANGES["slot_length"][0], b[0]))
                params["slot_width"] = _q(rng.uniform(RANGES["slot_width"][0], min(b[1], params["slot_length"] - 2)))
        if is_valid(params):
            return params


def edit_candidate(base: dict[str, float], rng: random.Random) -> dict[str, float] | None:
    """A proposed hidden edit: width and/or length change by 15-40%, sometimes the hole size or
    thickness too. The CAD worker keeps it only if it passes the discriminative rules."""
    new = dict(base)
    keys = rng.choice([("width",), ("length",), ("width", "length")])
    for k in keys:
        factor = rng.uniform(0.15, 0.40) * rng.choice((-1, 1))
        new[k] = _q(base[k] * (1 + factor))
    if rng.random() < 0.3:
        new["hole_diameter"] = _q(base["hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(1, 2))
    if rng.random() < 0.3:
        new["thickness"] = _q(base["thickness"] + rng.choice((-1, 1)) * rng.uniform(1, 4))
    if has_slot(base) and rng.random() < 0.3:
        new["slot_length"] = _q(base["slot_length"] + rng.choice((-1, 1)) * rng.uniform(2, 6))
    return new if new != base and is_valid(new) else None


def overrides(base: dict[str, float], edited: dict[str, float]) -> dict[str, float]:
    """What build_part receives for an edit: only the parameters that changed."""
    return {k: v for k, v in edited.items() if base.get(k) != v}


def max_feature_shift(a: dict[str, float], b: dict[str, float]) -> float:
    """Largest move of any critical feature between two parameter sets (the slot stays centred)."""
    ca, cb = hole_centers(a), hole_centers(b)
    return max(((ca[n][0] - cb[n][0]) ** 2 + (ca[n][1] - cb[n][1]) ** 2) ** 0.5 for n in ca)


def hole_centers(params: dict[str, float]) -> dict[str, tuple[float, float]]:
    x = params["width"] / 2 - EDGE_OFFSET
    y = params["length"] / 2 - EDGE_OFFSET
    return {"hole_1": (-x, -y), "hole_2": (x, -y), "hole_3": (-x, y), "hole_4": (x, y)}


def parameter_specs(params: dict[str, float]) -> list[ParameterSpec]:
    return [ParameterSpec(name=n, description=DESCRIPTIONS[n], min=RANGES[n][0], max=RANGES[n][1]) for n in params]


def critical_feature_specs(params: dict[str, float]) -> list[CriticalFeatureSpec]:
    specs = [
        CriticalFeatureSpec(name=name, kind="hole", description=f"through-hole {EDGE_OFFSET:g} mm from the nearest edges",
                            size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL)
        for name in hole_centers(params)
    ]
    if has_slot(params):
        specs.append(CriticalFeatureSpec(name="slot", kind="slot", description="centred through-slot along X",
                                         size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL))
    return specs


def required_labels(params: dict[str, float]) -> list[str]:
    """Text that must appear in the drawing's dimension labels, or the drawing is rejected."""
    labels = [f"{params['width']:g}", f"{params['length']:g}", f"{params['thickness']:g}",
              f"{EDGE_OFFSET:g}", f"⌀{params['hole_diameter']:g}"]
    if has_slot(params):
        labels += [f"{params['slot_length']:g}", f"{params['slot_width']:g}"]
    return labels
