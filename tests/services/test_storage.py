from pathlib import Path

from cadrecover.protocol import Artifact, ParameterSpec, PublicChallenge
from cadrecover.storage import db


def test_schema_wal_and_challenge_round_trip(tmp_path: Path):
    con = db.connect(tmp_path / "t.sqlite")
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for t in ("challenges", "miners", "runs", "assignments", "submissions", "evaluations", "evaluation_sets",
              "events", "weight_batches", "receipts", "commitments", "audits"):
        assert t in tables, t

    pub = PublicChallenge(
        challenge_id="ch_x", family="plate", frame="f",
        parameters=[ParameterSpec(name="width", description="X", min=1, max=2)],
        edit_rules=[], critical_features=[],
        drawing=Artifact(path="ch_x/drawing.png", sha256="0" * 64, media_type="image/png"),
    )
    db.save_challenge(con, pub, tmp_path / "private.json")
    assert db.get_public_challenge(con, "ch_x") == pub
    kinds = [r["kind"] for r in con.execute("SELECT kind FROM events ORDER BY event_id")]
    assert kinds == ["challenge.created"]


def test_reconnect_is_idempotent(tmp_path: Path):
    db.connect(tmp_path / "t.sqlite").close()
    con = db.connect(tmp_path / "t.sqlite")
    assert con.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 1
