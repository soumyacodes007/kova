"""Read model commitments without axon dependency. No miner registration or spend."""
from __future__ import annotations
import hashlib
import json

from cadrecover.chain import commitments
from cadrecover.chain.bootstrap import load_state, wallet
from cadrecover.chain.setup import network_url
from cadrecover.protocol.hill import Model
from cadrecover.storage import db
from cadrecover.validator.hill.match import now
from cadrecover.validator.hill.precheck import PrecheckError, precheck_model


def discover_model_commitments(network="local", *, con=None, log=print):
    import bittensor as bt
    network_url(network)
    own=con is None
    con=con or db.connect()
    state=load_state(network)
    found=[]
    try:
        with bt.Subtensor(network_url(network)) as sub:
            mg=sub.subnets.metagraph(netuid=state["netuid"],commitments=False)
            pending=[]
            for n in mg.neurons:
                raw=commitments.read_commitment(n.hotkey,network,sub=sub)
                if raw and raw.get("k")=="m" and raw.get("block") is not None:
                    pending.append((n,raw))
            # Metagraph UID order is not commit order. Earliest weights win even
            # when the later copier has a lower UID.
            for n,raw in sorted(pending,key=lambda pair:(int(pair[1]["block"]),pair[0].hotkey)):
                key=(network,n.hotkey,int(raw["block"]))
                if con.execute("SELECT 1 FROM hill_commitments WHERE network=? AND hotkey=? AND commit_block=?",key).fetchone():
                    continue
                # Submitted is a chain fact even if metadata resolution subsequently rejects it.
                db.add_event(con,"model.status",{"fingerprint":raw["f"],"status":"submitted",
                             "block":raw["block"],"detail":"model commitment observed; full fingerprint pending",
                             "hotkey":n.hotkey,"network":network})
                full=None
                error=None
                try:
                    checked=precheck_model(raw["r"],raw["v"])
                    full=checked.fingerprint
                    if full[:16]!=raw["f"]:
                        raise PrecheckError("committed fingerprint prefix does not match pinned weights")
                    earlier=next((m for m in db.hill_models(con,network) if m.fingerprint==full),None)
                    if earlier:
                        raise PrecheckError(f"same weights as {earlier.name}, committed later")
                    model=Model(fingerprint=full,name=raw["r"].rsplit("/",1)[-1],source="miner",
                                repo=raw["r"],revision=raw["v"],base_model=checked.base_model,
                                hotkey=n.hotkey,uid=n.uid,commit_block=raw["block"],submitted_at=now(),
                                status="submitted",hf_url=f"https://huggingface.co/{raw['r']}/tree/{raw['v']}",
                                fee={"amount_tao":0,"simulated":True} if network=="local" else None)
                    db.model_status(con,model,"submitted",block=raw["block"],network=network)
                    db.model_status(con,model,"prechecked",block=raw["block"],network=network)
                    db.model_status(con,model,"queued",detail="deploy disabled on this network",network=network)
                    found.append(model)
                    log(f"[hill] model submitted: {model.name} {full} block {raw['block']} -> queued (deploy disabled on this network)")
                except PrecheckError as exc:
                    error=str(exc)
                    db.add_event(con,"model.status",{"fingerprint":full or raw["f"],"status":"rejected",
                                 "block":raw["block"],"detail":error,"hotkey":n.hotkey,"commit_block":raw["block"],
                                 "commitment_rejection":True,"network":network})
                    log(f"[hill] rejected model commitment at block {raw['block']}: {error}")
                con.execute("INSERT INTO hill_commitments VALUES (?,?,?,?,?,?)",
                            (*key,json.dumps(raw),full,error))
                con.commit()
        return found
    finally:
        if own: con.close()


def submit_model(wallet_name: str, repo: str, revision: str, network="local", *, allow_testnet_spend=False):
    network_url(network)
    if network=="test" and not allow_testnet_spend:
        raise ValueError("testnet model commitment fees require explicit allow_testnet_spend")
    con=db.connect()
    try:
        checked=precheck_model(repo,revision)
        prior=next((m for m in db.hill_models(con,network) if m.fingerprint==checked.fingerprint),None)
        if prior:
            raise PrecheckError(f"same weights as {prior.name}, committed later")
        # Validate the 128-byte wire payload before any extrinsic fee.
        commitments.encode_model(repo,checked.revision,checked.fingerprint)
        result=commitments.commit_model(wallet_name,repo,checked.revision,checked.fingerprint,network)
        discovered=discover_model_commitments(network,con=con)
        row=con.execute("SELECT error FROM hill_commitments WHERE network=? AND hotkey=? AND commit_block=?",
                        (network,result["hotkey"],result["block"])).fetchone()
        stored=next((m for m in db.hill_models(con,network)
                     if m.fingerprint==checked.fingerprint and m.hotkey==result["hotkey"]
                     and m.commit_block==result["block"]),None)
        if not row or row["error"] or stored is None:
            raise PrecheckError(row["error"] if row and row["error"] else "watcher has not confirmed submitted model")
        return {**result,"fingerprint":checked.fingerprint,"commitment_block":result["block"],
                "fee":{"amount_tao":0.0,"simulated":True} if network=="local" else None,
                "status":"queued","detail":"deploy disabled on this network"}
    finally:
        con.close()
