"""Runs in the CAD worker env (build123d 0.13)."""

import math

import pytest
from build123d import Cylinder, Pos

from cadrecover.challenges.families import vacuum_chamber as chamber, vacuum_chamber_spec as spec
from cadrecover.challenges.measure import measure


def _seed(ports: int, bolts: int | None = None) -> int:
    return next(s for s in range(2000) if spec.port_count(spec.sample(s)) == ports
                and (bolts is None or spec.bolt_count(spec.sample(s)) == bolts))


def test_reference_self_test_passes_across_seeds():
    for seed in range(20):
        params = spec.sample(seed)
        result = chamber.self_test(params)
        assert result["ok"], (seed, params, result["checks"], result["feature_problems"])


@pytest.mark.parametrize("ports", [4, 5, 6])
def test_measure_finds_every_port_and_bolt_hole_with_outward_axes(ports):
    params = spec.sample(_seed(ports))
    feats = measure(chamber.build(params))
    found_ports = [f for f in feats if f.kind == "port"]
    holes = [f for f in feats if f.kind == "hole"]
    n_bolts = spec.bolt_count(params)
    assert len(found_ports) == ports
    assert len(holes) == 1 + ports * n_bolts  # the body bore plus every bolt hole; rims and stubs are not holes
    for f in found_ports:
        assert abs(f.diameter - params["port_diameter"]) < 1e-9
        assert f.center[2] == pytest.approx(params["body_height"] / 2)
        assert math.hypot(f.center[0], f.center[1]) == pytest.approx(params["port_reach"])  # on the flange's outer face
        assert f.axis[0] * f.center[0] + f.axis[1] * f.center[1] > 0  # points away from the Z axis
    angles = sorted(round(math.degrees(math.atan2(f.axis[1], f.axis[0])) % 360, 6) for f in found_ports)
    assert angles == pytest.approx(spec.port_angles(params))
    z_holes = [h for h in holes if abs(abs(h.axis[2]) - 1) < 1e-9]
    assert len(z_holes) == 1 and z_holes[0].center == pytest.approx((0, 0, params["body_height"]))
    assert abs(z_holes[0].diameter - params["body_bore_diameter"]) < 1e-9
    assert all(abs(h.diameter - params["port_bolt_hole_diameter"]) < 1e-9 for h in holes if h not in z_holes)


def test_opposite_ports_have_opposite_axes():
    params = spec.sample(_seed(4))
    axes = {tuple(round(c, 6) for c in f.axis) for f in measure(chamber.build(params)) if f.kind == "port"}
    assert axes == {(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0)}


def test_self_test_catches_a_wrong_part():
    params = spec.sample(_seed(4))
    part = chamber.build(params)
    part -= Pos(0, 0, params["body_height"] / 2) * Cylinder(params["body_bore_diameter"] / 2 + 3, 3 * params["body_height"])
    result = chamber.self_test(params, part)
    assert not result["ok"] and not result["checks"]["volume"]


def test_a_missing_port_is_reported():
    params = spec.sample(_seed(6))
    result = chamber.self_test(params, chamber.build(dict(params, port_count=5.0)))
    assert not result["ok"] and any(p.startswith("port_") for p in result["feature_problems"])  # the 135 degree port


def test_moved_bolt_circle_and_wrong_bolt_count_are_reported():
    params = spec.sample(_seed(5, 6))
    moved = chamber.self_test(params, chamber.build(dict(params, port_bolt_circle_diameter=params["port_bolt_circle_diameter"] + 2)))
    assert not moved["ok"] and any("_bolt_" in p for p in moved["feature_problems"])
    fewer = chamber.self_test(params, chamber.build(dict(params, bolt_count=4.0)))
    assert not fewer["ok"] and any("_bolt_" in p for p in fewer["feature_problems"])


def test_a_port_off_its_axis_height_is_reported():
    params = spec.sample(_seed(4))
    result = chamber.self_test(params, chamber.build(dict(params, body_height=params["body_height"] + 2.0)))
    assert not result["ok"]  # ports sit at body_height / 2: they moved 1 mm


def test_the_stub_is_four_millimetres_thick():
    params = spec.sample(_seed(4))
    assert spec.stub_diameter(params) == params["port_diameter"] + 8.0
