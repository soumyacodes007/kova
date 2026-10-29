"""Miner templates and strategies for the flange family (services env)."""

import ast
import json

import pytest

from cadrecover.challenges.families import flange_spec as spec
from cadrecover.miner import strategies
from cadrecover.miner.templates import MODES, flange_source, source_for
from cadrecover.protocol import PublicChallenge

DRAWN = spec.sample(next(s for s in range(500) if spec.has_hub(spec.sample(s))))


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_renders_valid_python_with_the_entry_point(mode):
    tree = ast.parse(flange_source(DRAWN, mode))
    assert any(isinstance(n, ast.FunctionDef) and n.name == "build_part" for n in tree.body)


def test_templates_embed_the_drawn_values_and_modes_differ():
    honest = flange_source(DRAWN, "honest")
    assert repr(DRAWN["bolt_circle_diameter"]) in honest
    assert "socket" in flange_source(DRAWN, "crash") and "socket" not in honest
    assert "1.3" in flange_source(DRAWN, "wrong_holes")
    assert "p = dict(DRAWN)" in flange_source(DRAWN, "constant")
    assert 'DRAWN["outer_diameter"]' in flange_source(DRAWN, "proportional")


def test_source_for_dispatches_by_family():
    assert "bolt_circle_diameter" in source_for("flange", DRAWN)
    assert "slot_length" in source_for("plate", {"width": 100.0, "length": 60.0, "thickness": 8.0, "hole_diameter": 6.0})
    with pytest.raises(ValueError):
        source_for("wafer_chuck", DRAWN)


def test_mock_strategies_pick_the_flange_template(tmp_path, monkeypatch):
    from cadrecover import paths

    monkeypatch.setenv("CADRECOVER_DEV_ORACLE", "1")
    monkeypatch.setattr(paths, "PRIVATE", tmp_path)
    (tmp_path / "ch_x").mkdir()
    (tmp_path / "ch_x" / "private.json").write_text(json.dumps({"sets": [{"values": DRAWN}]}))
    ch = PublicChallenge(challenge_id="ch_x", family="flange", frame="f", parameters=spec.parameter_specs(DRAWN),
                         edit_rules=[], critical_features=spec.critical_feature_specs(DRAWN),
                         drawing={"path": "ch_x/drawing.png", "sha256": "0", "media_type": "image/png"})
    for name in ("mock-oracle", "mock-noisy", "diag-constant", "diag-proportional", "diag-wrong-holes"):
        sol = strategies.get(name).solve(ch, b"", "job-1")
        assert "bolt_circle_diameter" in sol.source and "def build_part" in sol.source, name
