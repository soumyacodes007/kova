"""PRD v2.1 self-test on real flange solids (CAD env): reference 100, one-edit-wrong 75, constant 25, wrong hole 0."""

import pytest

from cadrecover.challenges.edits import MAX_SELF_IOU, SHIFT_FACTOR, sample_edits
from cadrecover.challenges.families import flange, flange_spec as spec
from cadrecover.evaluation.checks import score_set
from cadrecover.protocol import task_quality


def _seed(hub: bool, count: int) -> int:
    return next(s for s in range(2000) if spec.has_hub(spec.sample(s)) == hub and spec.bolt_count(spec.sample(s)) == count)


@pytest.fixture(scope="module", params=[(False, 6), (True, 4), (True, 8)], ids=["plain-6", "hub-4", "hub-8"])
def task(request):
    seed = _seed(*request.param)
    base = spec.sample(seed)
    edits = sample_edits(spec, flange, base, seed)
    sets = [base] + [e["values"] for e in edits]
    refs = [flange.build(v) for v in sets]
    return sets, refs, edits


def _score_sets(sets, refs, candidates):
    return [score_set(i, v, refs[i], c, flange.expected_features(v), iou_fn=flange.iou,
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
    assert all(v["bolt_count"] == sets[0]["bolt_count"] and spec.has_hub(v) == spec.has_hub(sets[0]) for v in sets)


def test_correct_model_scores_100(task):
    sets, refs, _ = task
    assert _score(sets, refs, [flange.build(v) for v in sets]) == pytest.approx(100.0)


def test_one_edit_wrong_scores_75(task):
    sets, refs, _ = task
    cands = [flange.build(v) for v in sets]
    drift = dict(sets[2], bolt_circle_diameter=sets[2]["bolt_circle_diameter"] + 2.0)  # bolt holes drift 1 mm at s2 only
    cands[2] = flange.build(drift)
    assert _score(sets, refs, cands) == pytest.approx(75.0)


def test_constant_model_scores_25(task):
    sets, refs, _ = task
    s0 = flange.build(sets[0])
    assert _score(sets, refs, [s0, s0, s0, s0]) == pytest.approx(25.0)


def test_bolt_circle_scaling_with_the_disc_scores_25(task):
    """The "proportional" mistake: keep the drawn bolt-circle / outer-diameter ratio instead of the parameter."""
    sets, refs, _ = task
    s0 = sets[0]
    ratio = s0["bolt_circle_diameter"] / s0["outer_diameter"]
    cands = [flange.build(dict(v, bolt_circle_diameter=ratio * v["outer_diameter"])) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(25.0)


def test_wrong_hole_size_scores_0(task):
    sets, refs, _ = task
    cands = [flange.build(dict(v, bolt_hole_diameter=v["bolt_hole_diameter"] * 1.3)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_wrong_bore_size_scores_0(task):
    sets, refs, _ = task
    cands = [flange.build(dict(v, bore_diameter=v["bore_diameter"] + 1.0)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_wrong_bolt_count_scores_0(task):
    sets, refs, _ = task
    wrong = 6.0 if spec.bolt_count(sets[0]) == 4 else 4.0  # 4 and 6 holes share only the +X / -X pair
    cands = [flange.build(dict(v, bolt_count=wrong)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_misread_thickness_costs_geometry_not_critical_features(task):
    sets, refs, _ = task
    thick = [flange.build(dict(v, thickness=v["thickness"] - 1.0)) for v in sets]
    scores = _score_sets(sets, refs, thick)
    assert all(s.valid and s.critical_ok for s in scores), [f.name for s in scores for f in s.failed_checks]
    assert all(s.geometry < 1.0 and s.dimensions < 1.0 for s in scores)  # still penalised
    assert 50 < task_quality(scores) < 100
