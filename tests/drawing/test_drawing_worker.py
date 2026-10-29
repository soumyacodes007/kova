"""Runs in the drawing env (draftwright + build123d 0.11)."""

import json

from build123d import export_step

from cadrecover.challenges import drawing_worker
from cadrecover.challenges.families import plate, plate_spec as spec


def _draw(tmp_path, params, require, capsys, clean=True):
    step = tmp_path / "ref.step"
    export_step(plate.build(params), str(step))
    args = ["draw", "--step", str(step), "--out", str(tmp_path / "out"), "--require", json.dumps(require), "--seed", "1"]
    assert drawing_worker.main(args + (["--clean"] if clean else [])) == 0
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_coverage_passes_for_a_slotted_plate(tmp_path, capsys):
    params = spec.sample(next(s for s in range(1000) if spec.has_slot(spec.sample(s))))
    out = _draw(tmp_path, params, spec.required_labels(params), capsys, clean=False)
    assert out["coverage"]["ok"], out["coverage"]
    assert out["coverage"]["unplaced"] == [] and out["coverage"]["ledger_requirements"] > 0
    assert out["lint"]["passed"] is True
    assert (tmp_path / "out" / "drawing.png").stat().st_size > 10_000


def test_coverage_rejects_a_missing_required_dimension(tmp_path, capsys):
    params = spec.sample(next(s for s in range(1000) if not spec.has_slot(spec.sample(s))))
    out = _draw(tmp_path, params, spec.required_labels(params) + ["999.5"], capsys)
    assert out["coverage"]["ok"] is False
    assert out["coverage"]["missing_required"] == ["999.5"]
