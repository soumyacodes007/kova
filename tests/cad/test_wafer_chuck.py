"""Runs in the CAD worker env (build123d 0.13)."""

import pytest
from build123d import Cylinder, Pos

from cadrecover.challenges.families import wafer_chuck, wafer_chuck_spec as spec
from cadrecover.challenges.measure import measure


def _seed(ring2: bool, mount: bool, ring1_count: int | None = None) -> int:
    return next(s for s in range(2000) if spec.has_ring2(spec.sample(s)) == ring2 and spec.has_mount(spec.sample(s)) == mount
                and (ring1_count is None or spec.sample(s)["ring1_count"] == ring1_count))


def test_reference_self_test_passes_across_seeds():
    for seed in range(25):
        params = spec.sample(seed)
        result = wafer_chuck.self_test(params)
        assert result["ok"], (seed, params, result["checks"], result["feature_problems"])


@pytest.mark.parametrize("ring2,mount", [(False, False), (True, False), (False, True), (True, True)],
                         ids=["1ring", "2rings", "1ring-mount", "2rings-mount"])
def test_measure_finds_every_hole_but_not_the_rim(ring2, mount):
    params = spec.sample(_seed(ring2, mount))
    holes = [f for f in measure(wafer_chuck.build(params)) if f.kind == "hole"]
    assert len(holes) == spec.hole_count(params)  # the outer rim is convex: not a hole
    diameters = sorted(spec.hole_diameters(params).values())
    assert sorted(h.diameter for h in holes) == pytest.approx(diameters)
    assert all(h.center[2] == pytest.approx(params["thickness"]) for h in holes)


def test_self_test_catches_a_wrong_part():
    params = spec.sample(_seed(False, False))
    part = wafer_chuck.build(params)
    part -= Pos(0, 0, params["thickness"] / 2) * Cylinder(params["pin_circle_diameter"] / 4, 3 * params["thickness"])
    result = wafer_chuck.self_test(params, part)
    assert not result["ok"] and not result["checks"]["volume"]


def test_wrong_ring_count_is_reported_missing():
    params = spec.sample(_seed(False, False, ring1_count=6))
    result = wafer_chuck.self_test(params, wafer_chuck.build(dict(params, ring1_count=12.0)))
    assert not result["ok"]
    # the six real holes are still there, six unexpected extras are reported (and the reverse for 12 -> 6)
    assert sum(p.startswith("unexpected:") for p in result["feature_problems"]) == 6
    params12 = spec.sample(_seed(False, False, ring1_count=12))
    missing = wafer_chuck.self_test(params12, wafer_chuck.build(dict(params12, ring1_count=6.0)))["feature_problems"]
    assert sum(p.startswith("vac1_") for p in missing) == 6


def test_moved_ring_is_reported_missing():
    params = spec.sample(_seed(True, False))
    result = wafer_chuck.self_test(params, wafer_chuck.build(dict(params, ring1_diameter=params["ring1_diameter"] + 2)))
    assert not result["ok"]
    n = int(params["ring1_count"])
    assert {f"vac1_{k}" for k in range(1, n + 1)} <= set(result["feature_problems"])
