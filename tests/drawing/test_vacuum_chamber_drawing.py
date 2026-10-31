"""Runs in the drawing env (draftwright + build123d 0.11). A chamber drawing takes about two minutes, so only two are made."""

import json

import pytest
from build123d import export_step

from cadrecover.challenges import drawing_worker
from cadrecover.challenges.families import vacuum_chamber, vacuum_chamber_spec as spec


def _draw(tmp_path, params, require, capsys, waive=None, clean=True):
    step = tmp_path / "ref.step"
    tmp_path.mkdir(parents=True, exist_ok=True)
    export_step(vacuum_chamber.build(params), str(step))
    args = ["draw", "--step", str(step), "--out", str(tmp_path / "out"), "--require", json.dumps(require),
            "--waive", json.dumps(spec.LEDGER_WAIVERS if waive is None else waive), "--seed", "1"]
    assert drawing_worker.main(args + (["--clean"] if clean else [])) == 0
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _seed(ports: int) -> int:
    return next(s for s in range(1000) if spec.port_count(spec.sample(s)) == ports)


def test_coverage_passes_for_a_five_port_chamber_and_rejects_a_missing_dimension(tmp_path, capsys):
    params = spec.sample(_seed(5))
    out = _draw(tmp_path, params, spec.required_labels(params) + ["⌀999.5"], capsys, clean=False)
    cov = out["coverage"]
    # every real required value is drawn and every ledger entry is placed or waived: only the invented one is missing
    assert cov["missing_required"] == ["⌀999.5"] and cov["unplaced"] == [] and cov["ok"] is False
    assert cov["ledger_requirements"] > 0 and cov["waived"]
    assert all(w.startswith(("holes:", "bosses:", "hole_patterns:")) for w in cov["waived"])
    assert (tmp_path / "out" / "drawing.png").stat().st_size > 10_000


def test_the_waivers_hide_only_ledger_false_negatives_not_the_dimension_labels(tmp_path, capsys):
    params = spec.sample(_seed(4))
    out = _draw(tmp_path, params, spec.required_labels(params), capsys, waive=[])
    assert out["coverage"]["ok"] is False  # without the waivers draftwright's radial-feature false negatives remain
    assert all(u.startswith(("holes:", "bosses:", "hole_patterns:")) for u in out["coverage"]["unplaced"])
    assert out["coverage"]["missing_required"] == []  # ... but every required value is drawn
