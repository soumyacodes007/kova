"""One validator round (owner: agent B):

  challenge -> signed dispatch to every miner -> poll until done or deadline
  -> sandboxed rebuild + evaluation of every submission -> SQLite + events
  -> standings -> proposed weight batch -> retire the challenge.

Weights are only *proposed* here; Phase 6 submits them on-chain and reads them back.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import bittensor as bt
import httpx

from cadrecover import paths
from cadrecover.challenges.pipeline import new_challenge
from cadrecover.evaluation.score import load_private, score_source
from cadrecover.protocol import QUALITY_FLOOR, Evaluation, JobRequest, SetScore, WeightBatch
from cadrecover.storage import db
from cadrecover.validator import aggregate, artifacts, client, discovery

POLL_S = 1.0


def _zero_eval(challenge_id: str, job_id: str, hotkey: str, sets, reason: str) -> Evaluation:
    return Evaluation(challenge_id=challenge_id, job_id=job_id, miner_hotkey=hotkey, failure_class="miner",
                      failure_reason=reason,
                      sets=[SetScore(index=s.index, values=s.values, valid=False, critical_ok=False, geometry=0,
                                     dimensions=0) for s in sets])


async def _collect(miners, wallet, jobs: dict[str, JobRequest], deadline: datetime, con, run_id, log) -> dict:
    """Dispatch to every miner, then poll until each is terminal or the deadline passes."""
    outcome: dict[str, dict] = {}
    store = bt.http_auth.InMemoryNonceStore()
    async with httpx.AsyncClient(timeout=15) as http:
        for m in miners:
            job = jobs[m.hotkey]
            try:
                await client.dispatch(http, m.url, wallet, m.hotkey, job)
                db.set_assignment(con, job.job_id, "sent")
                db.add_event(con, "job.sent", {"uid": m.uid, "job_id": job.job_id}, run_id)
            except Exception as e:  # noqa: BLE001 - unreachable miner = miner failure
                outcome[m.hotkey] = {"status": "failed", "error": f"dispatch: {e}"}
                db.set_assignment(con, job.job_id, "failed")
                db.add_event(con, "job.dispatch_failed", {"uid": m.uid, "error": str(e)[:200]}, run_id)
        pending = [m for m in miners if m.hotkey not in outcome]
        while pending and datetime.now(timezone.utc) < deadline:
            await asyncio.sleep(POLL_S)
            for m in list(pending):
                job = jobs[m.hotkey]
                try:
                    st = await client.poll(http, m.url, wallet, m.hotkey, job.job_id, store)
                except Exception as e:  # noqa: BLE001
                    log(f"  poll uid {m.uid}: {e}")
                    continue
                if st.status == "done":
                    outcome[m.hotkey] = {"status": "done", "result": st.result}
                elif st.status == "failed":
                    outcome[m.hotkey] = {"status": "failed", "error": st.error}
                else:
                    continue
                pending.remove(m)
                db.add_event(con, f"job.{st.status}", {"uid": m.uid, "job_id": job.job_id,
                                                       "error": st.error}, run_id)
        for m in pending:
            outcome[m.hotkey] = {"status": "timeout", "error": "no result before the deadline"}
            db.add_event(con, "job.timeout", {"uid": m.uid, "job_id": jobs[m.hotkey].job_id}, run_id)
    return outcome


def run_round(*, family: str = "plate", deadline_s: int = 180, network: str = "local", netuid: int = 0,
              artifact_port: int = 8790, log=print) -> dict:
    con = db.connect()
    wallet = bt.Wallet("validator", "default", path=str(paths.WALLETS))
    miners = discovery.static_miners()
    server, base_url = artifacts.serve(port=artifact_port)
    try:
        log(f"[round] creating {family} challenge …")
        ch = new_challenge(family=family)
        challenge_id = ch["challenge_id"]
        public = db.get_public_challenge(con, challenge_id)
        private_sets = load_private(challenge_id).sets
        run_id = "run_" + uuid.uuid4().hex[:10]
        deadline = datetime.now(timezone.utc) + timedelta(seconds=deadline_s)
        db.create_run(con, run_id, challenge_id, deadline)
        db.add_event(con, "run.started", {"challenge_id": challenge_id, "miners": len(miners),
                                          "deadline_s": deadline_s}, run_id)
        log(f"[round] {run_id}: challenge {challenge_id} · {len(miners)} miners · deadline {deadline_s}s")

        jobs: dict[str, JobRequest] = {}
        for m in miners:
            db.upsert_miner(con, m.hotkey, m.registered_at_block, m.uid, m.label)
            job_id = f"{run_id}-uid{m.uid}"
            db.add_assignment(con, job_id, run_id, m.hotkey, m.registered_at_block, m.uid)
            jobs[m.hotkey] = JobRequest(job_id=job_id, challenge=public, deadline_at=deadline,
                                        drawing_url=f"{base_url}/{public.drawing.path}")

        db.set_run_status(con, run_id, "collecting")
        outcome = asyncio.run(_collect(miners, wallet, jobs, deadline, con, run_id, log))

        db.set_run_status(con, run_id, "evaluating")
        results = []
        for m in miners:
            job_id = jobs[m.hotkey].job_id
            o = outcome[m.hotkey]
            if o["status"] == "done":
                res = o["result"]
                db.save_submission(con, job_id, res.model_dump_json(), res.source_sha256)
                db.set_assignment(con, job_id, "done")
                ev = score_source(challenge_id, res.source, job_id=job_id, miner_hotkey=m.hotkey,
                                  glb_dir=paths.RUNTIME / "runs" / run_id / f"uid{m.uid}")
            else:
                db.set_assignment(con, job_id, "timeout" if o["status"] == "timeout" else "failed")
                ev = _zero_eval(challenge_id, job_id, m.hotkey, private_sets, o["error"] or o["status"])
            db.save_evaluation(con, ev)
            q = None if ev.failure_class == "validator_outage" else ev.quality
            db.add_event(con, "job.evaluated", {"uid": m.uid, "job_id": job_id, "quality": q,
                                                "failure_class": ev.failure_class,
                                                "sets": [round(100 * s.q, 1) for s in ev.sets]}, run_id)
            results.append({"uid": m.uid, "label": m.label, "status": o["status"], "quality": q,
                            "failure_class": ev.failure_class,
                            "sets": [round(100 * s.q, 1) for s in ev.sets],
                            "first_failure": next((f"s{s.index}: {s.failed_checks[0].name}" for s in ev.sets
                                                   if s.failed_checks), None)})
            log(f"  uid {m.uid:<3} {m.label or '':<22} {o['status']:<8} Q {'—' if q is None else f'{q:5.1f}'}  "
                f"sets {[round(100 * s.q) for s in ev.sets]}")

        db.set_run_status(con, run_id, "done")
        db.retire_challenge(con, challenge_id, "round finished; ground truth may be revealed")

        table = aggregate.standings(con)
        weights = {s.uid: s.weight for s in table if s.weight > 0}
        batch = WeightBatch(batch_id="wb_" + uuid.uuid4().hex[:10], network=network, netuid=netuid,
                            validator_hotkey=wallet.hotkey.ss58_address, floor=QUALITY_FLOOR,
                            mean_quality={s.hotkey: round(s.mean_quality, 3) for s in table},
                            samples={s.hotkey: s.samples for s in table}, weights=weights)
        state = "proposed" if weights else "skipped_no_qualifier"
        db.save_weight_batch(con, batch, state)
        db.add_event(con, "weights.proposed" if weights else "weights.no_update", {"batch_id": batch.batch_id,
                     "weights": weights}, run_id)
        log(f"[round] weights {state}: {weights or 'nobody above the floor (no update)'}")
        return {"run_id": run_id, "challenge_id": challenge_id, "results": results, "weight_batch": batch.batch_id,
                "weights_state": state, "weights": weights}
    finally:
        server.shutdown()
