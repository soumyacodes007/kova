"""Chain + audit logic that doesn't need a node: commitment encoding, weight readback check,
axon URL mapping, audit pass rule, audit-zeroed and stale identities in standings."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from cadrecover.audit.auditor import engine_command, verdict
from cadrecover.chain import commitments
from cadrecover.chain.neurons import _axon_url
from cadrecover.protocol import Evaluation, SetScore
from cadrecover.storage import db
from cadrecover.validator.aggregate import standings
from cadrecover.validator.round import matches

DIGEST = "sha256:" + "ab" * 32


def test_commitment_round_trip_and_sdk_shapes():
    raw = commitments.encode(DIGEST, "mock-oracle@0.1.0")
    assert len(raw) <= commitments.MAX_RAW
    want = {"e": DIGEST, "s": "mock-oracle@0.1.0"}
    assert commitments.decode(raw) == want
    assert commitments.decode("0x" + raw.hex()) == want
    assert commitments.decode({"fields": [[{f"Raw{len(raw)}": "0x" + raw.hex()}]]}) == want
    assert commitments.decode({"commitment": raw.decode()}) == want
    obj = SimpleNamespace(block=17264, data=raw.decode())
    assert commitments.decode(obj) == {**want, "block": 17264}
    assert commitments.decode(None) is None and commitments.decode("not json") is None


def test_commitment_rejects_bad_digest_and_oversize():
    with pytest.raises(ValueError):
        commitments.encode("sha256:short", "x")
    with pytest.raises(ValueError):
        commitments.encode(DIGEST, "s" * 100)


def test_readback_match_tolerates_u16_quantization_only():
    assert matches({2: 1.0}, {2: 1.0})
    assert matches({2: 65535, 3: 32767}, {2: 2 / 3, 3: 1 / 3})  # raw u16 row vs normalized batch
    assert not matches({2: 1.0}, {2: 0.5, 3: 0.5})
    assert not matches({}, {2: 1.0})
    assert not matches({2: 0.6, 3: 0.4}, {2: 0.5, 3: 0.5})


def test_axon_url_maps_this_host_to_loopback():
    assert _axon_url("10.0.0.5:8101", {"10.0.0.5"}) == "http://127.0.0.1:8101"
    assert _axon_url("8.8.8.8:8101", {"10.0.0.5"}) == "http://8.8.8.8:8101"
    assert _axon_url("0.0.0.0:0", set()) is None and _axon_url(None, set()) is None


def test_audit_pass_rule_is_one_sided_with_margin():
    assert verdict([100, 100, 100], 100)[0]
    assert verdict([95, 90, 85], 100)[0]  # mean 90 = 100 - 10
    assert not verdict([25, 25, 25], 100)[0]  # swapped constant engine
    assert verdict([100, 100, 100], 60)[0]  # better than live is not hiding anything


def test_engine_runs_locked_down_and_oracle_mount_is_dev_only(tmp_path):
    cmd = engine_command(DIGEST, tmp_path, "ch_x", "job", dev_oracle=False)
    for flag in ("--network", "--read-only", "--cap-drop", "no-new-privileges"):
        assert flag in cmd
    assert cmd[cmd.index("--network") + 1] == "none" and cmd[-1] == DIGEST
    assert not any("private" in c for c in cmd)
    dev = engine_command(DIGEST, tmp_path, "ch_x", "job", dev_oracle=True)
    assert any(c.endswith("private.json:ro") for c in dev)


@pytest.fixture
def con(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    c.execute("INSERT INTO challenges VALUES ('c', 'plate', 'now', 'retired', '{}', 'p', NULL)")
    c.commit()
    return c


def _add(con, uid, hotkey, reg, job_id, q):
    db.create_run(con, f"run-{job_id}", "c", datetime.now(timezone.utc) + timedelta(minutes=3))
    db.upsert_miner(con, hotkey, reg, uid, None)
    db.add_assignment(con, job_id, f"run-{job_id}", hotkey, reg, uid)
    sets = [SetScore(index=i, values={}, valid=True, critical_ok=True, geometry=q, dimensions=q) for i in range(4)]
    db.save_evaluation(con, Evaluation(challenge_id="c", job_id=job_id, miner_hotkey=hotkey, sets=sets))


def test_failed_audit_zeroes_until_a_clean_audit(con):
    _add(con, 2, "hk_a", 10, "j1", 1.0)
    _add(con, 3, "hk_b", 10, "j2", 0.8)
    db.save_audit(con, "a1-0", "hk_a", DIGEST, "c", 25, False, 1, {"verdict": "fail"})
    zeroed = db.failed_audits(con)
    assert zeroed == {"hk_a"}
    table = {s.hotkey: s for s in standings(con, zeroed=zeroed)}
    assert table["hk_a"].weight == 0 and table["hk_b"].weight == pytest.approx(1)
    db.save_audit(con, "a2-0", "hk_a", DIGEST, "c", 100, True, 2, {"verdict": "pass"})
    assert db.failed_audits(con) == set()


def test_only_current_identities_earn(con):
    _add(con, 2, "hk_a", 0, "j1", 1.0)  # stale identity from static discovery (block 0)
    _add(con, 2, "hk_a", 11631, "j2", 1.0)  # the same hotkey registered on chain
    table = standings(con, current={("hk_a", 11631)})
    w = {(s.hotkey, s.registered_at_block): s.weight for s in table}
    assert w[("hk_a", 0)] == 0 and w[("hk_a", 11631)] == pytest.approx(1)


def test_audit_zeroed_miner_still_holding_chain_weight_is_detected(con, monkeypatch):
    from cadrecover.chain import neurons
    from cadrecover.validator.discovery import MinerEndpoint
    from cadrecover.validator.round import _holds_audit_zeroed_weight

    miners = [MinerEndpoint(hotkey=h, uid=u, registered_at_block=10, url=f"http://x:{u}")
              for u, h in ((2, "hk_a"), (3, "hk_b"))]
    row = {"revealed_row": {2: 1.0}}
    monkeypatch.setattr(neurons, "read_weights", lambda network="local": row)
    assert not _holds_audit_zeroed_weight(con, miners, "local")  # no failed audit yet
    db.save_audit(con, "a1-0", "hk_a", DIGEST, "c", 25, False, 1, {"verdict": "fail"})
    assert _holds_audit_zeroed_weight(con, miners, "local")  # failed miner still on chain: must be revoked
    row["revealed_row"] = {3: 1.0}
    assert not _holds_audit_zeroed_weight(con, miners, "local")  # on-chain weight is for someone else
    row["revealed_row"] = {1: 1.0}  # the validator's own self-weight = already revoked
    assert not _holds_audit_zeroed_weight(con, miners, "local")


def test_model_commitment_round_trip_distinct_and_bounded():
    raw=commitments.encode_model("owner/model","a"*40,"b"*64)
    want={"k":"m","r":"owner/model","v":"a"*40,"f":"b"*16}
    assert len(raw)<=128
    assert commitments.decode(raw)==want
    assert commitments.decode(SimpleNamespace(data=raw,block=17))=={**want,"block":17}
    assert "e" not in commitments.decode(raw)
    with pytest.raises(ValueError):
        commitments.encode_model("owner/"+"m"*100,"a"*40,"b"*64)
    with pytest.raises(ValueError):
        commitments.encode_model("owner/model","main","b"*64)


def test_testnet_state_separate_owner_validator(tmp_path,monkeypatch):
    from cadrecover.chain import bootstrap
    import json
    monkeypatch.setattr(bootstrap,"STATE_FILE",tmp_path/"chain.json")
    monkeypatch.setattr(bootstrap.paths,"HOME",tmp_path)
    (tmp_path/"chain.json").write_text(json.dumps({"netuid":2}))
    (tmp_path/"chain-test.json").write_text(json.dumps({"netuid":605,"owner_hotkey":"ownerhot"}))
    assert bootstrap.load_state()["netuid"]==2
    test=bootstrap.load_state("test")
    assert test["netuid"]==605 and test["neurons"]["validator"]=={"uid":0,"hotkey":"ownerhot"}
    with pytest.raises(ValueError):
        bootstrap.load_state("mainnet")
