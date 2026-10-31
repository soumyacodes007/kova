"""King of the hill: same fresh drawings, fixed harness, exact Track A evaluator."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cadrecover import paths
from cadrecover.challenges import pipeline
from cadrecover.evaluation.score import load_private, score_source
from cadrecover.protocol import QUALITY_FLOOR, Evaluation, SetScore, WeightBatch
from cadrecover.protocol.hill import Entry, LineageEntry, MatchSummary, MatchTask, Model, ModelRef, SetResult, Progress
from cadrecover.storage import db
from cadrecover.validator.hill.budget import BudgetExceeded
from cadrecover.validator.hill.chutes import HARNESS_VERSION, ChutesRunner, ChutesUnavailable

FAMILIES = ("plate", "flange", "wafer_chuck")
MARGIN = 2.0


class HillUnavailable(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_seed(block_hash: str, match_id: str, drand_randomness: str) -> int:
    block = bytes.fromhex(block_hash.removeprefix("0x"))
    randomness = bytes.fromhex(drand_randomness.removeprefix("0x"))
    if len(block) != 32 or len(randomness) != 32 or not match_id:
        raise ValueError("seed requires a 32-byte block hash, match id and 32-byte drand randomness")
    return int.from_bytes(hashlib.sha256(block + match_id.encode("utf-8") + randomness).digest()[:4], "big")


def task_specs(seed: int, count: int) -> list[tuple[str, int]]:
    if not 1 <= count <= 100:
        raise ValueError("tasks_per_match must be between 1 and 100")
    return [(FAMILIES[i % len(FAMILIES)], int.from_bytes(
        hashlib.sha256(seed.to_bytes(4, "big") + i.to_bytes(4, "big")).digest()[:4], "big"))
        for i in range(count)]


def fresh_snapshot(network: str, after_block: int | None = None) -> dict:
    import bittensor as bt
    from cadrecover.chain.setup import network_url
    with bt.Subtensor(network_url(network)) as sub:
        threshold = max(int(after_block or 0), sub.block)
        deadline = time.monotonic() + 60
        while sub.block <= threshold:
            if time.monotonic() > deadline:
                raise HillUnavailable("chain did not produce a fresh post-commit block")
            time.sleep(.5)
        block = sub.block
        info = sub.block_info(block)
        round_no = int(sub.query(bt.storage.Drand.LastStoredRound, [], block=block) or 0)
        pulse = sub.query(bt.storage.Drand.Pulses, [round_no], block=block) if round_no else None
        if not pulse or not pulse.get("randomness") or not info or not info.hash:
            raise HillUnavailable("chain block or stored drand randomness unavailable")
        return {"block_number": block, "block_hash": info.hash, "drand_round": round_no,
                "drand_randomness": pulse["randomness"]}


def current_champion(con, network="local") -> Model | None:
    champions = [m for m in db.hill_models(con,network) if m.status == "champion"]
    if len(champions) > 1:
        raise HillUnavailable("multiple champions in database; refusing an ambiguous hill")
    return champions[0] if champions else None


def verdict(challenger_mean: float, champion_mean: float | None, margin: float = MARGIN) -> str:
    if margin < 0:
        raise ValueError("margin cannot be negative")
    return "crowned" if (challenger_mean >= QUALITY_FLOOR if champion_mean is None
                         else challenger_mean > champion_mean + margin) else "defended"


def revision_label(index: int) -> str:
    label = ""
    while index >= 0:
        label = chr(65 + index % 26) + label
        index = index // 26 - 1
    return label


def _entry(ev: Evaluation, latency: float, error: str | None) -> Entry:
    # API withholds values/checks for active tasks independently; DB stores exact evaluation.
    return Entry(quality=None if ev.failure_class == "validator_outage" else ev.quality,
                 latency_s=latency,error=error or ev.failure_reason,
                 sets=[SetResult(index=s.index,valid=s.valid,critical_ok=s.critical_ok,
                       geometry=s.geometry,dimensions=s.dimensions,q_s=s.q,
                       passed=s.valid and s.critical_ok and not s.failed_checks,
                       failed_check_count=len(s.failed_checks),failed_checks=[],
                       values=None,revealed=False) for s in ev.sets])


def match_harness(con, network: str, match_id: str) -> int:
    """Harness a match started with. Matches from before versioning ran harness 1."""
    row = con.execute("SELECT value_json FROM hill_settings WHERE key=?", (f"{network}.harness.{match_id}",)).fetchone()
    return json.loads(row[0]) if row else 1


def _score(con, runner, model: Model, challenge_id: str, match_id: str, index: int, side: str, harness: int = 1):
    public = db.get_public_challenge(con,challenge_id)
    image_path = paths.PUBLIC / public.drawing.path
    png = image_path.read_bytes()
    if hashlib.sha256(png).hexdigest() != public.drawing.sha256:
        raise HillUnavailable("drawing hash mismatch")
    if model.source=="mock":
        from cadrecover.validator.hill.mock import MOCK_PREFIX
        model_id=MOCK_PREFIX+(model.base_model or "")
    else:
        catalog = runner._catalog or {m.id:m for m in runner.catalog()}
        model_id = next((mid for mid in catalog if hashlib.sha256(("chutes-catalog:"+mid).encode()).hexdigest()==model.fingerprint),None)
        if model_id is None:
            raise HillUnavailable("catalog endpoint no longer available")
    # Persist a successful paid response before sandbox execution so an outage
    # retries the identical source and never buys a different answer.
    folder=paths.RUNTIME/"hill"/match_id/f"task{index}"/side
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    cache=folder/"generation.json"
    from cadrecover.validator.hill.chutes import Generation
    if cache.exists():
        stored=json.loads(cache.read_text())
        if stored["fingerprint"]!=model.fingerprint or stored["drawing_sha256"]!=public.drawing.sha256:
            raise HillUnavailable("generation cache identity mismatch")
        gen=Generation(**stored["generation"])
    else:
        gen = runner.generate(model_id,public,png,match_id,harness)
        temp=cache.with_suffix(".tmp")
        temp.write_text(json.dumps({"fingerprint":model.fingerprint,"drawing_sha256":public.drawing.sha256,
                                   "generation":asdict(gen)}),encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(cache)
    if gen.source is None:
        ev = Evaluation(challenge_id=challenge_id,job_id=f"{match_id}-{index}-{side}",
                        miner_hotkey=model.hotkey or model.fingerprint,failure_class="miner",failure_reason=gen.error,
                        sets=[SetScore(index=s.index,values=s.values,valid=False,critical_ok=False,
                                       geometry=0,dimensions=0) for s in load_private(challenge_id).sets])
    else:
        ev = score_source(challenge_id,gen.source,job_id=f"{match_id}-{index}-{side}",
                          miner_hotkey=model.hotkey or model.fingerprint,
                          glb_dir=paths.RUNTIME/"hill"/match_id/f"task{index}"/side)
    return _entry(ev,gen.latency_s,gen.error), ev


def _update_stats(model: Model, tasks: list[MatchTask], side: str, evaluations: list[Evaluation]):
    entries = [getattr(t,side) for t in tasks]
    scored = [(t,e) for t,e in zip(tasks,entries) if e is not None and e.quality is not None]
    model.recent_tasks = [e.quality for t,e in scored]
    model.mean_quality = sum(model.recent_tasks)/len(scored) if scored else None
    model.per_family = {f:sum(e.quality for t,e in scored if t.family==f)/sum(t.family==f for t,e in scored)
                        for f in FAMILIES if any(t.family==f for t,e in scored)}
    sets = [s for ev in evaluations for s in ev.sets]
    model.critical_pass_rate = sum(s.valid and s.critical_ok for s in sets)/len(sets) if sets else None
    edits = [s for s in sets if s.index>0]
    model.edit_pass_rate = sum(s.valid and s.critical_ok and not s.failed_checks for s in edits)/len(edits) if edits else None
    latencies = [e.latency_s for t,e in scored if e.latency_s is not None]
    model.mean_latency_s = sum(latencies)/len(latencies) if latencies else None
    model.progress = None


def _finalize(con, summary, challenger, champion, block, network):
    """One transaction for lineage, champion ownership, events and match verdict."""
    decided=summary.model_copy(update={"status":"decided","decided_block":block})
    before_challenger=challenger.model_copy(deep=True)
    before_champion=champion.model_copy(deep=True) if champion else None
    con.execute("BEGIN IMMEDIATE")
    def event(kind,payload):
        con.execute("INSERT INTO events(at,kind,run_id,payload) VALUES (?,?,NULL,?)",
                    (now(),kind,json.dumps({**payload,"network":network})))
    def save(model,status,detail=None):
        model.status=status
        con.execute("INSERT INTO models VALUES (?,?,?) ON CONFLICT(fingerprint,network) DO UPDATE SET model_json=excluded.model_json",
                    (model.fingerprint,model.model_dump_json(),network))
        event("model.status",{"fingerprint":model.fingerprint,"status":status,"detail":detail,"block":block})
    try:
        save(challenger,"scored")
        if summary.verdict=="crowned":
            rows=con.execute("SELECT rev,entry_json FROM lineage WHERE network=? ORDER BY rowid",(network,)).fetchall()
            if champion and rows:
                last=LineageEntry.model_validate_json(rows[-1]["entry_json"])
                last.dethroned_at_block=block
                con.execute("UPDATE lineage SET entry_json=? WHERE rev=? AND network=?",
                            (last.model_dump_json(),last.rev,network))
            challenger.matches_won+=1
            entry=LineageEntry(rev=revision_label(len(rows)),fingerprint=challenger.fingerprint,
                               name=challenger.name,crowned_at_block=block,crowned_at=now(),score=challenger.mean_quality)
            con.execute("INSERT INTO lineage VALUES (?,?,?)",(entry.rev,entry.model_dump_json(),network))
            if champion:
                champion.matches_lost+=1
                save(champion,"defeated",f"dethroned by {challenger.name}")
            save(challenger,"champion")
        else:
            challenger.matches_lost+=1
            save(challenger,"defeated","quality floor or strict winning margin not met")
            if champion:
                champion.matches_won+=1
                save(champion,"champion")
        con.execute("UPDATE matches SET summary_json=? WHERE match_id=?",
                    (decided.model_dump_json(),summary.match_id))
        # Retire in the same transaction that makes the seed public.
        for row in con.execute("SELECT challenge_id FROM match_tasks WHERE match_id=?",(summary.match_id,)).fetchall():
            con.execute("UPDATE challenges SET status='retired',retired_at=? WHERE challenge_id=?",(now(),row[0]))
            event("challenge.retired",{"challenge_id":row[0],"reason":"hill match finished"})
        event("hill."+summary.verdict,{"match_id":summary.match_id,"fingerprint":
              challenger.fingerprint if summary.verdict=="crowned" else champion.fingerprint if champion else None,
              "block":block})
        con.commit()
        return decided
    except BaseException:
        con.rollback()
        challenger.__dict__.update(before_challenger.__dict__)
        if champion:
            champion.__dict__.update(before_champion.__dict__)
        raise


def run_match(con, challenger: Model, runner, *, tasks_per_match=10, margin=MARGIN, network="local",
              snapshot=None, log=print) -> MatchSummary:
    # Miner endpoints are not treated as catalog calls. Deployment must be enabled and verified separately.
    if challenger.source=="mock" and network not in ("local","test"):
        raise HillUnavailable("the scripted mock miner runs on localnet or testnet only")
    if challenger.source not in ("catalog","mock"):
        db.model_status(con,challenger,"queued",detail="deploy disabled on this network",network=network)
        raise HillUnavailable("deploy disabled on this network")
    champion=current_champion(con,network)
    if champion and challenger.fingerprint==champion.fingerprint:
        raise ValueError("a champion cannot challenge itself")
    existing=con.execute("SELECT * FROM matches WHERE network=? AND json_extract(summary_json,'$.status')='running' ORDER BY rowid LIMIT 1",(network,)).fetchone()
    if existing:
        summary=MatchSummary.model_validate_json(existing["summary_json"])
        expected=champion.fingerprint if champion else None
        if summary.challenger.fingerprint != challenger.fingerprint or (summary.champion.fingerprint if summary.champion else None)!=expected:
            raise HillUnavailable("an interrupted match must be resumed before another challenger")
        snap={"block_number":existing["block_number"],"drand_randomness":existing["drand_randomness"]}
    else:
        match_id="m_"+uuid.uuid4().hex[:12]
        snap=snapshot or fresh_snapshot(network,challenger.commit_block)
        if challenger.commit_block is not None and snap["block_number"] <= challenger.commit_block:
            raise HillUnavailable("seed block must be produced after challenger commitment")
        seed=derive_seed(snap["block_hash"],match_id,snap["drand_randomness"])
        summary=MatchSummary(match_id=match_id,challenger=ModelRef(fingerprint=challenger.fingerprint,name=challenger.name),
                             champion=ModelRef(fingerprint=champion.fingerprint,name=champion.name) if champion else None,
                             status="running",seed={"block_hash":snap["block_hash"],"drand_round":snap["drand_round"],"value":seed},
                             tasks_total=tasks_per_match,margin=margin,started_at=now())
        db.save_match(con,summary,snap["block_number"],snap["drand_randomness"],network)
        db.hill_setting(con,f"{network}.harness.{match_id}",HARNESS_VERSION)
        db.add_event(con,"hill.match_started",{"match_id":match_id,"fingerprint":challenger.fingerprint,
                                               "harness":HARNESS_VERSION,"network":network})
    harness=match_harness(con,network,summary.match_id)
    def persist():
        db.save_match(con,summary,snap["block_number"],snap["drand_randomness"],network)
    tasks, challenger_evals, champion_evals = [],[],[]
    db.model_status(con,challenger,"evaluating",network=network)
    try:
        # Task records are persisted before any inference. Resume uses existing drawings/results.
        for index,(family,seed) in enumerate(task_specs(summary.seed.value,summary.tasks_total)):
            row=con.execute("SELECT * FROM match_tasks WHERE match_id=? AND task_index=?",(summary.match_id,index)).fetchone()
            if row:
                task=MatchTask.model_validate_json(row["task_json"])
                cev=Evaluation.model_validate_json(row["challenger_evaluation_json"]) if row["challenger_evaluation_json"] else None
                hev=Evaluation.model_validate_json(row["champion_evaluation_json"]) if row["champion_evaluation_json"] else None
            else:
                ch=pipeline.new_challenge(family,seed=seed)
                task=MatchTask(index=index,challenge_id=ch["challenge_id"],family=family,
                               drawing_url=f"/v1/challenges/{ch['challenge_id']}/drawing.png",
                               challenger=Entry(),champion=Entry() if champion else None)
                cev=hev=None
                db.save_match_task(con,summary.match_id,task)
            for side,model,ev in (("challenger",challenger,cev),("champion",champion,hev)):
                if model is None:
                    continue
                if ev is None or ev.failure_class=="validator_outage":
                    entry,ev=_score(con,runner,model,task.challenge_id,summary.match_id,index,side,harness)
                    setattr(task,side,entry)
                    if side=="challenger": cev=ev
                    else: hev=ev
                    db.save_match_task(con,summary.match_id,task,cev,hev)
                    if ev.failure_class=="validator_outage":
                        raise HillUnavailable("sandbox/evaluator outage; task excluded for both sides")
                    db.add_event(con,"hill.task_scored",{"match_id":summary.match_id,"index":index,"side":side,
                                                        "quality":entry.quality,"network":network})
                    log(f"[hill] {summary.match_id} task {index+1}/{summary.tasks_total} {family} {side} {model.name}: Q {entry.quality:.2f}")
            tasks.append(task)
            challenger_evals.append(cev)
            if champion: champion_evals.append(hev)
            summary.tasks_done=len(tasks)
            summary.challenger_mean=sum(t.challenger.quality for t in tasks)/len(tasks)
            summary.champion_mean=sum(t.champion.quality for t in tasks)/len(tasks) if champion else None
            challenger.progress=Progress(done=len(tasks),total=summary.tasks_total)
            db.save_model(con,challenger,network)
            persist()
        _update_stats(challenger,tasks,"challenger",challenger_evals)
        if champion: _update_stats(champion,tasks,"champion",champion_evals)
        summary.challenger_mean=challenger.mean_quality
        summary.champion_mean=champion.mean_quality if champion else None
        summary.verdict=verdict(summary.challenger_mean,summary.champion_mean,summary.margin)
        # A real block is read only after scoring. Unit tests may supply a complete explicit snapshot.
        summary.decided_block=snap.get("decided_block")
        if summary.decided_block is None:
            import bittensor as bt
            from cadrecover.chain.setup import network_url
            with bt.Subtensor(network_url(network)) as sub:
                summary.decided_block=sub.block
        summary=_finalize(con,summary,challenger,champion,summary.decided_block,network)
        log(f"[hill] {summary.verdict}: challenger {summary.challenger_mean:.2f} vs "
            f"{summary.champion_mean if champion else 'empty hill'} (margin {summary.margin})")
        return summary
    except Exception as exc:
        if summary.status!="decided":
            challenger.progress=None
            db.model_status(con,challenger,"queued",detail=f"match interrupted: {type(exc).__name__}; resume required",network=network)
            db.add_event(con,"hill.interrupted",{"match_id":summary.match_id,"reason":type(exc).__name__,"network":network})
        raise


def submit_champion_weights(con, *, network="local", reveal_wait_s=120, log=print):
    from cadrecover.chain import bootstrap
    from cadrecover.validator.round import _set_weights
    champion=current_champion(con,network)
    if champion is None:
        log("[hill] no champion above quality floor; no weights update")
        return None
    state=bootstrap.load_state(network)
    v=bootstrap.wallet("owner" if network=="test" else "validator")
    uid=champion.uid if champion.hotkey else state["neurons"]["validator"]["uid"]
    if champion.hotkey:
        import bittensor as bt
        from cadrecover.chain.setup import network_url
        with bt.Subtensor(network_url(network)) as sub:
            actual=sub.read("uid",netuid=state["netuid"],hotkey_ss58=champion.hotkey)
        if actual is None or int(actual)!=uid:
            raise HillUnavailable("champion identity no longer registered; refusing recycled UID weights")
    else:
        db.add_event(con,"hill.self_weight",{"fingerprint":champion.fingerprint,"uid":uid,
                     "reason":"catalog champion has no miner hotkey; validator self-weight","network":network})
        log("[hill] catalog champion has no hotkey: validator self-weight")
    batch=WeightBatch(batch_id="wb_"+uuid.uuid4().hex[:10],network=network,netuid=state["netuid"],
                      validator_hotkey=v.hotkey.ss58_address,floor=QUALITY_FLOOR,
                      mean_quality={champion.hotkey or champion.fingerprint:champion.mean_quality},
                      samples={champion.hotkey or champion.fingerprint:len(champion.recent_tasks)},weights={uid:1.0})
    db.save_weight_batch(con,batch,"proposed")
    db.add_event(con,"weights.proposed",{"batch_id":batch.batch_id,"weights":batch.weights,"hill":True})
    result=_set_weights(con,batch,network,"hill",reveal_wait_s,log)
    return {"batch_id":batch.batch_id,"state":result,"weights":batch.weights}


@contextmanager
def _hill_lock(network):
    paths.RUNTIME.mkdir(parents=True,exist_ok=True)
    with (paths.RUNTIME/f"hill-{network}.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise HillUnavailable("another hill runner already holds this network") from None
        try: yield
        finally: fcntl.flock(lock,fcntl.LOCK_UN)


def run_catalog(*, network="local", tasks_per_match=10, max_spend_usd=.50, total_cap_usd=3.0,
                margin=MARGIN, allow_testnet_spend=False, only=None, set_weights=True, log=print) -> dict:
    from cadrecover.chain.setup import network_url
    from cadrecover.validator.hill.watcher import discover_model_commitments
    network_url(network)
    if network=="test" and not allow_testnet_spend:
        raise ValueError("testnet hill spending requires explicit allow_testnet_spend")
    if not 1<=tasks_per_match<=100 or margin<0:
        raise ValueError("invalid match settings")
    with _hill_lock(network):
        con=db.connect()
        runner=ChutesRunner(con,total_cap=total_cap_usd,match_cap=max_spend_usd)
        try:
            for key,value in (("margin",margin),("tasks_per_match",tasks_per_match),("families",FAMILIES)):
                db.hill_setting(con,f"{network}.{key}",value)
            discover_model_commitments(network,con=con,log=log)
            catalog=runner.catalog()
            if not catalog: raise HillUnavailable("no priced vision catalog models available")
            results=[]
            # Resume a pending challenger first; never draw a new task set to replace a poor output.
            running=con.execute("SELECT summary_json FROM matches WHERE network=? AND json_extract(summary_json,'$.status')='running' ORDER BY rowid LIMIT 1",(network,)).fetchone()
            pending=MatchSummary.model_validate_json(running[0]).challenger.fingerprint if running else None
            catalog.sort(key=lambda m:0 if hashlib.sha256(("chutes-catalog:"+m.id).encode()).hexdigest()==pending else 1)
            for entry in catalog:
                fp=hashlib.sha256(("chutes-catalog:"+entry.id).encode()).hexdigest()
                models={m.fingerprint:m for m in db.hill_models(con,network)}
                model=models.get(fp)
                if model is None:
                    model=Model(fingerprint=fp,name=entry.name,source="catalog",submitted_at=now(),status="submitted",
                                tee=entry.tee,chutes_url="https://llm.chutes.ai/v1/chat/completions")
                    db.model_status(con,model,"submitted",detail="catalog endpoint identity; weights not attested",network=network)
                    db.model_status(con,model,"prechecked",detail="priced vision catalog endpoint",network=network)
                    db.model_status(con,model,"queued",network=network)
                if model.status=="champion": continue
                # One decided match per catalog model per harness: a harness change applies to every model.
                decided=con.execute("SELECT match_id FROM matches WHERE network=? AND json_extract(summary_json,'$.challenger.fingerprint')=? AND json_extract(summary_json,'$.status')='decided'",(network,fp)).fetchall()
                if any(match_harness(con,network,r[0])==HARNESS_VERSION for r in decided): continue
                if only and entry.id not in only: continue
                result=run_match(con,model,runner,tasks_per_match=tasks_per_match,margin=margin,network=network,log=log)
                results.append(result.model_dump(mode="json"))
                # Both tracks share one validator weight vector; --no-weights defers the commit to the operator.
                if set_weights:
                    submit_champion_weights(con,network=network,log=log)
            spent=runner.budget.totals()
            log(f"[hill] Chutes spent/reserved total USD {spent:.6f} (cap {total_cap_usd:.2f})")
            return {"matches":results,"champion":current_champion(con,network).model_dump(mode="json") if current_champion(con,network) else None,
                    "spend_usd":spent,"total_cap_usd":total_cap_usd}
        finally:
            log(f"[hill] Chutes spent/reserved total USD {runner.budget.totals():.6f}")
            runner.close()
            con.close()


def run_mock(*, strategy="mock-noisy", wallet="miner2", network="local", tasks_per_match=10,
             max_spend_usd=.50, total_cap_usd=3.0, margin=MARGIN, allow_testnet_spend=False, set_weights=True,
             log=print) -> dict:
    """Enter Track A's scripted mock miner as a labelled challenger. Localnet only; the champion side still
    runs on real Chutes inference and is charged as usual."""
    from cadrecover.chain import bootstrap
    from cadrecover.validator.hill.mock import MOCK_STRATEGIES, HillRunner, mock_fingerprint
    if network not in ("local","test"):
        raise ValueError("the scripted mock miner runs on localnet or testnet only")
    if network=="test" and not allow_testnet_spend:
        raise ValueError("testnet hill spending requires explicit allow_testnet_spend")
    if strategy not in MOCK_STRATEGIES:
        raise ValueError(f"strategy must be one of {MOCK_STRATEGIES}")
    hotkey=bootstrap.wallet(wallet).hotkey.ss58_address
    import bittensor as bt
    from cadrecover.chain.setup import network_url
    with bt.Subtensor(network_url(network)) as sub:
        uid=sub.read("uid",netuid=bootstrap.load_state(network)["netuid"],hotkey_ss58=hotkey)
    if uid is None:
        raise HillUnavailable(f"{wallet} is not registered on {network}")
    with _hill_lock(network):
        con=db.connect()
        runner=HillRunner(ChutesRunner(con,total_cap=total_cap_usd,match_cap=max_spend_usd))
        try:
            fp=mock_fingerprint(strategy,hotkey)
            model={x.fingerprint:x for x in db.hill_models(con,network)}.get(fp)
            if model is None:
                model=Model(fingerprint=fp,name=f"{strategy} (mock miner)",source="mock",base_model=strategy,
                            hotkey=hotkey,uid=uid,submitted_at=now(),status="submitted")
                detail="scripted demo miner: reads drawn values from the validator's private record; not a model"
                db.model_status(con,model,"submitted",detail=detail,network=network)
                db.model_status(con,model,"prechecked",detail="localnet mock; no weights to check",network=network)
                db.model_status(con,model,"queued",network=network)
            if model.status=="champion":
                raise HillUnavailable("the mock miner already holds the hill")
            result=run_match(con,model,runner,tasks_per_match=tasks_per_match,margin=margin,network=network,log=log)
            weights=submit_champion_weights(con,network=network,log=log) if set_weights else None
            spent=runner.budget.totals()
            log(f"[hill] Chutes spent/reserved total USD {spent:.6f} (cap {total_cap_usd:.2f})")
            return {"match":result.model_dump(mode="json"),"weights":weights,"spend_usd":spent}
        finally:
            runner.close()
            con.close()
