"""PRD v2.1 self-test on real wafer chuck solids (CAD env): reference 100, one-edit-wrong 75, constant 25, wrong hole 0."""

import pytest

from cadrecover.challenges.edits import MAX_SELF_IOU, SHIFT_FACTOR, sample_edits
from cadrecover.challenges.families import wafer_chuck, wafer_chuck_spec as spec
from cadrecover.evaluation.checks import score_set
from cadrecover.protocol import task_quality

CIRCLES = ("pin_circle_diameter", "ring1_diameter", "ring2_diameter", "mount_circle_diameter")


def _seed(ring2: bool, mount: bool) -> int:
    return next(s for s in range(2000) if spec.has_ring2(spec.sample(s)) == ring2 and spec.has_mount(spec.sample(s)) == mount)


@pytest.fixture(scope="module", params=[(False, True), (True, False), (True, True)],
                ids=["1ring-mount", "2rings", "2rings-mount"])
def task(request):
    seed = _seed(*request.param)
    base = spec.sample(seed)
    edits = sample_edits(spec, wafer_chuck, base, seed)
    sets = [base] + [e["values"] for e in edits]
    refs = [wafer_chuck.build(v) for v in sets]
    return sets, refs, edits


def _score_sets(sets, refs, candidates):
    return [score_set(i, v, refs[i], c, wafer_chuck.expected_features(v), iou_fn=wafer_chuck.iou,
                      size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
            for i, (v, c) in enumerate(zip(sets, candidates))]


def _score(sets, refs, candidates):
    return task_quality(_score_sets(sets, refs, candidates))


def test_edits_are_discriminative(task):
    sets, _, edits = task
    for e in edits:
        assert e["max_feature_shift_mm"] > SHIFT_FACTOR * spec.POSITION_TOL
        assert e["reference_self_iou"] < MAX_SELF_IOU
        assert e["overrides"] and set(e["overrides"]) <= set(sets[0])
        assert "plate_diameter" in e["overrides"] and "ring1_diameter" in e["overrides"]
    for v in sets:  # structure never changes
        assert v["ring1_count"] == sets[0]["ring1_count"] and spec.has_ring2(v) == spec.has_ring2(sets[0])
        assert spec.has_mount(v) == spec.has_mount(sets[0]) and v.get("ring2_count") == sets[0].get("ring2_count")


def test_correct_model_scores_100(task):
    sets, refs, _ = task
    assert _score(sets, refs, [wafer_chuck.build(v) for v in sets]) == pytest.approx(100.0)


def test_one_edit_wrong_scores_75(task):
    sets, refs, _ = task
    cands = [wafer_chuck.build(v) for v in sets]
    drift = dict(sets[2], ring1_diameter=sets[2]["ring1_diameter"] + 2.0)  # ring 1 drifts 1 mm at s2 only
    cands[2] = wafer_chuck.build(drift)
    assert _score(sets, refs, cands) == pytest.approx(75.0)


def test_constant_model_scores_25(task):
    sets, refs, _ = task
    s0 = wafer_chuck.build(sets[0])
    assert _score(sets, refs, [s0, s0, s0, s0]) == pytest.approx(25.0)


def test_pattern_scaling_with_the_plate_scores_25(task):
    """The "proportional" mistake: keep each circle at its drawn fraction of the plate diameter."""
    sets, refs, _ = task
    s0 = sets[0]
    cands = []
    for v in sets:
        scaled = dict(v)
        for c in CIRCLES:
            if c in s0:
                scaled[c] = s0[c] / s0["plate_diameter"] * v["plate_diameter"]
        cands.append(wafer_chuck.build(scaled))
    scores = _score_sets(sets, refs, cands)
    assert all(s.critical_ok for s in scores[:1]) and not any(s.critical_ok for s in scores[1:])
    assert task_quality(scores) == pytest.approx(25.0)


@pytest.mark.parametrize("key", ["vacuum_hole_diameter", "pin_hole_diameter"])
def test_wrong_hole_size_scores_0(task, key):
    sets, refs, _ = task
    cands = [wafer_chuck.build(dict(v, **{key: v[key] * 1.3})) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_wrong_ring_count_scores_0(task):
    sets, refs, _ = task
    wrong = 6.0 if sets[0]["ring1_count"] != 6 else 8.0
    cands = [wafer_chuck.build(dict(v, ring1_count=wrong)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_missing_second_ring_scores_0(task):
    sets, refs, _ = task
    if not spec.has_ring2(sets[0]):
        pytest.skip("single-ring variant")
    cands = [wafer_chuck.build({k: x for k, x in v.items() if k not in ("ring2_diameter", "ring2_count")}) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_misread_thickness_costs_geometry_not_critical_features(task):
    sets, refs, _ = task
    thick = [wafer_chuck.build(dict(v, thickness=v["thickness"] - 1.0)) for v in sets]
    scores = _score_sets(sets, refs, thick)
    assert all(s.valid and s.critical_ok for s in scores), [f.name for s in scores for f in s.failed_checks]
    assert all(s.geometry < 1.0 and s.dimensions < 1.0 for s in scores)  # still penalised
    assert 50 < task_quality(scores) < 100
