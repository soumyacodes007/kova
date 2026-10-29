"""build123d source templates for scripted miner strategies (owner: agent C).

A strategy decides what it *read* off the drawing (`drawn` values) and a mode;
the template turns that into a submission. Honest mode is fully parametric.
The other modes are labelled diagnostics that the mechanism must punish:

  constant      ignores overrides: right at s0 only                -> expect 25
  proportional  holes scale with the plate instead of the 10 mm rule -> expect 25
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
