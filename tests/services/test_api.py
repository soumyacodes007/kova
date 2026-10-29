"""The read API: shapes, honesty (no invented data, no ground truth), files, and resumable SSE."""

import asyncio
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cadrecover.api import events as api_events
from cadrecover.api.app import create_app
from cadrecover.api.db_access import connect_ro
from cadrecover.protocol import (
    Artifact,
    CriticalFeatureSpec,
    Evaluation,
    FailedCheck,
    ParameterSpec,
    PublicChallenge,
    SetScore,
    WeightBatch,
)
from cadrecover.storage import db

REPO = Path(__file__).resolve().parents[2]
SECRET = "SECRET_SEED_9137"
HK = {1: "5HotkeyOneAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 2: "5HotkeyTwoBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
      3: "5HotkeyThreeCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"}
DIGEST = "sha256:" + "ab" * 32


def _public(cid: str) -> PublicChallenge:
    return PublicChallenge(
        challenge_id=cid, family="plate", frame="origin at the centre of the bottom face",
        parameters=[ParameterSpec(name="width", description="X size", min=80, max=200)],
        edit_rules=["holes stay 10 mm from the edges"],
        critical_features=[CriticalFeatureSpec(name="hole_1", kind="hole", description="through-hole",
                                               size_tolerance_mm=0.1, position_tolerance_mm=0.1)],
        drawing=Artifact(path=f"{cid}/drawing.png", sha256="0" * 64, media_type="image/png"))


def _ev(job_id, hotkey, cid, per_set, failure="none"):
    sets = []
    for i, q in enumerate(per_set):
        checks = [] if q > 0 else [FailedCheck(name="hole_1.position", message="hole centre off by 14.750 mm (tolerance 0.1)",
                                               location=(1.0, 2.0, 3.0))]
        sets.append(SetScore(index=i, values={"width": 100.0 + 10 * i}, valid=True, critical_ok=q > 0,
                             geometry=q, dimensions=q, failed_checks=checks))
    return Evaluation(challenge_id=cid, job_id=job_id, miner_hotkey=hotkey, sets=sets, failure_class=failure)


def _round(con, run_id, cid, miners, *, retire):
    """miners: {uid: per_set_q list}. One run; every miner evaluated."""
    db.save_challenge(con, _public(cid), Path("/nonexistent/private") / cid / "private.json")
    db.create_run(con, run_id, cid, datetime.now(timezone.utc) + timedelta(minutes=3))
    db.add_event(con, "run.started", {"challenge_id": cid, "miners": len(miners)}, run_id)
    for uid, qs in miners.items():
        db.upsert_miner(con, HK[uid], 100 + uid, uid, f"label-{uid}")
        job = f"{run_id}-uid{uid}"
        db.add_assignment(con, job, run_id, HK[uid], 100 + uid, uid)
        db.set_assignment(con, job, "done")
        env = {"source_sha256": "f" * 64, "model_id": "mock", "strategy_version": "mock/0.1", "duration_s": 1.5}
        db.save_submission(con, job, json.dumps(env), "f" * 64)
        db.save_evaluation(con, _ev(job, HK[uid], cid, qs))
        db.add_event(con, "job.evaluated", {"uid": uid, "job_id": job}, run_id)
    db.set_run_status(con, run_id, "done")
    if retire:
        db.retire_challenge(con, cid, "round finished")


@pytest.fixture
def world(tmp_path):
    """A DB with one finished (retired) round and one in-flight (active) round, plus files on disk."""
    con = db.connect(tmp_path / "t.sqlite")
    _round(con, "run_done", "ch_done", {1: [1, 1, 1, 1], 2: [1, 0, 0, 0], 3: [0, 0, 0, 0]}, retire=True)
    _round(con, "run_live", "ch_live", {1: [1, 1, 1, 1]}, retire=False)

    batch = WeightBatch(batch_id="wb_1", network="local", netuid=2, validator_hotkey="5Validator", floor=50.0,
                        mean_quality={HK[1]: 100.0, HK[2]: 25.0, HK[3]: 0.0}, samples={HK[1]: 2, HK[2]: 1, HK[3]: 1},
                        weights={1: 1.0})
    db.save_weight_batch(con, batch, "proposed")
    db.add_event(con, "weights.proposed", {"batch_id": "wb_1", "weights": {"1": 1.0}}, "run_done")
    db.add_receipt(con, "wb_1", "submitted", block=500, extrinsic="500-2")
    db.add_receipt(con, "wb_1", "committed", block=501, extrinsic="500-2")
    db.add_receipt(con, "wb_1", "revealed", block=520, readback={1: 1.0})
    db.save_commitment(con, HK[1], 101, DIGEST, "mock/0.1", 400)
    db.save_commitment(con, HK[1], 101, "sha256:" + "cd" * 32, "mock/0.2", 450)
    db.save_audit(con, "audit_x-0", HK[1], DIGEST, "ch_a0", 100.0, True, 600,
                  {"audit_run": "audit_x", "live_mean": 100.0, "audit_mean": 100.0, "margin": 10.0, "verdict": "pass",
                   "reason": None, "task_index": 0, "error": None, "commitment": {"e": DIGEST, "s": "mock/0.1", "block": 400}})
    db.save_audit(con, "audit_x-1", HK[1], DIGEST, "ch_a1", 100.0, True, 600,
                  {"audit_run": "audit_x", "live_mean": 100.0, "audit_mean": 100.0, "margin": 10.0, "verdict": "pass",
                   "reason": None, "task_index": 1, "error": None})
    con.close()

    public = tmp_path / "public"
    (public / "ch_done").mkdir(parents=True)
    (public / "ch_done" / "drawing.png").write_bytes(b"\x89PNG\r\n\x1a\n-drawing")
    (public / "ch_live").mkdir()
    (public / "ch_live" / "drawing.png").write_bytes(b"\x89PNG\r\n\x1a\n-live")
    runs = tmp_path / "runs"
    for run in ("run_done", "run_live"):
        for uid in (1, 2, 3):
            d = runs / run / f"uid{uid}"
            d.mkdir(parents=True)
            for s in (0, 1):
                (d / f"s{s}.candidate.glb").write_bytes(b"glTF-candidate")
                (d / f"s{s}.reference.glb").write_bytes(b"glTF-reference")
    # ground truth that must never be reachable
    private = tmp_path / "private" / "ch_done"
    private.mkdir(parents=True)
    (private / "private.json").write_text(json.dumps({"seed": 5550123, "marker": SECRET}))
    (tmp_path / "secret.txt").write_text(SECRET)
    return tmp_path


@pytest.fixture
def client(world):
    app = create_app(world / "t.sqlite", public_dir=world / "public", runs_dir=world / "runs", chain_rpc=None,
                     state_file=world / "no-chain.json", sse_poll_s=0.01, sse_keepalive_s=0.05)
    with TestClient(app) as c:
        yield c


GET_ENDPOINTS = ["/v1/health", "/v1/status", "/v1/runs", "/v1/runs/run_done", "/v1/runs/run_live", "/v1/leaderboard",
                 f"/v1/miners/{HK[1]}", "/v1/weights", "/v1/commitments", "/v1/audits", "/v1/challenges/ch_done",
                 "/v1/challenges/ch_live", "/v1/events"]


# ------------------------------------------------------------------ honesty: empty means empty


def test_empty_database_returns_empty_not_invented(tmp_path):
    app = create_app(tmp_path / "e.sqlite", public_dir=tmp_path, runs_dir=tmp_path, chain_rpc=None,
                     state_file=tmp_path / "none.json")
    c = TestClient(app)
    for path in ("/v1/runs", "/v1/weights", "/v1/commitments", "/v1/audits"):
        assert c.get(path).json() == [], path
    assert c.get("/v1/events").json() == {"events": [], "next_after": 0, "latest_event_id": 0}
    lb = c.get("/v1/leaderboard").json()
    assert lb["rows"] == [] and lb["latest_batch_id"] is None
    st = c.get("/v1/status").json()
    assert st["latest_run"] is None and st["chain"]["block"] is None and st["chain"]["reachable"] is False
    assert all(v == 0 for v in st["counts"].values()) and st["latest_event_id"] == 0
    for path in ("/v1/runs/nope", f"/v1/miners/{HK[1]}", "/v1/challenges/nope"):
        assert c.get(path).status_code == 404, path


def test_status_shape(client):
    st = client.get("/v1/status").json()
    assert st["protocol_version"] and st["scoring_version"] == "2.1" and st["quality_floor"] == 50.0
    assert st["cad_engine"] == {"build123d": "0.13.0"}
    assert st["counts"]["runs"] == 2 and st["counts"]["active_challenges"] == 1 and st["counts"]["weight_batches"] == 1
    assert st["counts"]["receipts"] == 4 and st["counts"]["commitments"] == 2 and st["counts"]["audits"] == 2
    assert st["latest_run"]["run_id"] == "run_live" and st["latest_event_id"] == st["counts"]["events"]
    assert st["chain"]["block"] is None


# ------------------------------------------------------------------ runs


def test_runs_list_and_filter(client):
    runs = client.get("/v1/runs").json()
    assert [r["run_id"] for r in runs] == ["run_live", "run_done"]
    done = runs[1]
    assert done["miners"] == 3 and done["evaluated"] == 3 and done["family"] == "plate"
    assert done["mean_quality"] == pytest.approx((100 + 25 + 0) / 3) and done["best_quality"] == 100 and done["best_uid"] == 1
    assert client.get("/v1/runs?status=aborted").json() == []
    assert client.get("/v1/runs?limit=1").json()[0]["run_id"] == "run_live"
    assert client.get("/v1/runs?status=bogus").status_code == 422


def test_retired_run_reveals_per_set_scores_values_and_checks(client):
    d = client.get("/v1/runs/run_done").json()
    assert d["challenge"]["status"] == "retired" and d["challenge"]["drawing_url"] == "/v1/challenges/ch_done/drawing.png"
    r2 = next(r for r in d["results"] if r["uid"] == 2)
    assert r2["quality"] == 25.0 and r2["hotkey"] == HK[2] and r2["label"] == "label-2" and r2["evaluated"]
    assert r2["strategy_version"] == "mock/0.1" and r2["source_sha256"] == "f" * 64
    s0, s1 = r2["sets"][0], r2["sets"][1]
    assert (s0["valid"], s0["critical_ok"], s0["geometry"], s0["dimensions"], s0["q_s"]) == (True, True, 1.0, 1.0, 1.0)
    assert s0["passed"] and s0["revealed"] and s0["values"] == {"width": 100.0}
    assert not s1["passed"] and s1["q_s"] == 0 and s1["failed_check_count"] == 1
    assert s1["failed_checks"][0]["name"] == "hole_1.position" and s1["failed_checks"][0]["location"] == [1.0, 2.0, 3.0]
    kinds = {(m["set_index"], m["kind"]) for m in r2["models"]}
    assert kinds == {(0, "candidate"), (0, "reference"), (1, "candidate"), (1, "reference")}


def test_active_run_withholds_ground_truth(client):
    d = client.get("/v1/runs/run_live").json()
    assert d["challenge"]["status"] == "active"
    (r,) = d["results"]
    assert r["quality"] == 100.0  # the score is public
    for s in r["sets"]:
        assert s["values"] is None and s["revealed"] is False and s["failed_checks"] == []
    assert {(m["kind"]) for m in r["models"]} == {"candidate"}  # references stay private


def test_active_run_failed_checks_hidden_but_counted(world):
    con = db.connect(world / "t.sqlite")
    db.upsert_miner(con, HK[2], 102, 2, "label-2")
    db.add_assignment(con, "run_live-uid2", "run_live", HK[2], 102, 2)
    db.save_evaluation(con, _ev("run_live-uid2", HK[2], "ch_live", [1, 0, 0, 0]))
    con.close()
    c = TestClient(create_app(world / "t.sqlite", public_dir=world / "public", runs_dir=world / "runs", chain_rpc=None,
                              state_file=world / "none.json"))
    r2 = next(r for r in c.get("/v1/runs/run_live").json()["results"] if r["uid"] == 2)
    assert r2["sets"][1]["failed_check_count"] == 1 and r2["sets"][1]["failed_checks"] == []
    assert "14.750" not in json.dumps(c.get("/v1/runs/run_live").json())


# ------------------------------------------------------------------ leaderboard and miners


def test_leaderboard_standings_and_pass_rates(client):
    lb = client.get("/v1/leaderboard").json()
    rows = {r["uid"]: r for r in lb["rows"]}
    assert [r["uid"] for r in lb["rows"]] == [1, 2, 3] and [r["rank"] for r in lb["rows"]] == [1, 2, 3]
    assert lb["quality_floor"] == 50.0 and lb["latest_batch_id"] == "wb_1"
    assert rows[1]["mean_quality"] == 100 and rows[1]["samples"] == 2 and rows[1]["weight"] == pytest.approx(1.0)
    assert rows[2]["mean_quality"] == 25 and rows[2]["weight"] == 0 and rows[3]["mean_quality"] == 0
    assert rows[1]["latest_batch_weight"] == 1.0 and rows[2]["latest_batch_weight"] == 0.0
    assert rows[1]["drawing_pass_rate"] == 1.0 and rows[1]["edit_pass_rate"] == 1.0
    assert rows[2]["drawing_pass_rate"] == 1.0 and rows[2]["edit_pass_rate"] == 0.0  # constant model
    assert rows[3]["drawing_pass_rate"] == 0.0
    assert rows[1]["committed_engine"] == "sha256:" + "cd" * 32  # the newest commitment
    assert rows[1]["audit"]["verdict"] == "pass" and rows[1]["audit"]["block"] == 600 and rows[2]["audit"] is None


def test_failed_audit_zeroes_weight_in_standings(world):
    con = db.connect(world / "t.sqlite")
    db.save_audit(con, "audit_y-0", HK[1], DIGEST, "ch_a2", 25.0, False, 700,
                  {"audit_run": "audit_y", "live_mean": 100.0, "audit_mean": 25.0, "margin": 10.0, "verdict": "fail",
                   "reason": "audit mean 25.0 < live 100.0 - 10", "task_index": 0, "error": None})
    con.close()
    c = TestClient(create_app(world / "t.sqlite", public_dir=world / "public", runs_dir=world / "runs", chain_rpc=None,
                              state_file=world / "none.json"))
    row = next(r for r in c.get("/v1/leaderboard").json()["rows"] if r["uid"] == 1)
    assert row["weight"] == 0 and row["audit"]["verdict"] == "fail" and row["audit"]["audit_mean"] == 25.0
    audits = c.get("/v1/audits").json()
    assert audits[0]["audit_run"] == "audit_y" and audits[0]["verdict"] == "fail"  # newest first


def test_miner_history(client):
    m = client.get(f"/v1/miners/{HK[2]}").json()
    assert m["identities"][0]["uid"] == 2 and m["identities"][0]["registered_at_block"] == 102
    assert m["standing"]["mean_quality"] == 25
    assert len(m["history"]) == 1 and m["history"][0]["set_q"] == [1.0, 0.0, 0.0, 0.0]
    assert m["history"][0]["run_id"] == "run_done" and m["batches"][0]["batch_id"] == "wb_1"
    assert m["batches"][0]["latest_state"] == "revealed"
    one = client.get(f"/v1/miners/{HK[1]}").json()
    assert len(one["commitments"]) == 2 and one["audits"][0]["audit_run"] == "audit_x"
    assert client.get("/v1/miners/5Unknown").status_code == 404
    assert client.get("/v1/miners/bad%20key").status_code == 404


# ------------------------------------------------------------------ chain records


def test_weights_never_collapse_commit_and_reveal(client):
    (b,) = client.get("/v1/weights").json()
    assert b["batch_id"] == "wb_1" and b["run_id"] == "run_done" and b["network"] == "local" and b["netuid"] == 2
    assert [r["state"] for r in b["receipts"]] == ["proposed", "submitted", "committed", "revealed"]
    by = {r["state"]: r for r in b["receipts"]}
    assert by["submitted"]["block"] == 500 and by["committed"]["block"] == 501 and by["revealed"]["block"] == 520
    assert by["revealed"]["readback"] == {"1": 1.0} and by["proposed"]["readback"] is None
    assert b["latest_state"] == "revealed" and b["weights"] == {"1": 1.0}
    assert b["mean_quality"][HK[1]] == 100.0 and b["samples"][HK[2]] == 1


def test_commitments_and_audits(client):
    cs = client.get("/v1/commitments").json()
    assert [(c["block"], c["latest"]) for c in cs] == [(450, True), (400, False)]
    assert cs[0]["uid"] == 1 and cs[0]["label"] == "label-1" and cs[0]["strategy_version"] == "mock/0.2"
    (a,) = client.get("/v1/audits").json()
    assert a["verdict"] == "pass" and a["live_mean"] == 100 and a["audit_mean"] == 100 and a["block"] == 600
    assert [t["task_index"] for t in a["tasks"]] == [0, 1] and a["commitment"]["e"] == DIGEST
    assert client.get(f"/v1/audits?hotkey={HK[2]}").json() == []


# ------------------------------------------------------------------ ground truth never leaks


def test_challenge_is_public_record_only(client):
    ch = client.get("/v1/challenges/ch_done").json()
    assert ch["challenge_id"] == "ch_done" and ch["status"] == "retired"
    assert {"parameters", "critical_features", "drawing", "edit_rules"} <= set(ch)
    assert not ({"seed", "sets", "private_path", "reference", "measurements"} & set(ch))
    assert all("value" not in p for p in ch["parameters"])  # ranges, never values
    assert ch["drawing"]["path"] == "ch_done/drawing.png"


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_no_private_data_in_any_response(client, world, path):
    body = client.get(path).text
    for needle in (SECRET, "private_path", "private.json", str(world / "private"), "/nonexistent/private", "5550123"):
        assert needle not in body, (path, needle)


def test_every_event_and_stream_is_free_of_private_paths(client, world):
    text = client.get("/v1/events?limit=1000").text
    n = len(client.get("/v1/events?run_id=run_done").json()["events"])
    with client.stream("GET", f"/v1/events/stream?after=0&limit={n}&run_id=run_done") as r:
        text += "".join(r.iter_text())
    assert "private" not in text.lower() and SECRET not in text


# ------------------------------------------------------------------ files and path traversal


def test_drawing_and_models_are_served(client):
    r = client.get("/v1/challenges/ch_done/drawing.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
    r = client.get("/v1/runs/run_done/miners/2/models/s1.candidate.glb")
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary" and r.content == b"glTF-candidate"
    assert client.get("/v1/runs/run_done/miners/2/models/s1.reference.glb").content == b"glTF-reference"


def test_reference_models_are_withheld_until_retirement(client):
    assert client.get("/v1/runs/run_live/miners/1/models/s0.candidate.glb").status_code == 200
    assert client.get("/v1/runs/run_live/miners/1/models/s0.reference.glb").status_code == 404
    assert client.get("/v1/runs/run_live/miners/3/models/s0.candidate.glb").status_code == 404  # never evaluated


@pytest.mark.parametrize("path", [
    "/v1/challenges/..%2fprivate%2fch_done/drawing.png",
    "/v1/challenges/%2e%2e/drawing.png",
    "/v1/challenges/ch_done%2f..%2f..%2fsecret.txt",
    "/v1/challenges/ch_done/..%2f..%2fsecret.txt",
    "/v1/challenges/ch_done/drawing.png/../../secret.txt",
    "/v1/runs/run_done/miners/2/models/..%2f..%2f..%2fsecret.txt",
    "/v1/runs/run_done/miners/2/models/..%2f..%2fuid1%2fs0.candidate.glb",
    "/v1/runs/run_done/miners/2/models/s0.candidate.glb%00.png",
    "/v1/runs/..%2f..%2fprivate/miners/2/models/s0.candidate.glb",
    "/v1/runs/run_done/miners/2/models/s9.candidate.glb",
    "/v1/runs/run_done/miners/2/models/private.json",
    "/v1/runs/run_done/miners/2/models/s0.candidate.glb.bak",
    "//etc/passwd",
])
def test_path_traversal_is_blocked(client, path):
    r = client.get(path)
    assert r.status_code in (400, 404, 422), (path, r.status_code)
    assert SECRET not in r.text and "root:" not in r.text


def test_symlink_escape_is_blocked(world):
    link = world / "public" / "ch_done" / "drawing.png"
    link.unlink()
    link.symlink_to(world / "secret.txt")
    c = TestClient(create_app(world / "t.sqlite", public_dir=world / "public", runs_dir=world / "runs", chain_rpc=None,
                              state_file=world / "none.json"))
    r = c.get("/v1/challenges/ch_done/drawing.png")
    assert r.status_code == 404 and SECRET not in r.text


# ------------------------------------------------------------------ read-only and CORS


def test_api_is_read_only(client):
    for route in client.app.routes:
        assert set(getattr(route, "methods", None) or ()) <= {"GET", "HEAD"}, route.path
    assert client.post("/v1/runs", json={}).status_code == 405
    assert client.delete("/v1/runs/run_done").status_code == 405


def test_cors_allows_only_localhost_3000(client):
    ok = client.options("/v1/status", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                                               "Access-Control-Request-Headers": "last-event-id"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "last-event-id" in ok.headers["access-control-allow-headers"].lower()
    bad = client.options("/v1/status", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
    plain = client.get("/v1/status", headers={"Origin": "http://localhost:3000"})
    assert plain.headers["access-control-allow-origin"] == "http://localhost:3000"


# ------------------------------------------------------------------ events and SSE


def _frames(text: str) -> list[dict]:
    """Parse SSE text into [{id, data}] (comments and retry lines skipped)."""
    out = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "id" in fields:
            out.append({"id": int(fields["id"]), "data": json.loads(fields["data"])})
    return out


def _stream(client, url, headers=None) -> str:
    with client.stream("GET", url, headers=headers or {}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        assert "no-cache" in r.headers["cache-control"]
        return "".join(r.iter_text())


def test_events_list_pagination_and_filters(client):
    page = client.get("/v1/events?limit=3").json()
    assert [e["event_id"] for e in page["events"]] == [1, 2, 3] and page["next_after"] == 3
    rest = client.get(f"/v1/events?after={page['next_after']}&limit=1000").json()
    assert rest["events"][0]["event_id"] == 4 and rest["next_after"] == rest["latest_event_id"]
    assert client.get(f"/v1/events?after={rest['latest_event_id']}").json()["next_after"] == rest["latest_event_id"]
    only = client.get("/v1/events?run_id=run_live").json()["events"]
    assert only and all(e["run_id"] == "run_live" for e in only)
    weights = client.get("/v1/events?kind=weights").json()["events"]
    assert [e["kind"] for e in weights] == ["weights.proposed"] and weights[0]["payload"]["batch_id"] == "wb_1"
    assert client.get("/v1/events?kind=weight").json()["events"] == []  # prefix means a dotted prefix, not a substring
    assert client.get("/v1/events?kind=job.evaluated").json()["events"]


def test_sse_replays_from_after_zero_with_ids(client):
    text = _stream(client, "/v1/events/stream?after=0&limit=5")
    assert text.startswith("retry: ")
    frames = _frames(text)
    assert [f["id"] for f in frames] == [1, 2, 3, 4, 5]
    assert all(f["data"]["event_id"] == f["id"] for f in frames) and frames[0]["data"]["kind"] == "challenge.created"
    assert re.search(r"^id: 1\ndata: \{", text, re.M)


def test_sse_resumes_from_last_event_id_with_only_newer_events(client):
    total = client.get("/v1/status").json()["latest_event_id"]
    first = _frames(_stream(client, "/v1/events/stream?after=0&limit=4"))
    last_seen = first[-1]["id"]
    resumed = _frames(_stream(client, "/v1/events/stream?limit=3", headers={"Last-Event-ID": str(last_seen)}))
    assert [f["id"] for f in resumed] == [last_seen + 1, last_seen + 2, last_seen + 3]
    # the union of both connections is exactly the log, with no gaps and no repeats
    tail = _frames(_stream(client, f"/v1/events/stream?limit={total - last_seen}", headers={"Last-Event-ID": str(last_seen)}))
    assert [f["id"] for f in first + tail] == list(range(1, total + 1))


def test_last_event_id_header_wins_over_query_after(client):
    # EventSource reconnects to the same URL (still `after=0`) but with the header set
    frames = _frames(_stream(client, "/v1/events/stream?after=0&limit=2", headers={"Last-Event-ID": "3"}))
    assert [f["id"] for f in frames] == [4, 5]


def test_sse_filters_by_run(client):
    frames = _frames(_stream(client, "/v1/events/stream?after=0&run_id=run_live&limit=2"))
    assert len(frames) == 2 and all(f["data"]["run_id"] == "run_live" for f in frames)


def test_sse_invalid_cursor_falls_back_to_live_tail(client):
    # an unparsable Last-Event-ID is ignored; with no `after` we tail from the newest event, so nothing replays
    latest = client.get("/v1/status").json()["latest_event_id"]
    async def run():
        gen = api_events.event_stream(lambda: connect_ro(client.app.state.db_path), cursor=latest, poll_s=0.01, keepalive_s=0.02)
        assert (await gen.__anext__()).startswith("retry:")
        frame = await gen.__anext__()  # nothing new: the next frame is a keep-alive, not a replayed event
        await gen.aclose()
        return frame
    assert asyncio.run(run()) == ": keep-alive\n\n"
    assert api_events.parse_cursor("abc") is None and api_events.parse_cursor("-1") is None
    assert api_events.parse_cursor(" 7 ") == 7 and api_events.parse_cursor(None) is None


def test_sse_delivers_new_rows_live_and_sends_keepalives(world):
    path = world / "t.sqlite"

    async def run():
        con = db.connect(path)
        latest = con.execute("SELECT max(event_id) FROM events").fetchone()[0]
        gen = api_events.event_stream(lambda: connect_ro(path), cursor=latest, poll_s=0.01, keepalive_s=0.03)
        got = [await gen.__anext__()]  # retry:
        got.append(await gen.__anext__())  # idle: keep-alive comment
        new_id = db.add_event(con, "job.done", {"uid": 9}, "run_live")
        while not any(g.startswith(f"id: {new_id}\n") for g in got):
            got.append(await asyncio.wait_for(gen.__anext__(), 2))
        await gen.aclose()
        return got, new_id

    got, new_id = asyncio.run(run())
    assert ": keep-alive\n\n" in got
    frame = next(g for g in got if g.startswith(f"id: {new_id}\n"))
    assert json.loads(frame.split("data: ", 1)[1])["payload"] == {"uid": 9}


def test_sse_stops_when_client_disconnects(world):
    async def run():
        calls = {"n": 0}

        async def gone():
            calls["n"] += 1
            return calls["n"] > 1
        frames = [f async for f in api_events.event_stream(lambda: connect_ro(world / "t.sqlite"), cursor=0, poll_s=0.01,
                                                           is_disconnected=gone)]
        return frames
    frames = asyncio.run(run())
    assert frames[0].startswith("retry:") and len(frames) < 300  # first poll drained <=200 events, then it returned


# ------------------------------------------------------------------ the committed OpenAPI file is current


def test_committed_openapi_matches_the_api():
    spec_path = REPO / "scripts" / "export-openapi.py"
    s = importlib.util.spec_from_file_location("export_openapi", spec_path)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    text = mod.render_json(mod.build_spec())
    committed = (REPO / "docs" / "api" / "openapi.json").read_text(encoding="utf-8")
    assert committed == text, "docs/api/openapi.json is stale: run `python scripts/export-openapi.py`"
    assert (REPO / "apps" / "web" / "lib" / "api-types.ts").exists()
    spec = json.loads(text)
    for name in ("StatusOut", "Leaderboard", "RunDetail", "WeightBatchOut", "AuditOut", "EventOut", "ChallengeOut"):
        assert name in spec["components"]["schemas"], name
    assert "text/event-stream" in json.dumps(spec["paths"]["/v1/events/stream"])


def test_identities_outside_the_newest_run_earn_no_weight(world):
    con = db.connect(world / "t.sqlite")
    _round(con, "run_new", "ch_new", {3: [0, 0, 0, 0]}, retire=True)  # only hotkey 3 is registered in the newest round
    con.close()
    c = TestClient(create_app(world / "t.sqlite", public_dir=world / "public", runs_dir=world / "runs", chain_rpc=None,
                              state_file=world / "none.json"))
    rows = {r["uid"]: r for r in c.get("/v1/leaderboard").json()["rows"]}
    assert rows[1]["mean_quality"] == 100 and rows[1]["weight"] == 0  # stale identity: above the floor but not current
    assert rows[1]["latest_batch_weight"] == 1.0  # what the newest weight batch actually gave it
