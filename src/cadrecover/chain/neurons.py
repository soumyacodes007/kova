"""Neurons on chain (owner: agent B): miner endpoints, metagraph discovery, weights with readback.

Weights go through bt.SetWeights (plaintext or commit-reveal, chosen by the SDK).
Commit, reveal and incentive are separate states and are stored as separate
receipts; a commit-reveal row only appears in the `weights` read once revealed.
"""

from __future__ import annotations

import json
import subprocess

import bittensor as bt

from cadrecover.chain.bootstrap import load_state, wallet
from cadrecover.chain.setup import network_url
from cadrecover.validator.discovery import MinerEndpoint


def serve_axon(wallet_name: str, port: int, ip: str | None = None, network: str = "local") -> dict:
    """Publish a miner's endpoint (signed by its hotkey) and read it back from the metagraph."""
    state = load_state()
    netuid = state["netuid"]
    w = wallet(wallet_name)
    if ip is None:  # the chain rejects loopback; publish this host's first LAN IP
        ip = sorted(host_ips(), key=lambda a: (a.startswith("172."), a))[0]
    with bt.Subtensor(network_url(network)) as sub:
        res = sub.execute(bt.ServeAxon(netuid=netuid, ip=ip, port=port), w)
        if not res.success:
            raise RuntimeError(f"serve_axon {wallet_name}: {res.error}")
        mg = sub.subnets.metagraph(netuid=netuid, commitments=False)
        n = mg.by_hotkey(w.hotkey.ss58_address) if hasattr(mg, "by_hotkey") else \
            next(x for x in mg.neurons if x.hotkey == w.hotkey.ss58_address)
        return {"wallet": wallet_name, "uid": n.uid, "axon": str(n.axon)}


def host_ips() -> set[str]:
    """This machine's IPv4 addresses (Linux/WSL)."""
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout
        return set(out.split())
    except (OSError, subprocess.SubprocessError):
        return set()


def _axon_url(axon, local: set[str]) -> str | None:
    """http URL for an on-chain axon. The chain rejects loopback IPs, so same-machine miners
    publish this host's LAN IP while binding to 127.0.0.1 only; map those back to loopback.
    (Same-machine demo only: testnet peers need routable addresses.)"""
    if axon is None:
        return None
    text = str(axon)
    if not text or text.startswith("0.0.0.0") or text in ("None", ":0") or ":" not in text:
        return None
    ip, port = text.rsplit(":", 1)
    if ip in local:
        ip = "127.0.0.1"
    return f"http://{ip}:{port}"


def metagraph_miners(network: str = "local", *, exclude_hotkeys: set[str] | None = None,
                     labels: dict[str, str] | None = None) -> list[MinerEndpoint]:
    """Miners to query: registered neurons serving an axon, minus validators we exclude (e.g. ourselves)."""
    state = load_state()
    exclude = exclude_hotkeys or set()
    with bt.Subtensor(network_url(network)) as sub:
        mg = sub.subnets.metagraph(netuid=state["netuid"], commitments=False)
    out = []
    local = host_ips()
    for n in mg.neurons:
        url = _axon_url(n.axon, local)
        if url is None or n.hotkey in exclude:
            continue
        out.append(MinerEndpoint(hotkey=n.hotkey, uid=n.uid, registered_at_block=n.block_at_registration,
                                 url=url, label=(labels or {}).get(n.hotkey)))
    return sorted(out, key=lambda m: m.uid)


def submit_weights(weights: dict[int, float], network: str = "local", version_key: int = 0) -> dict:
    """Plan -> execute -> readback. Returns the receipt fields to store."""
    state = load_state()
    netuid = state["netuid"]
    v = wallet("validator")
    with bt.Subtensor(network_url(network)) as sub:
        uids = sorted(weights)
        intent = bt.SetWeights(netuid=netuid, uids=uids, weights=[weights[u] for u in uids], version_key=version_key)
        plan = sub.plan(intent, v)
        if not plan.ok:
            return {"state": "failed", "error": f"plan rejected: {plan.violations}", "block": sub.block}
        res = sub.execute(intent, v)
        block = sub.block
        if not res.success:
            return {"state": "failed", "error": f"{getattr(res.error, 'code', '')} {getattr(res.error, 'message', res.error)}",
                    "block": block}
        events = [e.get("event_id") for e in res.events or []]
        committed = any("Commit" in (e or "") for e in events) or bool(sub.read("commit_reveal_enabled", netuid=netuid))
        return {"state": "committed" if committed else "submitted", "block": block,
                "extrinsic": getattr(res, "extrinsic_id", None) or getattr(res, "block_hash", None),
                "events": events}


def read_weights(network: str = "local") -> dict:
    """The validator's on-chain weight row (revealed) and any pending timelocked commits."""
    state = load_state()
    netuid = state["netuid"]
    vuid = state["neurons"]["validator"]["uid"]
    with bt.Subtensor(network_url(network)) as sub:
        rows = sub.read("weights", netuid=netuid) or {}
        pending = sub.read("timelocked_weight_commits", netuid=netuid) or {}
        row = rows.get(vuid) or rows.get(str(vuid))
        mine = []
        vhot = state["neurons"]["validator"]["hotkey"]
        for epoch, entries in (pending.items() if isinstance(pending, dict) else []):
            for c in entries or []:
                if (c.get("hotkey") if isinstance(c, dict) else None) == vhot:
                    mine.append({"epoch": epoch, **{k: c.get(k) for k in ("commit_block", "reveal_round", "reveals_at")}})
        return {"block": sub.block, "revealed_row": {int(k): float(v) for k, v in (row or {}).items()},
                "pending_commits": json.loads(json.dumps(mine, default=str))}
