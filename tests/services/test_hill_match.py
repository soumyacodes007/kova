import hashlib
from types import SimpleNamespace as NS
import pytest
from cadrecover.protocol import Evaluation, SetScore
from cadrecover.protocol.hill import Model
from cadrecover.storage import db
from cadrecover.validator.hill import match

SNAP={"block_number":12,"block_hash":"0x"+"a"*64,"drand_round":5,"drand_randomness":"0x"+"b"*64,"decided_block":14}

@pytest.mark.parametrize("challenger,champion,expected",[(50,None,"crowned"),(49.9,None,"defended"),
    (82.01,80,"crowned"),(82,80,"defended"),(80,80,"defended"),(70,80,"defended")])
def test_strict_margin_and_initial_floor(challenger,champion,expected):
    assert match.verdict(challenger,champion)==expected


def test_reproducible_seed_and_task_plan():
    seed=match.derive_seed(SNAP["block_hash"],"m_x",SNAP["drand_randomness"])
    assert seed==match.derive_seed(SNAP["block_hash"],"m_x",SNAP["drand_randomness"])
    tasks=match.task_specs(seed,10)
    assert tasks==match.task_specs(seed,10)
    assert [t[0] for t in tasks[:3]]==["plate","flange","wafer_chuck"]
    different=match.derive_seed("0x"+"c"*64,"m_x",SNAP["drand_randomness"])
    assert match.task_specs(different,10)!=tasks
    assert match.derive_seed(SNAP["block_hash"],"m_y",SNAP["drand_randomness"])!=seed
    assert match.derive_seed(SNAP["block_hash"],"m_x","0x"+"d"*64)!=seed

@pytest.fixture
def setup(tmp_path,monkeypatch):
    con=db.connect(tmp_path/"hill.db")
    counter=[]
    def challenge(family,seed):
        cid=f"ch_{len(counter)}"
        counter.append((family,seed))
        con.execute("INSERT INTO challenges VALUES (?,?,?,'active','{}','private',NULL)",(cid,family,"now"))
        con.commit()
        return {"challenge_id":cid}
    monkeypatch.setattr(match.pipeline,"new_challenge",challenge)
    calls=[]
    scores={"challenger":100.0,"champion":75.0}
    harnesses=[]
    def score(con,runner,model,cid,mid,index,side,harness):
        calls.append((cid,index,side))
        harnesses.append(harness)
        ev=Evaluation(challenge_id=cid,job_id=f"{mid}-{index}-{side}",miner_hotkey=model.fingerprint,
                      sets=[SetScore(index=i,values={"x":42+i},valid=True,critical_ok=True,
                             geometry=scores[side]/100,dimensions=scores[side]/100) for i in range(4)])
        return match._entry(ev,1,None),ev
    monkeypatch.setattr(match,"_score",score)
    return NS(con=con,counter=counter,calls=calls,scores=scores,harnesses=harnesses)

def model(name,status="queued",source="catalog"):
    return Model(fingerprint=hashlib.sha256(name.encode()).hexdigest(),name=name,source=source,
                 submitted_at="now",status=status,commit_block=10)


def test_crown_same_tasks_lineage_and_retirement(setup):
    s=setup
    old=model("old","champion")
    old.mean_quality=75
    db.save_model(s.con,old)
    new=model("new")
    db.save_model(s.con,new)
    summary=match.run_match(s.con,new,None,tasks_per_match=3,snapshot=SNAP,log=lambda _:None)
    assert summary.verdict=="crowned" and summary.challenger_mean==pytest.approx(100,abs=1e-12) and summary.champion_mean==pytest.approx(75,abs=1e-12)
    assert summary.tasks_done==3 and summary.decided_block==14
    assert len(s.calls)==6 and len(s.counter)==3
    for index in range(3):
        ids={c[0] for c in s.calls if c[1]==index}
        assert len(ids)==1
    assert match.current_champion(s.con).fingerprint==new.fingerprint
    assert s.con.execute("SELECT count(*) FROM challenges WHERE status='active'").fetchone()[0]==0
    assert s.con.execute("SELECT count(*) FROM lineage").fetchone()[0]==1
    assert {m.name:m.status for m in db.hill_models(s.con)}=={"old":"defeated","new":"champion"}


def test_empty_hill_below_floor_no_crown(setup):
    s=setup
    s.scores["challenger"]=25
    summary=match.run_match(s.con,model("constant"),None,tasks_per_match=1,snapshot=SNAP,log=lambda _:None)
    assert summary.verdict=="defended" and summary.champion is None
    assert match.current_champion(s.con) is None
    assert s.con.execute("SELECT count(*) FROM lineage").fetchone()[0]==0


def test_interruption_resumes_hidden_tasks_and_cached_champion(setup,monkeypatch):
    s=setup
    db.save_model(s.con,model("old","champion"))
    ch=model("new")
    orig=match._score
    def fail_second(con,runner,model,cid,mid,index,side,harness):
        if index==1 and side=="challenger":
            raise match.ChutesUnavailable("network down")
        return orig(con,runner,model,cid,mid,index,side,harness)
    monkeypatch.setattr(match,"_score",fail_second)
    with pytest.raises(match.ChutesUnavailable):
        match.run_match(s.con,ch,None,tasks_per_match=3,snapshot=SNAP,log=lambda _:None)
    assert s.con.execute("SELECT count(*) FROM challenges WHERE status='active'").fetchone()[0]==2
    assert match.current_champion(s.con).name=="old"
    monkeypatch.setattr(match,"_score",orig)
    # Explicit snap on resume isn't allowed to replace the stored entropy/task plan.
    stored=match.MatchSummary.model_validate_json(s.con.execute("SELECT summary_json FROM matches").fetchone()[0])
    # Avoid a real chain query in unit test for deciding block.
    class Sub:
        block=20
        def __enter__(self):return self
        def __exit__(self,*a):pass
    import bittensor
    monkeypatch.setattr(bittensor,"Subtensor",lambda *a,**k:Sub())
    done=match.run_match(s.con,ch,None,tasks_per_match=99,snapshot=SNAP,log=lambda _:None)
    assert done.match_id==stored.match_id and done.tasks_total==3
    assert len(s.counter)==3
    assert len([c for c in s.calls if c[1]==0 and c[2]=="champion"])==1


def test_seed_must_be_after_commit(setup):
    with pytest.raises(match.HillUnavailable,match="after challenger"):
        match.run_match(setup.con,model("new"),None,snapshot={**SNAP,"block_number":10},log=lambda _:None)

def test_miner_never_faked_when_deploy_disabled(setup):
    m=model("miner",source="miner")
    with pytest.raises(match.HillUnavailable,match="deploy disabled"):
        match.run_match(setup.con,m,None,snapshot=SNAP)
    assert not setup.calls and not setup.counter
    assert db.hill_models(setup.con)[0].status=="queued"

def test_lineage_labels():
    assert [match.revision_label(i) for i in (0,25,26,27,701)]==["A","Z","AA","AB","ZZ"]

def test_catalog_champion_self_weight_receipt(setup,monkeypatch):
    from cadrecover.chain import bootstrap
    from cadrecover.validator import round as rounds
    con=setup.con
    champ=model("catalog","champion")
    champ.mean_quality=80
    champ.recent_tasks=[80]
    db.save_model(con,champ)
    monkeypatch.setattr(bootstrap,"load_state",lambda network:{"netuid":2,"neurons":{"validator":{"uid":1}}})
    monkeypatch.setattr(bootstrap,"wallet",lambda name:NS(hotkey=NS(ss58_address="validator")))
    seen=[]
    def weights(con,batch,*args):
        seen.append(batch.weights)
        db.add_receipt(con,batch.batch_id,"revealed",block=5,readback=batch.weights)
        return "revealed"
    monkeypatch.setattr(rounds,"_set_weights",weights)
    assert match.submit_champion_weights(con,log=lambda _:None)["state"]=="revealed"
    assert seen==[{1:1.0}]
    assert con.execute("SELECT count(*) FROM events WHERE kind='hill.self_weight'").fetchone()[0]==1


def test_paid_generation_cached_across_sandbox_outage(tmp_path,monkeypatch):
    from cadrecover.validator.hill.chutes import Generation
    from cadrecover import paths
    png=b"practice-png"
    (tmp_path/"drawing.png").write_bytes(png)
    monkeypatch.setattr(paths,"PUBLIC",tmp_path)
    monkeypatch.setattr(paths,"RUNTIME",tmp_path/"runtime")
    monkeypatch.setattr(db,"get_public_challenge",lambda *a:NS(drawing=NS(
        path="drawing.png",sha256=hashlib.sha256(png).hexdigest())))
    mid="o/catalog"
    m=model("x")
    m.fingerprint=hashlib.sha256(("chutes-catalog:"+mid).encode()).hexdigest()
    generated=[]
    class Runner:
        _catalog={mid:object()}
        def generate(self,*a):
            generated.append(a)
            return Generation("def build_part(overrides): pass\n",None,1,10,10,.001)
    ev=Evaluation(challenge_id="ch",job_id="j",miner_hotkey="m",
                  sets=[SetScore(index=i,values={},valid=False,critical_ok=False,geometry=0,dimensions=0) for i in range(4)],
                  failure_class="validator_outage")
    scored=[]
    def score(cid,source,**kwargs):
        scored.append(source)
        return ev
    monkeypatch.setattr(match,"score_source",score)
    for _ in range(2):
        assert match._score(None,Runner(),m,"ch","m_cache",0,"champion")[1].failure_class=="validator_outage"
    assert len(generated)==1 and len(scored)==2
    cache=tmp_path/"runtime/hill/m_cache/task0/champion/generation.json"
    assert cache.exists() and cache.stat().st_mode & 0o077==0


def test_finalization_failure_rolls_back_champion_and_seed_publication(setup):
    import sqlite3
    s=setup
    db.save_model(s.con,model("old","champion"))
    s.con.executescript("""CREATE TRIGGER fail_lineage BEFORE INSERT ON lineage
                          BEGIN SELECT RAISE(ABORT,'simulated disk failure'); END;""")
    with pytest.raises(sqlite3.IntegrityError):
        match.run_match(s.con,model("new"),None,tasks_per_match=1,snapshot=SNAP,log=lambda _:None)
    assert match.current_champion(s.con).name=="old"
    assert s.con.execute("SELECT count(*) FROM lineage").fetchone()[0]==0
    row=s.con.execute("SELECT summary_json FROM matches").fetchone()[0]
    assert match.MatchSummary.model_validate_json(row).status=="running"
    assert s.con.execute("SELECT status FROM challenges").fetchone()[0]=="active"


def test_lineage_dethrones_prior_revision_and_defence_keeps_owner(setup):
    import json
    s=setup
    s.scores["challenger"]=60
    first=match.run_match(s.con,model("first"),None,tasks_per_match=1,snapshot=SNAP,log=lambda _:None)
    assert first.verdict=="crowned"
    s.scores.update(challenger=90,champion=60)
    second=match.run_match(s.con,model("second"),None,tasks_per_match=1,snapshot=SNAP,log=lambda _:None)
    assert second.verdict=="crowned"
    rows=[json.loads(r[0]) for r in s.con.execute("SELECT entry_json FROM lineage ORDER BY rowid")]
    assert [r["rev"] for r in rows]==["A","B"] and rows[0]["dethroned_at_block"]==14
    s.scores.update(challenger=92,champion=90)
    third=match.run_match(s.con,model("third"),None,tasks_per_match=1,snapshot=SNAP,log=lambda _:None)
    assert third.verdict=="defended" and match.current_champion(s.con).name=="second"
    assert s.con.execute("SELECT count(*) FROM lineage").fetchone()[0]==2


def test_match_pins_harness_and_legacy_match_resumes_on_v1(setup):
    s=setup
    summary=match.run_match(s.con,model("first"),None,tasks_per_match=2,snapshot=SNAP,log=lambda _:None)
    assert match.match_harness(s.con,"local",summary.match_id)==match.HARNESS_VERSION
    assert set(s.harnesses)=={match.HARNESS_VERSION}
    # A match stored before harness versioning has no record: it ran and must finish on harness 1.
    assert match.match_harness(s.con,"local","m_legacy")==1


def test_mock_miner_is_localnet_only_and_routes_to_the_strategy(setup,monkeypatch):
    from cadrecover.validator.hill import mock
    s=setup
    mk=model("mock-noisy (mock miner)",source="mock")
    mk.base_model="mock-noisy"
    with pytest.raises(match.HillUnavailable):
        match.run_match(s.con,mk,None,tasks_per_match=1,network="finney",snapshot=SNAP,log=lambda _:None)
    calls=[]
    class Chutes:
        budget=None; _catalog={}
        def generate(self,*a): calls.append(a)
    solved=[]
    monkeypatch.setattr("cadrecover.miner.strategies.get",lambda name:NS(solve=lambda pub,png,job:solved.append((name,job)) or NS(source="x=1\n")))
    gen=mock.HillRunner(Chutes()).generate("mock:mock-noisy",NS(challenge_id="ch_1"),b"png","m_1",2)
    assert gen.source=="x=1\n" and gen.cost_usd==0 and solved==[("mock-noisy","m_1-ch_1")] and calls==[]
    mock.HillRunner(Chutes()).generate("google/x",NS(challenge_id="ch_1"),b"png","m_1",2)
    assert calls and calls[0][0]=="google/x" and calls[0][4]==2
    with pytest.raises(ValueError):
        mock.HillRunner(Chutes()).generate("mock:diag-crash",NS(challenge_id="ch_1"),b"png","m_1",2)
