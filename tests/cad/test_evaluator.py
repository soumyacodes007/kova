"""PRD v2.1 self-test on real solids (CAD env): reference 100, one-edit-wrong 75, constant 25, wrong hole 0."""

import pytest

from cadrecover.challenges.edits import MAX_SELF_IOU, SHIFT_FACTOR, sample_edits
from cadrecover.challenges.families import plate, plate_spec as spec
from cadrecover.evaluation.checks import score_set
from cadrecover.protocol import task_quality


def _seed(slot: bool) -> int:
    return next(s for s in range(1000) if spec.has_slot(spec.sample(s)) == slot)


@pytest.fixture(scope="module", params=[False, True], ids=["plain", "slotted"])
def task(request):
    seed = _seed(request.param)
    base = spec.sample(seed)
    edits = sample_edits(spec, plate, base, seed)
    sets = [base] + [e["values"] for e in edits]
    refs = [plate.build(v) for v in sets]
    return sets, refs, edits


def _score(sets, refs, candidates):
    return task_quality([
        score_set(i, v, refs[i], c, plate.expected_features(v), iou_fn=plate.iou,
                  size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
        for i, (v, c) in enumerate(zip(sets, candidates))
    ])


def test_edits_are_discriminative(task):
    sets, _, edits = task
    for e in edits:
        assert e["max_feature_shift_mm"] > SHIFT_FACTOR * spec.POSITION_TOL
        assert e["reference_self_iou"] < MAX_SELF_IOU
        assert e["overrides"] and set(e["overrides"]) <= set(sets[0])


def test_correct_model_scores_100(task):
    sets, refs, _ = task
    assert _score(sets, refs, [plate.build(v) for v in sets]) == pytest.approx(100.0)


def test_one_edit_wrong_scores_75(task):
    sets, refs, _ = task
    cands = [plate.build(v) for v in sets]
    drift = dict(sets[2], width=sets[2]["width"] + 2.0)  # holes drift 1 mm at s2 only
    cands[2] = plate.build(drift)
    assert _score(sets, refs, cands) == pytest.approx(75.0)


def test_constant_model_scores_25(task):
    sets, refs, _ = task
    s0 = plate.build(sets[0])
    assert _score(sets, refs, [s0, s0, s0, s0]) == pytest.approx(25.0)


def test_wrong_hole_size_scores_0(task):
    sets, refs, _ = task
    cands = [plate.build(dict(v, hole_diameter=v["hole_diameter"] * 1.3)) for v in sets]
    assert _score(sets, refs, cands) == pytest.approx(0.0)


def test_missing_solid_is_invalid(task):
    sets, refs, _ = task
    s = score_set(0, sets[0], refs[0], None, plate.expected_features(sets[0]), iou_fn=plate.iou,
                  size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
    assert not s.valid and s.q == 0
