"""Scores -> weights: rolling mean, floor, outage exclusion, identity = hotkey + registration."""

from datetime import datetime, timedelta, timezone

import pytest

from cadrecover.protocol import Evaluation, SetScore
from cadrecover.storage import db
from cadrecover.validator.aggregate import standings


def _ev(job_id, hotkey, per_set_q, failure="none"):
    # build sets whose Q_s equals per_set_q (valid + critical, geometry = dimensions = q)
    sets = [SetScore(index=i, values={}, valid=q > 0, critical_ok=q > 0, geometry=q, dimensions=q)
            for i, q in enumerate(per_set_q)]
    return Evaluation(challenge_id="c", job_id=job_id, miner_hotkey=hotkey, sets=sets, failure_class=failure)


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    c.execute("INSERT INTO challenges VALUES ('c', 'plate', 'now', 'retired', '{}', 'p', NULL)")
    c.commit()
    return c


def _add(con, uid, hotkey, reg, job_id, per_set_q, label=None, failure="none"):
    # one run per job: a miner gets at most one assignment per run (UNIQUE run_id, miner_hotkey)
    db.create_run(con, f"run-{job_id}", "c", datetime.now(timezone.utc) + timedelta(minutes=3))
    db.upsert_miner(con, hotkey, reg, uid, label)
    db.add_assignment(con, job_id, f"run-{job_id}", hotkey, reg, uid)
    db.save_evaluation(con, _ev(job_id, hotkey, per_set_q, failure))


def test_floor_and_normalization(con):
    _add(con, 1, "hk1", 0, "j1", [1, 1, 1, 1])        # Q 100
    _add(con, 2, "hk2", 0, "j2", [1, 1, 1, 0])        # Q 75
    _add(con, 3, "hk3", 0, "j3", [1, 0, 0, 0])        # Q 25 (constant) -> below floor
    table = {s.uid: s for s in standings(con)}
    assert table[1].mean_quality == pytest.approx(100) and table[3].mean_quality == pytest.approx(25)
    assert table[3].weight == 0
    # (100-50) : (75-50) = 2 : 1
    assert table[1].weight == pytest.approx(2 / 3) and table[2].weight == pytest.approx(1 / 3)


def test_nobody_above_floor_means_no_weights(con):
    _add(con, 1, "hk1", 0, "j1", [1, 0, 0, 0])
    assert all(s.weight == 0 for s in standings(con))


def test_validator_outage_is_excluded_not_zeroed(con):
    _add(con, 1, "hk1", 0, "j1", [1, 1, 1, 1])
    _add(con, 1, "hk1", 0, "j2", [0, 0, 0, 0], failure="validator_outage")
    (s,) = standings(con)
    assert s.samples == 1 and s.mean_quality == pytest.approx(100)


def test_recycled_uid_starts_fresh(con):
    _add(con, 7, "old_hotkey", 100, "j1", [1, 1, 1, 1])
    _add(con, 7, "new_hotkey", 900, "j2", [1, 0, 0, 0])
    table = {(s.hotkey, s.registered_at_block): s for s in standings(con)}
    assert table[("new_hotkey", 900)].mean_quality == pytest.approx(25)  # no inherited history
    assert table[("old_hotkey", 100)].mean_quality == pytest.approx(100)
