"""Runs in the drawing env (draftwright + build123d 0.11)."""

import json

from build123d import export_step

from cadrecover.challenges import drawing_worker
from cadrecover.challenges.families import flange, flange_spec as spec


def _draw(tmp_path, params, require, capsys, waive=None, clean=True):
    step = tmp_path / "ref.step"
    tmp_path.mkdir(parents=True, exist_ok=True)
    export_step(flange.build(params), str(step))
    args = ["draw", "--step", str(step), "--out", str(tmp_path / "out"), "--require", json.dumps(require),
            "--waive", json.dumps(spec.LEDGER_WAIVERS if waive is None else waive), "--seed", "1"]
    assert drawing_worker.main(args + (["--clean"] if clean else [])) == 0
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _seed(hub: bool) -> int:
    return next(s for s in range(1000) if spec.has_hub(spec.sample(s)) == hub)


def test_coverage_passes_for_a_plain_and_a_hubbed_flange(tmp_path, capsys):
    for hub in (False, True):
        params = spec.sample(_seed(hub))
        out = _draw(tmp_path / str(hub), params, spec.required_labels(params), capsys, clean=False)
        cov = out["coverage"]
        assert cov["ok"], cov
        assert cov["unplaced"] == [] and cov["missing_required"] == [] and cov["ledger_requirements"] > 0
        assert all(w.startswith(("holes:", "bosses:")) for w in cov["waived"])
        assert (tmp_path / str(hub) / "out" / "drawing.png").stat().st_size > 10_000


def test_the_bolt_circle_and_count_are_not_waivable(tmp_path, capsys):
    params = spec.sample(_seed(False))
    assert not any(w.startswith("hole_patterns") for w in spec.LEDGER_WAIVERS)
    out = _draw(tmp_path, params, spec.required_labels(params), capsys, waive=[])
    assert out["coverage"]["ok"] is False  # without the waivers, draftwright's centred-bore false negatives remain
    assert all(u.startswith(("holes:", "bosses:")) for u in out["coverage"]["unplaced"])


def test_coverage_rejects_a_missing_required_dimension(tmp_path, capsys):
    params = spec.sample(_seed(True))
    out = _draw(tmp_path, params, spec.required_labels(params) + ["⌀999.5"], capsys)
    assert out["coverage"]["missing_required"] == ["⌀999.5"] and out["coverage"]["ok"] is False
