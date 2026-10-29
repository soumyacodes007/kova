"""Runs in the CAD worker env (build123d 0.13)."""

from build123d import Pos, Cylinder

from cadrecover.challenges.families import plate, plate_spec as spec
from cadrecover.challenges.measure import measure


def _seed_with(slot: bool) -> int:
    return next(s for s in range(1000) if spec.has_slot(spec.sample(s)) == slot)


def test_reference_self_test_passes_across_seeds():
    for seed in range(25):
        params = spec.sample(seed)
        result = plate.self_test(params)
        assert result["ok"], (seed, params, result["checks"], result["feature_problems"])


def test_measure_finds_four_holes_and_the_slot():
    params = spec.sample(_seed_with(slot=True))
    feats = measure(plate.build(params))
    holes = [f for f in feats if f.kind == "hole"]
    slots = [f for f in feats if f.kind == "slot"]
    assert len(holes) == 4 and len(slots) == 1
    assert abs(slots[0].length - params["slot_length"]) < 1e-6
    assert abs(slots[0].diameter - params["slot_width"]) < 1e-6
    for h in holes:
        assert abs(h.diameter - params["hole_diameter"]) < 1e-6


def test_self_test_catches_a_wrong_part():
    params = spec.sample(_seed_with(slot=False))
    part = plate.build(params)
    # an extra hole the spec doesn't have
    part -= Pos(0, 0, params["thickness"] / 2) * Cylinder(1.5, 3 * params["thickness"])
    result = plate.self_test(params, part)
    assert not result["ok"]
    assert not result["checks"]["volume"] and not result["checks"]["features"]
    assert any(p.startswith("unexpected:") for p in result["feature_problems"])


def test_moved_hole_is_reported_missing():
    params = spec.sample(_seed_with(slot=False))
    shifted = dict(params, width=params["width"] + 2)  # build at a different width: holes move 1 mm
    result = plate.self_test(params, plate.build(shifted))
    assert not result["ok"]
    assert {"hole_1", "hole_2", "hole_3", "hole_4"} <= set(result["feature_problems"])
