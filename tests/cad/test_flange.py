"""Runs in the CAD worker env (build123d 0.13)."""

import pytest
from build123d import Cylinder, Pos

from cadrecover.challenges.families import flange, flange_spec as spec
from cadrecover.challenges.measure import measure


def _seed(hub: bool, count: int | None = None) -> int:
    return next(s for s in range(2000) if spec.has_hub(spec.sample(s)) == hub
                and (count is None or spec.bolt_count(spec.sample(s)) == count))


def test_reference_self_test_passes_across_seeds():
    for seed in range(25):
        params = spec.sample(seed)
        result = flange.self_test(params)
        assert result["ok"], (seed, params, result["checks"], result["feature_problems"])


@pytest.mark.parametrize("hub", [False, True], ids=["plain", "hub"])
def test_measure_finds_bore_and_every_bolt_hole_but_not_the_rim_or_hub(hub):
    params = spec.sample(_seed(hub))
    holes = [f for f in measure(flange.build(params)) if f.kind == "hole"]
    assert len(holes) == spec.bolt_count(params) + 1  # the outer rim and the hub are convex: not holes
    bore = [h for h in holes if abs(h.center[0]) < 1e-9 and abs(h.center[1]) < 1e-9]
    assert len(bore) == 1 and abs(bore[0].diameter - params["bore_diameter"]) < 1e-9
    assert bore[0].center[2] == pytest.approx(spec.total_height(params))  # reported at its highest edge
    for h in holes:
        if h not in bore:
            assert abs(h.diameter - params["bolt_hole_diameter"]) < 1e-9
            assert h.center[2] == pytest.approx(params["thickness"])  # on the disc's top face, below any hub


def test_self_test_catches_a_wrong_part():
    params = spec.sample(_seed(hub=False))
    part = flange.build(params)
    part -= Pos(0, 0, params["thickness"] / 2) * Cylinder(params["bore_diameter"] / 2 + 3, 3 * params["thickness"])
    result = flange.self_test(params, part)
    assert not result["ok"] and not result["checks"]["volume"]


def test_wrong_bolt_count_is_reported_missing():
    params = spec.sample(_seed(hub=False, count=6))
    result = flange.self_test(params, flange.build(dict(params, bolt_count=4.0)))
    assert not result["ok"]
    assert {"bolt_2", "bolt_3", "bolt_5", "bolt_6"} <= set(result["feature_problems"])


def test_moved_bolt_circle_is_reported_missing():
    params = spec.sample(_seed(hub=True))
    result = flange.self_test(params, flange.build(dict(params, bolt_circle_diameter=params["bolt_circle_diameter"] + 2)))
    assert not result["ok"]
    assert {f"bolt_{k}" for k in range(1, spec.bolt_count(params) + 1)} <= set(result["feature_problems"])
