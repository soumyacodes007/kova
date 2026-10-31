"""PRD v2.1 self-test on real vacuum chamber solids (CAD env): reference 100, one-edit-wrong 75, constant 25,
wrong bolt-hole size 0; plus the chamber's own failure modes (stale port diameter, rotated or missing port)."""

import pytest

from cadrecover.challenges.edits import MAX_SELF_IOU, SHIFT_FACTOR, sample_edits
from cadrecover.challenges.families import vacuum_chamber as chamber, vacuum_chamber_spec as spec
from cadrecover.evaluation.checks import score_set
from cadrecover.protocol import task_quality


def _seed(ports: int, bolts: int) -> int:
    return next(s for s in range(2000) if spec.port_count(spec.sample(s)) == ports and spec.bolt_count(spec.sample(s)) == bolts)


@pytest.fixture(scope="module", params=[(4, 6), (6, 4), (5, 6)], ids=["4-ports", "6-ports", "5-ports"])
def task(request):
    seed = _seed(*request.param)
    base = spec.sample(seed)
    edits = sample_edits(spec, chamber, base, seed)
    sets = [base] + [e["values"] for e in edits]
    refs = [chamber.build(v) for v in sets]
    return sets, refs, edits


def _score_sets(sets, refs, candidates):
    return [score_set(i, v, refs[i], c, chamber.expected_features(v), iou_fn=chamber.iou,
                      size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
            for i, (v, c) in enumerate(zip(sets, candidates))]


def _score(sets, refs, candidates):
    return task_quality(_score_sets(sets, refs, candidates))


def _names(scores):
    return {f.name for s in scores for f in s.failed_checks}


def test_edits_are_discriminative(task):
    sets, _, edits = task
    for e in edits:
        assert e["max_feature_shift_mm"] > SHIFT_FACTOR * spec.POSITION_TOL
        assert e["reference_self_iou"] < MAX_SELF_IOU
        assert e["overrides"]["port_diameter"] != sets[0]["port_diameter"]  # every edit changes the port diameter
        assert set(e["overrides"]) <= set(sets[0])
    assert all(v["port_count"] == sets[0]["port_count"] and v["bolt_count"] == sets[0]["bolt_count"] for v in sets)


def test_correct_model_scores_100(task):
    sets, refs, _ = task
    assert _score(sets, refs, [chamber.build(v) for v in sets]) == pytest.approx(100.0)


def test_one_edit_wrong_scores_75(task):
    sets, refs, _ = task
    cands = [chamber.build(v) for v in sets]
    cands[2] = chamber.build(dict(sets[2], port_bolt_circle_diameter=sets[2]["port_bolt_circle_diameter"] + 2.0))  # 1 mm drift at s2
    assert _score(sets, refs, cands) == pytest.approx(75.0)


def test_constant_model_scores_25(task):
    sets, refs, _ = task
    s0 = chamber.build(sets[0])
    assert _score(sets, refs, [s0, s0, s0, s0]) == pytest.approx(25.0)


def test_bolt_circle_scaling_with_the_port_scores_25(task):
    """The "proportional" mistake: keep the drawn bolt-circle / port-diameter ratio instead of the parameter."""
    sets, refs, _ = task
    ratio = sets[0]["port_bolt_circle_diameter"] / sets[0]["port_diameter"]
    cands = [chamber.build(dict(v, port_bolt_circle_diameter=ratio * v["port_diameter"])) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(25.0)


def test_wrong_bolt_hole_size_scores_0(task):
    sets, refs, _ = task
    cands = [chamber.build(dict(v, port_bolt_hole_diameter=v["port_bolt_hole_diameter"] * 1.3)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_wrong_port_diameter_scores_0(task):
    sets, refs, _ = task
    cands = [chamber.build(dict(v, port_diameter=v["port_diameter"] + 1.0)) for v in sets]
    scores = _score_sets(sets, refs, cands)
    assert task_quality(scores) == pytest.approx(0.0) and "port_1.size" in _names(scores)


def test_ports_that_keep_the_old_diameter_after_an_edit_fail(task):
    """The demo: the port diameter changes and the model must change every port with it."""
    sets, refs, _ = task
    old = sets[0]["port_diameter"]
    cands = [chamber.build(dict(v, port_diameter=old)) for v in sets]
    scores = _score_sets(sets, refs, cands)
    assert scores[0].critical_ok and all(not s.critical_ok for s in scores[1:])
    assert task_quality(scores) == pytest.approx(25.0)
    assert any(n.startswith("port_") and n.endswith(".size") for n in _names(scores[1:]))


def test_one_port_rotated_a_few_degrees_fails_on_axis_and_position(task, monkeypatch):
    sets, refs, _ = task
    cands = [chamber.build(v) for v in sets]
    real = spec.port_angles
    monkeypatch.setattr(spec, "port_angles", lambda p: [real(p)[0] + 3.0] + real(p)[1:])  # port 1 turned by 3 degrees
    cands[2] = chamber.build(sets[2])
    monkeypatch.undo()
    scores = _score_sets(sets, refs, cands)
    assert not scores[2].critical_ok and all(s.critical_ok for i, s in enumerate(scores) if i != 2)
    assert task_quality(scores) == pytest.approx(75.0)
    assert "port_1.axis" in _names(scores) and "port_1_bolt_1.axis" in _names(scores)


def test_a_port_tilted_in_place_fails_on_axis_alone():
    """Rotating a port about its own centre keeps the flange-face centre but tips the axis: caught by the axis check."""
    from cadrecover.protocol import FeatureMeasurement
    from cadrecover.evaluation.checks import critical

    e = FeatureMeasurement(name="port_1", kind="port", center=(150.0, 0.0, 90.0), axis=(1.0, 0.0, 0.0), diameter=40.0)
    straight = FeatureMeasurement(name="p", kind="port", center=(150.0, 0.0, 90.0), axis=(1.0, 0.0, 0.0), diameter=40.0)
    tilted = FeatureMeasurement(name="p", kind="port", center=(150.0, 0.0, 90.0), axis=(0.99985, 0.0175, 0.0), diameter=40.0)
    assert critical([e], [straight], 0.1, 0.1)[0]
    ok, failed = critical([e], [tilted], 0.1, 0.1)
    assert not ok and [f.name for f in failed] == ["port_1.axis"]


def test_a_missing_port_fails_critical(task):
    sets, refs, _ = task
    cands = [chamber.build(v) for v in sets]
    cands[1] = chamber.build(dict(sets[1], port_count=4.0)) if spec.port_count(sets[1]) > 4 else \
        chamber.build(dict(sets[1], port_count=5.0))  # 4-port reference: an extra port instead
    scores = _score_sets(sets, refs, cands)
    assert not scores[1].critical_ok
    names = _names(scores)  # the nearest measured port is compared instead, so the failure names an axis or an extra port
    assert any(n.startswith(("port_", "extra_")) for n in names), names
    assert task_quality(scores) <= 75.0


def test_an_extra_port_fails_critical():
    base = spec.sample(_seed(4, 6))
    ref = chamber.build(base)
    cand = chamber.build(dict(base, port_count=5.0))
    s = score_set(0, base, ref, cand, chamber.expected_features(base), iou_fn=chamber.iou,
                  size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
    assert not s.critical_ok and {"extra_port", "extra_hole"} & {f.name for f in s.failed_checks}


def test_a_swapped_opposite_port_axis_is_not_matched():
    """+X and -X ports share an axis line: only the outward orientation tells them apart."""
    from cadrecover.protocol import FeatureMeasurement
    from cadrecover.evaluation.checks import critical

    e = [FeatureMeasurement(name="port_1", kind="port", center=(150.0, 0.0, 90.0), axis=(1.0, 0.0, 0.0), diameter=40.0),
         FeatureMeasurement(name="port_3", kind="port", center=(-150.0, 0.0, 90.0), axis=(-1.0, 0.0, 0.0), diameter=40.0)]
    only_first = [e[0]]
    ok, failed = critical(e, only_first, 0.1, 0.1)
    assert not ok and any(f.name.startswith("port_3") for f in failed)  # the -X port must not match the +X one


def test_misread_flange_thickness_and_reach_cost_geometry_not_critical_features(task):
    sets, refs, _ = task
    thick = [chamber.build(dict(v, flange_thickness=v["flange_thickness"] - 1.0)) for v in sets]
    scores = _score_sets(sets, refs, thick)
    assert all(s.valid and s.critical_ok for s in scores), [f.name for s in scores for f in s.failed_checks]
    assert all(s.geometry < 1.0 for s in scores)
    assert 50 < task_quality(scores) < 100
    # a port reach misread moves flanges along their own axes: not a misplaced port, but the envelope and overlap pay
    far = [chamber.build(dict(v, port_reach=v["port_reach"] + 1.0)) for v in sets]
    scores = _score_sets(sets, refs, far)
    assert all(s.critical_ok for s in scores) and all(s.dimensions < 1.0 and s.geometry < 1.0 for s in scores)
