"""build123d source templates for scripted miner strategies (owner: agent C).

A strategy decides what it *read* off the drawing (`drawn` values) and a mode;
the template turns that into a submission. Honest mode is fully parametric.
The other modes are labelled diagnostics that the mechanism must punish:

  constant      ignores overrides: right at s0 only                -> expect 25
  proportional  holes scale with the part instead of the edit rule  -> expect 25
                (plate: 10 mm edge offset; flange: bolt circle scales with the outer diameter)
  wrong_holes   hole diameter off by 30%                           -> expect 0
  crash         forbidden import                                   -> expect 0 (invalid source)
  timeout       never returns                                      -> expect 0
"""

from __future__ import annotations

MODES = ("honest", "constant", "proportional", "wrong_holes", "crash", "timeout")

_PLATE = '''\
"""{header}"""
{imports}from build123d import Align, Box, Cylinder, Pos

DRAWN = {drawn!r}  # values read off the drawing
EDGE_OFFSET = 10.0


def build_part(overrides):
{body}    w, l, t = p["width"], p["length"], p["thickness"]
    part = Box(w, l, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
{holes}    if "slot_length" in p:
        straight = p["slot_length"] - p["slot_width"]
        slot = Pos(0, 0, t / 2) * Box(straight, p["slot_width"], 3 * t)
        slot += Pos(-straight / 2, 0, t / 2) * Cylinder(p["slot_width"] / 2, 3 * t)
        slot += Pos(straight / 2, 0, t / 2) * Cylinder(p["slot_width"] / 2, 3 * t)
        part -= slot
    return part
'''

_HOLES_RULE = '''\
    x, y = w / 2 - EDGE_OFFSET, l / 2 - EDGE_OFFSET
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= Pos(sx * x, sy * y, t / 2) * Cylinder(p["hole_diameter"] / 2, 3 * t)
'''

_HOLES_PROPORTIONAL = '''\
    # holes kept at the drawn *fraction* of the plate, not 10 mm from the edges
    fx = (DRAWN["width"] / 2 - EDGE_OFFSET) / DRAWN["width"]
    fy = (DRAWN["length"] / 2 - EDGE_OFFSET) / DRAWN["length"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= Pos(sx * fx * w, sy * fy * l, t / 2) * Cylinder(p["hole_diameter"] / 2, 3 * t)
'''


def plate_source(drawn: dict[str, float], mode: str = "honest", label: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    body = {
        "constant": "    p = dict(DRAWN)  # ignores overrides\n",
        "wrong_holes": "    p = {**DRAWN, **overrides}\n    p['hole_diameter'] = p['hole_diameter'] * 1.3\n",
        "timeout": "    while True:\n        pass\n    p = {}\n",
    }.get(mode, "    p = {**DRAWN, **overrides}\n")
    return _PLATE.format(
        header=f"CADRecover plate solution ({label or mode})",
        imports="import socket  # forbidden: no network in a CAD submission\n" if mode == "crash" else "",
        drawn={k: float(v) for k, v in drawn.items()},
        body=body,
        holes=_HOLES_PROPORTIONAL if mode == "proportional" else _HOLES_RULE,
    )


_FLANGE = '''"""{header}"""
{imports}import math

from build123d import Align, Cylinder, Pos

DRAWN = {drawn!r}  # values read off the drawing (bolt_count is the number of holes counted on it)


def build_part(overrides):
{body}    t = p["thickness"]
    hub = "hub_diameter" in p
    h = t + (p["hub_height"] if hub else 0.0)
    part = Cylinder(p["outer_diameter"] / 2, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    if hub:
        part += Pos(0, 0, t) * Cylinder(p["hub_diameter"] / 2, p["hub_height"], align=(Align.CENTER, Align.CENTER, Align.MIN))
    part -= Pos(0, 0, h / 2) * Cylinder(p["bore_diameter"] / 2, 3 * h)
    n = int(DRAWN["bolt_count"])
{circle}    for k in range(n):
        a = 2 * math.pi * k / n
        part -= Pos(r * math.cos(a), r * math.sin(a), t / 2) * Cylinder(p["bolt_hole_diameter"] / 2, 3 * t)
    return part
'''

_CIRCLE_RULE = '    r = p["bolt_circle_diameter"] / 2\n'
_CIRCLE_PROPORTIONAL = '''\
    # bolt circle kept at the drawn *fraction* of the outer diameter, not at the edited bolt_circle_diameter
    r = DRAWN["bolt_circle_diameter"] / DRAWN["outer_diameter"] * p["outer_diameter"] / 2
'''


def flange_source(drawn: dict[str, float], mode: str = "honest", label: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    body = {
        "constant": "    p = dict(DRAWN)  # ignores overrides\n",
        "wrong_holes": "    p = {**DRAWN, **overrides}\n    p['bolt_hole_diameter'] = p['bolt_hole_diameter'] * 1.3\n",
        "timeout": "    while True:\n        pass\n    p = {}\n",
    }.get(mode, "    p = {**DRAWN, **overrides}\n")
    return _FLANGE.format(
        header=f"CADRecover flange solution ({label or mode})",
        imports="import socket  # forbidden: no network in a CAD submission\n" if mode == "crash" else "",
        drawn={k: float(v) for k, v in drawn.items()},
        body=body,
        circle=_CIRCLE_PROPORTIONAL if mode == "proportional" else _CIRCLE_RULE,
    )


_WAFER_CHUCK = '''"""{header}"""
{imports}import math

from build123d import Align, Compound, Cylinder, Pos

DRAWN = {drawn!r}  # values read off the drawing (ring counts are the holes counted on it)


def build_part(overrides):
{body}    t = p["thickness"]
    part = Cylinder(p["plate_diameter"] / 2, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # (circle diameter, hole diameter, hole count), centre outward; hole 1 of each circle on +X
    circles = [("pin_circle_diameter", "pin_hole_diameter", 3),
               ("ring1_diameter", "vacuum_hole_diameter", int(DRAWN["ring1_count"]))]
    if "ring2_diameter" in DRAWN:
        circles.append(("ring2_diameter", "vacuum_hole_diameter", int(DRAWN["ring2_count"])))
    if "mount_circle_diameter" in DRAWN:
        circles.append(("mount_circle_diameter", "mount_hole_diameter", 4))
    cutters = []
    for circle, hole, n in circles:
{radius}        for k in range(n):
            a = 2 * math.pi * k / n
            cutters.append(Pos(r * math.cos(a), r * math.sin(a), t / 2) * Cylinder(p[hole] / 2, 3 * t))
    return part - Compound(cutters)
'''

_RADIUS_RULE = '        r = p[circle] / 2\n'
_RADIUS_PROPORTIONAL = '''\
        # every circle kept at the drawn *fraction* of the plate diameter, not at its own edited diameter
        r = DRAWN[circle] / DRAWN["plate_diameter"] * p["plate_diameter"] / 2
'''


def wafer_chuck_source(drawn: dict[str, float], mode: str = "honest", label: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    body = {
        "constant": "    p = dict(DRAWN)  # ignores overrides\n",
        "wrong_holes": "    p = {**DRAWN, **overrides}\n    p['vacuum_hole_diameter'] = p['vacuum_hole_diameter'] * 1.3\n",
        "timeout": "    while True:\n        pass\n    p = {}\n",
    }.get(mode, "    p = {**DRAWN, **overrides}\n")
    return _WAFER_CHUCK.format(
        header=f"CADRecover wafer chuck solution ({label or mode})",
        imports="import socket  # forbidden: no network in a CAD submission\n" if mode == "crash" else "",
        drawn={k: float(v) for k, v in drawn.items()},
        body=body,
        radius=_RADIUS_PROPORTIONAL if mode == "proportional" else _RADIUS_RULE,
    )


_VACUUM_CHAMBER = '''"""{header}"""
{imports}import math

from build123d import Align, Cylinder, Pos, Rot

DRAWN = {drawn!r}  # values read off the drawing (port_count and bolt_count are counted on it)
ANGLES = sorted((0.0, 90.0, 180.0, 270.0, 45.0, 135.0)[: int(DRAWN["port_count"])])  # degrees, port 1 on +X


def along_x(radius, length, x, u=0.0, v=0.0):
    return Pos(x, u, v) * Rot(0, 90, 0) * Cylinder(radius, length)


def build_part(overrides):
{body}    d, db, h = p["body_diameter"], p["body_bore_diameter"], p["body_height"]
    r, ft = p["port_reach"], p["flange_thickness"]
    n = int(DRAWN["bolt_count"])
{circle}    x0, x1 = db / 4, r - ft
    port = along_x((p["port_diameter"] + 8.0) / 2, x1 - x0, (x0 + x1) / 2)  # stub tube, 4 mm wall
    port += along_x(p["flange_diameter"] / 2, ft, r - ft / 2)  # flange disc, outer face at r
    for j in range(n):  # bolt hole 1 straight up, then evenly around the port axis
        phi = math.pi / 2 + 2 * math.pi * j / n
        port -= along_x(p["port_bolt_hole_diameter"] / 2, 2 * ft, r - ft / 2, bc / 2 * math.cos(phi), bc / 2 * math.sin(phi))
    part = Cylinder(d / 2, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for a in ANGLES:
        part += Pos(0, 0, h / 2) * Rot(0, 0, a) * port
    part -= Pos(0, 0, h / 2) * Cylinder(db / 2, 3 * h)  # hollow body
    for a in ANGLES:  # every port bore opens into the body
        part -= Pos(0, 0, h / 2) * Rot(0, 0, a) * along_x(p["port_diameter"] / 2, r + ft - db / 4, (db / 4 + r + ft) / 2)
    return part
'''

_CHAMBER_CIRCLE_RULE = '    bc = p["port_bolt_circle_diameter"]\n'
_CHAMBER_CIRCLE_PROPORTIONAL = '''\
    # bolt circle kept at the drawn *fraction* of the port diameter, not at the edited bolt circle
    bc = DRAWN["port_bolt_circle_diameter"] / DRAWN["port_diameter"] * p["port_diameter"]
'''


def vacuum_chamber_source(drawn: dict[str, float], mode: str = "honest", label: str = "") -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    body = {
        "constant": "    p = dict(DRAWN)  # ignores overrides\n",
        "wrong_holes": "    p = {**DRAWN, **overrides}\n    p['port_bolt_hole_diameter'] = p['port_bolt_hole_diameter'] * 1.3\n",
        "timeout": "    while True:\n        pass\n    p = {}\n",
    }.get(mode, "    p = {**DRAWN, **overrides}\n")
    return _VACUUM_CHAMBER.format(
        header=f"CADRecover vacuum chamber solution ({label or mode})",
        imports="import socket  # forbidden: no network in a CAD submission\n" if mode == "crash" else "",
        drawn={k: float(v) for k, v in drawn.items()},
        body=body,
        circle=_CHAMBER_CIRCLE_PROPORTIONAL if mode == "proportional" else _CHAMBER_CIRCLE_RULE,
    )


SOURCES = {"plate": plate_source, "flange": flange_source, "wafer_chuck": wafer_chuck_source,
           "vacuum_chamber": vacuum_chamber_source}


def source_for(family: str, drawn: dict[str, float], mode: str = "honest", label: str = "") -> str:
    """The template for a challenge family; ValueError for a family without one."""
    if family not in SOURCES:
        raise ValueError(f"no template for family {family!r} yet")
    return SOURCES[family](drawn, mode, label)
