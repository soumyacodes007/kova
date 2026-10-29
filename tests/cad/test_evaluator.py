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


def test_misread_thickness_costs_geometry_not_critical_features(task):
    """Regression: a 1 mm thickness misread moved the measured hole centres in Z and zeroed whole sets."""
    sets, refs, _ = task
    thick = [plate.build(dict(v, thickness=v["thickness"] - 1.0)) for v in sets]
    scores = [score_set(i, v, refs[i], c, plate.expected_features(v), iou_fn=plate.iou,
                        size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
              for i, (v, c) in enumerate(zip(sets, thick))]
    assert all(s.valid and s.critical_ok for s in scores), [f.name for s in scores for f in s.failed_checks]
    assert all(s.geometry < 0.95 and s.dimensions < 1.0 for s in scores)  # still penalised
    assert 50 < task_quality(scores) < 100


def test_missing_solid_is_invalid(task):
    sets, refs, _ = task
    s = score_set(0, sets[0], refs[0], None, plate.expected_features(sets[0]), iou_fn=plate.iou,
                  size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)
    assert not s.valid and s.q == 0


# --- verification checklist: each bad model fails the right check (PRD §Verification) ---

def _set0(sets, refs, cand):
    v = sets[0]
    return score_set(0, v, refs[0], cand, plate.expected_features(v), iou_fn=plate.iou,
                     size_tol=spec.SIZE_TOL, pos_tol=spec.POSITION_TOL)


def _plug(part, v, name):
    from build123d import Cylinder, Pos

    x, y = spec.hole_centers(v)[name]
    return part + Pos(x, y, v["thickness"] / 2) * Cylinder(v["hole_diameter"] / 2 + 0.01, v["thickness"])


def _drill(part, v, x, y):
    from build123d import Cylinder, Pos

    return part - Pos(x, y, v["thickness"] / 2) * Cylinder(v["hole_diameter"] / 2, 3 * v["thickness"])


def _failed(s):
    return {f.name for f in s.failed_checks}


def test_missing_hole_fails_critical(task):
    sets, refs, _ = task
    s = _set0(sets, refs, _plug(plate.build(sets[0]), sets[0], "hole_1"))
    assert s.valid and not s.critical_ok and s.q == 0
    assert _failed(s) & {"hole_1.missing", "hole_1.position"}


def test_moved_hole_fails_critical(task):
    sets, refs, _ = task
    v = sets[0]
    x, y = spec.hole_centers(v)["hole_1"]
    cand = _drill(_plug(plate.build(v), v, "hole_1"), v, x + 1.0, y)  # 1 mm = 10x tolerance
    s = _set0(sets, refs, cand)
    assert not s.critical_ok and s.q == 0 and "hole_1.position" in _failed(s)


def test_extra_hole_fails_critical(task):
    """A superset of holes (e.g. guessing every pattern at once) must not pass the critical check."""
    sets, refs, _ = task
    v = sets[0]
    x, y = spec.hole_centers(v)["hole_1"]
    s = _set0(sets, refs, _drill(plate.build(v), v, x, 0.0 if not spec.has_slot(v) else y / 2))
    assert not s.critical_ok and s.q == 0 and "extra_hole" in _failed(s)


def test_wrong_units_fails(task):
    """A model drawn in inches (every length / 25.4) fails holes and dimensions."""
    sets, refs, _ = task
    inch = {k: (val / 25.4 if isinstance(val, float) else val) for k, val in sets[0].items()}
    try:
        cand = plate.build(inch)
    except Exception:  # noqa: BLE001 - an unbuildable inch model is also a fail (invalid)
        cand = None
    s = _set0(sets, refs, cand)
    assert s.q == 0


def test_mirrored_part_of_a_symmetric_family_is_the_same_part(task):
    """Plate (and flange) are mirror-symmetric, so a mirrored model is geometrically identical and must
    score like the reference: the check is that mirroring is not falsely penalised. Handedness only
    matters for asymmetric families (none shipped yet)."""
    from build123d import Plane

    sets, refs, _ = task
    s = _set0(sets, refs, plate.build(sets[0]).mirror(Plane.YZ))
    assert s.valid and s.critical_ok and s.q == pytest.approx(1.0, abs=1e-3)
