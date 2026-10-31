"""Miner templates and strategies for the vacuum chamber family (services env)."""

import ast
import json

import pytest

from cadrecover.challenges.families import vacuum_chamber_spec as spec
from cadrecover.miner import strategies
from cadrecover.miner.templates import MODES, source_for, vacuum_chamber_source
from cadrecover.protocol import PublicChallenge

DRAWN = spec.sample(4)


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_renders_valid_python_with_the_entry_point(mode):
    tree = ast.parse(vacuum_chamber_source(DRAWN, mode))
    assert any(isinstance(n, ast.FunctionDef) and n.name == "build_part" for n in tree.body)


def test_templates_embed_the_drawn_values_and_modes_differ():
    honest = vacuum_chamber_source(DRAWN, "honest")
    assert repr(DRAWN["port_bolt_circle_diameter"]) in honest and "p = {**DRAWN, **overrides}" in honest
    assert "socket" in vacuum_chamber_source(DRAWN, "crash") and "socket" not in honest
    assert "1.3" in vacuum_chamber_source(DRAWN, "wrong_holes")
    assert "p = dict(DRAWN)" in vacuum_chamber_source(DRAWN, "constant")
    assert 'DRAWN["port_diameter"]' in vacuum_chamber_source(DRAWN, "proportional")


def test_source_for_dispatches_to_the_chamber():
    assert "port_reach" in source_for("vacuum_chamber", DRAWN)


def test_mock_strategies_pick_the_chamber_template(tmp_path, monkeypatch):
    from cadrecover import paths

    monkeypatch.setenv("CADRECOVER_DEV_ORACLE", "1")
    monkeypatch.setattr(paths, "PRIVATE", tmp_path)
    (tmp_path / "ch_x").mkdir()
    (tmp_path / "ch_x" / "private.json").write_text(json.dumps({"sets": [{"values": DRAWN}]}))
    ch = PublicChallenge(challenge_id="ch_x", family="vacuum_chamber", frame="f", parameters=spec.parameter_specs(DRAWN),
                         edit_rules=[], critical_features=spec.critical_feature_specs(DRAWN),
                         drawing={"path": "ch_x/drawing.png", "sha256": "0", "media_type": "image/png"})
    for name in ("mock-oracle", "mock-noisy", "diag-constant", "diag-proportional", "diag-wrong-holes"):
        sol = strategies.get(name).solve(ch, b"", "job-1")
        assert "port_reach" in sol.source and "def build_part" in sol.source, name
