import hashlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from cadrecover.protocol import (
    Artifact,
    CriticalFeatureSpec,
    Evaluation,
    JobRequest,
    JobResult,
    ParameterSpec,
    PublicChallenge,
    SetScore,
    task_quality,
)


def _set(i, valid=True, critical=True, g=1.0, d=1.0):
    return SetScore(index=i, values={"width": 100.0 + i}, valid=valid, critical_ok=critical, geometry=g, dimensions=d)


# PRD v2.1 worked table: these four numbers are the contract.
@pytest.mark.parametrize(
    "sets, expected",
    [
        ([_set(i) for i in range(4)], 100.0),  # correct parametric model
        ([_set(0), _set(1), _set(2, critical=False, g=0.97, d=0.9), _set(3)], 75.0),  # one edit wrong
        ([_set(0)] + [_set(i, critical=False, g=0.8, d=0.5) for i in (1, 2, 3)], 25.0),  # constant model
        ([_set(i, critical=False, g=0.99, d=0.8) for i in range(4)], 0.0),  # wrong hole size everywhere
    ],
)
def test_worked_score_table(sets, expected):
    assert task_quality(sets) == pytest.approx(expected)


def test_invalid_build_zeroes_a_set_even_with_perfect_overlap():
    sets = [_set(0), _set(1, valid=False), _set(2), _set(3)]
    assert task_quality(sets) == pytest.approx(75.0)


def test_task_needs_exactly_four_sets():
    with pytest.raises(ValueError):
        task_quality([_set(0)])
    with pytest.raises(ValidationError):
        Evaluation(challenge_id="c", job_id="j", miner_hotkey="h", sets=[_set(0)])


def test_validator_outage_has_no_score():
    ev = Evaluation(challenge_id="c", job_id="j", miner_hotkey="h", sets=[_set(i) for i in range(4)],
                    failure_class="validator_outage")
    with pytest.raises(ValueError):
        _ = ev.quality


def _public():
    return PublicChallenge(
        challenge_id="ch_test", family="plate", frame="origin at plate centre, Z up, top face at Z = thickness",
        parameters=[ParameterSpec(name="width", description="overall X size", min=60, max=200)],
        edit_rules=["holes keep a 10 mm offset from the nearest edges"],
        critical_features=[CriticalFeatureSpec(name="hole_1", kind="hole", description="corner hole",
                                               size_tolerance_mm=0.1, position_tolerance_mm=0.1)],
        drawing=Artifact(path="ch_test/drawing.png", sha256="0" * 64, media_type="image/png"),
    )


def test_public_challenge_round_trips_and_has_no_shown_values():
    pub = _public()
    again = PublicChallenge.model_validate_json(pub.model_dump_json())
    assert again == pub
    assert "seed" not in pub.model_dump() and "sets" not in pub.model_dump()


def test_job_result_hash_must_match_source():
    src = "def build_part(params):\n    ...\n"
    ok = JobResult.for_source(job_id="j1", challenge_id="c1", source=src)
    assert ok.source_sha256 == hashlib.sha256(src.encode()).hexdigest()
    with pytest.raises(ValidationError):
        JobResult(job_id="j1", challenge_id="c1", source=src, source_sha256="f" * 64)


def test_job_request_round_trips():
    req = JobRequest(job_id="j1", challenge=_public(), drawing_url="http://127.0.0.1:8080/ch_test/drawing.png",
                     deadline_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
    assert JobRequest.model_validate_json(req.model_dump_json()) == req
