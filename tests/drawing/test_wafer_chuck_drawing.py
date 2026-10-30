"""Runs in the drawing env (draftwright + build123d 0.11)."""

import json

from build123d import export_step

from cadrecover.challenges import drawing_worker
from cadrecover.challenges.families import wafer_chuck, wafer_chuck_spec as spec


def _draw(tmp_path, params, require, capsys, waive=None, clean=True):
    step = tmp_path / "ref.step"
    tmp_path.mkdir(parents=True, exist_ok=True)
    export_step(wafer_chuck.build(params), str(step))
    args = ["draw", "--step", str(step), "--out", str(tmp_path / "out"), "--require", json.dumps(require),
            "--waive", json.dumps(spec.LEDGER_WAIVERS if waive is None else waive), "--seed", "1"]
    assert drawing_worker.main(args + (["--clean"] if clean else [])) == 0
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _seed(ring2: bool, mount: bool) -> int:
    return next(s for s in range(1000) if spec.has_ring2(spec.sample(s)) == ring2 and spec.has_mount(spec.sample(s)) == mount)


def test_coverage_passes_for_one_and_two_rings_with_and_without_mounting_holes(tmp_path, capsys):
    for ring2, mount in [(False, True), (True, False), (True, True)]:
        params = spec.sample(_seed(ring2, mount))
        out = _draw(tmp_path / f"{ring2}{mount}", params, spec.required_labels(params), capsys, clean=False)
        cov = out["coverage"]
        assert cov["ok"], cov
        assert cov["unplaced"] == [] and cov["missing_required"] == [] and cov["ledger_requirements"] > 0
        assert all(w.startswith("bosses:") for w in cov["waived"])
        assert (tmp_path / f"{ring2}{mount}" / "out" / "drawing.png").stat().st_size > 10_000


def test_every_hole_pattern_is_dimensioned_with_its_count(tmp_path, capsys):
    params = spec.sample(_seed(True, True))
    cov = _draw(tmp_path, params, spec.required_labels(params), capsys)["coverage"]
    text = " | ".join(cov["labels"]).replace("ø", "⌀")
    for c in spec.circles(params):
        assert f"{c.count}× ⌀{params[c.hole]:g} THRU EQ SP ON ⌀{params[c.circle]:g} BC" in text, (c, cov["labels"])


def test_hole_patterns_are_not_waivable(tmp_path, capsys):
    params = spec.sample(_seed(True, False))
    assert all(w.startswith("bosses:") for w in spec.LEDGER_WAIVERS)
    out = _draw(tmp_path, params, spec.required_labels(params), capsys, waive=[])
    assert out["coverage"]["ok"] is False  # without the waiver, draftwright's disc-height false negative remains
    assert all(u.startswith("bosses:") for u in out["coverage"]["unplaced"])


def test_coverage_rejects_a_missing_required_dimension(tmp_path, capsys):
    params = spec.sample(_seed(False, True))
    out = _draw(tmp_path, params, spec.required_labels(params) + ["⌀999.5"], capsys)
    assert out["coverage"]["missing_required"] == ["⌀999.5"] and out["coverage"]["ok"] is False
