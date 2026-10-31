"""Multi-port vacuum chamber family: parameters, sampling, edit rules, critical features.

Pure Python (no build123d), so the services, CAD and drawing environments all
share one definition. Geometry lives in families/vacuum_chamber.py (CAD env).

Part: a hollow cylindrical body (open at both ends) with 4-6 radial ports on its side wall. Each port is a
tube stub (outer diameter port_diameter + 2 * STUB_WALL) ending in a flange disc; the port bore
(port_diameter) runs through flange and stub into the body, and the flange carries `bolt_count` holes on a
bolt circle. Every port has the same design, so editing a port parameter updates all ports.
Frame: origin at the centre of the body's bottom face, Z up the body axis, port 1 along +X.
All port axes lie in the plane z = body_height / 2 and point radially outward.

`port_count` (4-6) and `bolt_count` (4 or 6, bolts per port) are structural: they are part of `values` (the
reference is built from them) but are never edited and never published as parameters; miners count the ports
and bolt holes on the drawing. Port angles follow from the port count (PORT_ORDER) and are never edited.
"""

from __future__ import annotations

import math
import random

from cadrecover.protocol import CriticalFeatureSpec, ParameterSpec

FAMILY = "vacuum_chamber"
SIZE_TOL = 0.1  # mm, diameters
POSITION_TOL = 0.1  # mm, centres
MIN_WALL = 3.0  # mm of material between a bolt hole and the stub, the flange rim or its neighbour
STUB_WALL = 4.0  # mm: stub tube outer diameter = port_diameter + 2 * STUB_WALL
GAP = 6.0  # mm of clearance between neighbouring ports
END_MARGIN = 20.0  # mm of body wall above and below a stub
FLANGE_MARGIN = 10.0  # mm: flange discs stay this far inside the body's height
BODY_WALL = (6.0, 16.0)  # mm, (body_diameter - body_bore_diameter) / 2
MAX_STUB_LENGTH = 120.0  # mm, from the body's outer surface to the flange face
PORT_COUNTS = (4, 5, 6)
BOLT_COUNTS = (4, 6)
PORT_ORDER = (0.0, 90.0, 180.0, 270.0, 45.0, 135.0)  # port angles (deg) by port count: the first N, sorted
MIN_CIRCLE_CHANGE = 4.0  # mm of bolt-circle diameter every hidden edit moves it by at least
MIN_PORT_CHANGE = 8.0  # mm of port_diameter every hidden edit changes it by at least
_TAN_HALF_45 = math.tan(math.radians(22.5))
_SIN_HALF_45 = math.sin(math.radians(22.5))

FRAME = ("Origin at the centre of the body's bottom face. Z runs up the body axis. Every port axis lies in the "
         "horizontal plane at mid-height of the body (z = body_height / 2) and points radially outward. Port 1 "
         "points along +X; the ports are at 0, 90, 180 and 270 degrees (counter-clockwise from +X) and, if the "
         "chamber has 5 or 6 ports, also at 45 degrees and then 135 degrees. Each flange's bolt hole 1 is straight "
         "up (+Z); the others follow evenly spaced around the port axis.")

RANGES = {
    "body_diameter": (200.0, 320.0),
    "body_bore_diameter": (160.0, 310.0),
    "body_height": (150.0, 240.0),
    "port_diameter": (25.0, 80.0),
    "port_reach": (110.0, 230.0),
    "flange_diameter": (60.0, 150.0),
    "flange_thickness": (8.0, 20.0),
    "port_bolt_circle_diameter": (46.0, 130.0),
    "port_bolt_hole_diameter": (5.0, 12.0),
    "port_count": (float(PORT_COUNTS[0]), float(PORT_COUNTS[-1])),
    "bolt_count": (float(BOLT_COUNTS[0]), float(BOLT_COUNTS[-1])),
}
STRUCTURAL = ("port_count", "bolt_count")
DESCRIPTIONS = {
    "body_diameter": "Outer diameter of the hollow cylindrical body",
    "body_bore_diameter": "Inner diameter of the body (open at both ends); the wall is half the difference",
    "body_height": "Height of the body along Z (the ports sit at half this height)",
    "port_diameter": "Bore diameter of every port; the tube stub around it is this plus 8 mm",
    "port_reach": "Distance from the Z axis to the outer face of every port flange, measured along the port axis",
    "flange_diameter": "Outer diameter of every port's flange disc",
    "flange_thickness": "Thickness of every port's flange disc along the port axis",
    "port_bolt_circle_diameter": "Diameter of the circle through the bolt-hole centres of every port flange",
    "port_bolt_hole_diameter": "Diameter of every port flange bolt hole",
}
EDIT_RULES = [
    "All ports share one design: when port_diameter, port_reach, flange_diameter, flange_thickness, "
    "port_bolt_circle_diameter or port_bolt_hole_diameter change, every port changes with it. The number of ports, "
    "their angles and the number of bolt holes per flange (as drawn) never change.",
    "Each port is a tube stub of outer diameter port_diameter + 8 mm (a 4 mm wall) that starts inside the body wall "
    "and runs radially outward to the flange disc; the bore of diameter port_diameter goes through flange and stub "
    "into the hollow body.",
    "The flange disc is centred on the port axis, its outer face is port_reach from the Z axis, and it has "
    "flange_thickness. Its bolt holes (all of one diameter, port_bolt_hole_diameter) go through the flange parallel "
    "to the port axis, evenly spaced on port_bolt_circle_diameter, hole 1 straight up (+Z).",
    "Port axes stay at z = body_height / 2, so changing body_height moves them. Changing body_diameter or "
    "body_bore_diameter does not move the flanges: port_reach is measured from the Z axis, and only the stub length "
    "changes.",
]


# draftwright's requirement ledger cannot join the chamber's radial bosses, holes and bolt patterns to its
# measurements: it reports them "missing" (boss height, boss grouping) or "unverifiable" (no parameter id) even though
# every dimension and callout is drawn. Waived here, and only here. Each fact they stand for is still enforced by
# required_labels(): port, stub, flange and bolt-hole diameters, bolt circle, bolt count, flange thickness, reach and
# body height must all appear in a rendered dimension label, or the drawing is rejected.
LEDGER_WAIVERS = [
    "bosses:boss_height.length", "bosses:grouping.count", "bosses:None", "holes:None", "hole_patterns:None",
]


def _q(x: float) -> float:
    """Drawing-friendly values: 0.5 mm steps."""
    return round(x * 2) / 2


def port_count(params: dict[str, float]) -> int:
    return int(params["port_count"])


def bolt_count(params: dict[str, float]) -> int:
    return int(params["bolt_count"])


def stub_diameter(params: dict[str, float]) -> float:
    return params["port_diameter"] + 2 * STUB_WALL


def stub_length(params: dict[str, float]) -> float:
    """From the body's outer surface (on the port axis) to the flange's inner face."""
    return params["port_reach"] - params["body_diameter"] / 2 - params["flange_thickness"]


def port_angles(params: dict[str, float]) -> list[float]:
    """Port angles in degrees, counter-clockwise from +X; port 1 is first."""
    return sorted(PORT_ORDER[:port_count(params)])


def flange_bounds(params: dict[str, float]) -> tuple[float, float]:
    """(lowest, highest) flange_diameter that leaves room for the bolt circle and fits the body and neighbours.

    Uses the other parameters only; lo > hi = no room."""
    s, d, n = stub_diameter(params), params["port_bolt_hole_diameter"], bolt_count(params)
    bc_lo = max(s + d + 2 * MIN_WALL, (d + MIN_WALL) / math.sin(math.pi / n), RANGES["port_bolt_circle_diameter"][0])
    hi = min(RANGES["flange_diameter"][1], params["body_height"] - 2 * FLANGE_MARGIN)
    if port_count(params) > 4:  # flange discs 45 degrees apart must clear each other
        hi = min(hi, 2 * (params["port_reach"] * _TAN_HALF_45 - GAP / 2))
    return max(RANGES["flange_diameter"][0], bc_lo + d + 2 * MIN_WALL), hi


def bolt_circle_bounds(params: dict[str, float]) -> tuple[float, float]:
    """(lowest, highest) port_bolt_circle_diameter that keeps MIN_WALL around every bolt hole; lo > hi = no room.

    Only the other parameters of `params` are used; its own bolt circle is ignored."""
    s, d, n = stub_diameter(params), params["port_bolt_hole_diameter"], bolt_count(params)
    lo = max(s + d + 2 * MIN_WALL,  # clear of the stub tube
             (d + MIN_WALL) / math.sin(math.pi / n),  # clear of the neighbouring hole
             RANGES["port_bolt_circle_diameter"][0])
    hi = min(params["flange_diameter"] - d - 2 * MIN_WALL, RANGES["port_bolt_circle_diameter"][1])
    return lo, hi


def is_valid(params: dict[str, float]) -> bool:
    """Every parameter in range and the geometry has room (used by sampling and by edits)."""
    for name, value in params.items():
        lo, hi = RANGES[name]
        if not lo <= value <= hi:
            return False
    if set(params) != set(RANGES):
        return False
    if port_count(params) not in PORT_COUNTS or bolt_count(params) not in BOLT_COUNTS:
        return False
    wall = (params["body_diameter"] - params["body_bore_diameter"]) / 2
    if not BODY_WALL[0] <= wall <= BODY_WALL[1]:
        return False
    s = stub_diameter(params)
    if params["body_height"] < s + 2 * END_MARGIN:
        return False
    ls = stub_length(params)
    if not 2 * params["flange_thickness"] + 10 <= ls <= MAX_STUB_LENGTH:
        return False
    if port_count(params) > 4 and s + GAP > 2 * (params["body_diameter"] / 2) * _SIN_HALF_45:
        return False  # neighbouring stubs 45 degrees apart would merge at the body wall
    lo, hi = flange_bounds(params)
    if not lo <= params["flange_diameter"] <= hi:
        return False
    lo, hi = bolt_circle_bounds(params)
    return lo <= params["port_bolt_circle_diameter"] <= hi


def _ceil_half(x: float) -> float:
    return math.ceil(x * 2) / 2


def _floor_half(x: float) -> float:
    return math.floor(x * 2) / 2


def _fill_flange(params: dict[str, float], rng: random.Random) -> bool:
    """Choose flange_diameter and the bolt circle inside their bounds; False if there is no room."""
    lo, hi = flange_bounds(params)
    if _ceil_half(lo) > _floor_half(hi):
        return False
    params["flange_diameter"] = _q(rng.uniform(_ceil_half(lo), _floor_half(hi)))
    lo, hi = bolt_circle_bounds(params)
    if _ceil_half(lo) > _floor_half(hi):
        return False
    params["port_bolt_circle_diameter"] = _q(rng.uniform(_ceil_half(lo), _floor_half(hi)))
    return True


def sample(seed: int) -> dict[str, float]:
    """Deterministic: the same private seed always gives the same part."""
    rng = random.Random(seed)
    while True:
        d = _q(rng.uniform(*RANGES["body_diameter"]))
        params = {
            "body_diameter": d,
            "body_bore_diameter": d - 2 * _q(rng.uniform(*BODY_WALL)),
            "body_height": _q(rng.uniform(*RANGES["body_height"])),
            "port_diameter": _q(rng.uniform(*RANGES["port_diameter"])),
            "flange_thickness": _q(rng.uniform(*RANGES["flange_thickness"])),
            "port_bolt_hole_diameter": _q(rng.uniform(*RANGES["port_bolt_hole_diameter"])),
            "port_count": float(rng.choice(PORT_COUNTS)),
            "bolt_count": float(rng.choice(BOLT_COUNTS)),
        }
        params["port_reach"] = _q(rng.uniform(d / 2 + 2 * params["flange_thickness"] + 10 + params["flange_thickness"],
                                              min(RANGES["port_reach"][1], d / 2 + MAX_STUB_LENGTH + params["flange_thickness"])))
        if _fill_flange(params, rng) and is_valid(params):
            return params


def edit_candidate(base: dict[str, float], rng: random.Random) -> dict[str, float] | None:
    """A proposed hidden edit: the port diameter changes by 8-28 mm (every port follows), the body diameter by
    12-30 %, and the flange and bolt circle are resampled independently (so neither "ports scale with the
    part" nor "ignore the edit" survives); sometimes the height, reach, bolt hole size or flange thickness
    change too. The port count and bolts per port never do. The CAD worker keeps it only if it passes the
    discriminative rules."""
    new = dict(base)
    new["port_diameter"] = _q(base["port_diameter"] + rng.choice((-1, 1)) * rng.uniform(MIN_PORT_CHANGE, 28))
    wall = (base["body_diameter"] - base["body_bore_diameter"]) / 2
    new["body_diameter"] = _q(base["body_diameter"] * (1 + rng.uniform(0.12, 0.30) * rng.choice((-1, 1))))
    new["body_bore_diameter"] = new["body_diameter"] - 2 * (wall if rng.random() < 0.6 else _q(rng.uniform(*BODY_WALL)))
    if rng.random() < 0.5:
        new["body_height"] = _q(base["body_height"] * (1 + rng.uniform(0.1, 0.3) * rng.choice((-1, 1))))
    if rng.random() < 0.3:
        new["port_bolt_hole_diameter"] = _q(base["port_bolt_hole_diameter"] + rng.choice((-1, 1)) * rng.uniform(1, 3))
    if rng.random() < 0.4:
        new["flange_thickness"] = _q(base["flange_thickness"] * (1 + rng.uniform(0.15, 0.4) * rng.choice((-1, 1))))
    if rng.random() < 0.6:
        new["port_reach"] = _q(base["port_reach"] * (1 + rng.uniform(0.05, 0.25) * rng.choice((-1, 1))))
    if any(not RANGES[k][0] <= new[k] <= RANGES[k][1] for k in new):
        return None
    if not _fill_flange(new, rng):
        return None
    proportional = base["port_bolt_circle_diameter"] * new["port_diameter"] / base["port_diameter"]
    if (abs(new["port_bolt_circle_diameter"] - base["port_bolt_circle_diameter"]) < MIN_CIRCLE_CHANGE
            or abs(new["port_bolt_circle_diameter"] - proportional) < MIN_CIRCLE_CHANGE):
        return None  # the bolt holes must visibly move, and not as "keep the drawn ratio to the port"
    return new if new != base and is_valid(new) else None


def overrides(base: dict[str, float], edited: dict[str, float]) -> dict[str, float]:
    """What build_part receives for an edit: only the parameters that changed."""
    return {k: v for k, v in edited.items() if base.get(k) != v}


def _unit(angle_deg: float) -> tuple[float, float, float]:
    a = math.radians(angle_deg)
    return (math.cos(a), math.sin(a), 0.0)


def port_features(params: dict[str, float]) -> list[dict]:
    """Every critical port feature, in the world frame: name, kind, centre on the flange's outer face,
    outward axis and diameter. Ports are `port_k`, their bolt holes `port_k_bolt_j`."""
    n_bolts, r, z0 = bolt_count(params), params["port_reach"], params["body_height"] / 2
    bc = params["port_bolt_circle_diameter"] / 2
    out = []
    for k, ang in enumerate(port_angles(params), start=1):
        ux, uy, _ = _unit(ang)
        out.append({"name": f"port_{k}", "kind": "port", "center": (r * ux, r * uy, z0), "axis": (ux, uy, 0.0),
                    "diameter": params["port_diameter"]})
        for j in range(n_bolts):  # hole 1 straight up, then counter-clockwise around the axis
            phi = math.pi / 2 + 2 * math.pi * j / n_bolts
            u, v = bc * math.cos(phi), bc * math.sin(phi)  # (tangential, vertical) in the flange plane
            out.append({"name": f"port_{k}_bolt_{j + 1}", "kind": "hole",
                        "center": (r * ux - u * uy, r * uy + u * ux, z0 + v), "axis": (ux, uy, 0.0),
                        "diameter": params["port_bolt_hole_diameter"]})
    return out


def _across(delta: tuple[float, float, float], axis: tuple[float, float, float]) -> float:
    along = sum(d * a for d, a in zip(delta, axis))
    return math.sqrt(max(0.0, sum(d * d for d in delta) - along * along))


def max_feature_shift(a: dict[str, float], b: dict[str, float]) -> float:
    """Largest move of any critical feature between two parameter sets, measured across the feature's own axis
    (the same way the evaluator compares positions)."""
    fa, fb = port_features(a), port_features(b)
    return max(_across(tuple(p - q for p, q in zip(x["center"], y["center"])), x["axis"]) for x, y in zip(fa, fb))


def parameter_specs(params: dict[str, float]) -> list[ParameterSpec]:
    """Published parameters: everything but the structural port and bolt counts (read off the drawing)."""
    return [ParameterSpec(name=n, description=DESCRIPTIONS[n], min=RANGES[n][0], max=RANGES[n][1])
            for n in params if n not in STRUCTURAL]


def critical_feature_specs(params: dict[str, float]) -> list[CriticalFeatureSpec]:
    specs = [CriticalFeatureSpec(name="body_bore", kind="bore", description="centred through-bore of the body",
                                 size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL)]
    for f in port_features(params):
        if f["kind"] == "port":
            desc = (f"port bore on the flange's outer face, axis pointing {math.degrees(math.atan2(f['axis'][1], f['axis'][0])):g} "
                    f"degrees from +X ({port_count(params)} ports in all)")
        else:
            desc = f"bolt hole of {f['name'].split('_bolt_')[0]} ({bolt_count(params)} per flange, hole 1 straight up)"
        specs.append(CriticalFeatureSpec(name=f["name"], kind=f["kind"], description=desc,
                                         size_tolerance_mm=SIZE_TOL, position_tolerance_mm=POSITION_TOL))
    return specs


def required_labels(params: dict[str, float]) -> list[str]:
    """Text that must appear in the drawing's dimension labels, or the drawing is rejected."""
    return [f"⌀{params['body_diameter']:g}", f"⌀{params['body_bore_diameter']:g}", f"{params['body_height']:g}",
            f"⌀{params['port_diameter']:g}", f"⌀{stub_diameter(params):g}", f"{params['port_reach']:g}",
            f"⌀{params['flange_diameter']:g}", f"{params['flange_thickness']:g}",
            f"⌀{params['port_bolt_circle_diameter']:g}", f"⌀{params['port_bolt_hole_diameter']:g}",
            f"{bolt_count(params)}× ⌀{params['port_bolt_hole_diameter']:g} THRU EQ SP ON ⌀{params['port_bolt_circle_diameter']:g} BC"]
