from types import SimpleNamespace as NS
import pytest
import bittensor as bt
from cadrecover.protocol.hill import ModelCommitment
from cadrecover.storage import db
from cadrecover.validator.hill import watcher

@pytest.fixture
def state(tmp_path,monkeypatch):
    con=db.connect(tmp_path/"h.db")
    neuron=NS(hotkey="miner-hot",uid=2)
    class Sub:
        subnets=NS(metagraph=lambda **k:NS(neurons=[neuron]))
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr(bt,"Subtensor",lambda *a:Sub())
    monkeypatch.setattr(watcher,"load_state",lambda n:{"netuid":2})
    monkeypatch.setattr(watcher.commitments,"read_commitment",lambda *a,**k:{
        "k":"m","r":"o/m","v":"a"*40,"f":"b"*16,"block":7})
    monkeypatch.setattr(watcher,"precheck_model",lambda *a,**k:ModelCommitment(
        repo="o/m",revision="a"*40,fingerprint="b"*64,weight_bytes=100))
    return con

def test_watcher_submitted_prechecked_queued_and_idempotent(state):
    found=watcher.discover_model_commitments(con=state,log=lambda _:None)
    assert len(found)==1 and found[0].status=="queued" and found[0].hotkey=="miner-hot"
    assert found[0].fee.simulated and found[0].fee.amount_tao==0
    assert not watcher.discover_model_commitments(con=state,log=lambda _:None)
    events=state.execute("SELECT payload FROM events WHERE kind='model.status'").fetchall()
    assert any("submitted" in r[0] for r in events)
    assert any("deploy disabled on this network" in r[0] for r in events)

def test_watcher_wrong_fingerprint_never_queued(state,monkeypatch):
    monkeypatch.setattr(watcher,"precheck_model",lambda *a,**k:ModelCommitment(
        repo="o/m",revision="a"*40,fingerprint="c"*64,weight_bytes=100))
    assert watcher.discover_model_commitments(con=state,log=lambda _:None)==[]
    assert db.hill_models(state)==[]
    assert "does not match" in state.execute("SELECT error FROM hill_commitments").fetchone()[0]


def test_watcher_duplicate_priority_uses_commit_block_not_uid(state,monkeypatch):
    class Sub:
        subnets=NS(metagraph=lambda **k:NS(neurons=[NS(hotkey="late",uid=1),NS(hotkey="early",uid=2)]))
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr(bt,"Subtensor",lambda *a:Sub())
    monkeypatch.setattr(watcher.commitments,"read_commitment",lambda h,*a,**k:{
        "k":"m","r":"o/m","v":"a"*40,"f":"b"*16,"block":20 if h=="late" else 10})
    found=watcher.discover_model_commitments(con=state,log=lambda _:None)
    assert len(found)==1 and found[0].hotkey=="early"
    assert db.hill_models(state)[0].hotkey=="early"
    assert "committed later" in state.execute("SELECT error FROM hill_commitments WHERE hotkey='late'").fetchone()[0]
