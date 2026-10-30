"""Engine commitments (owner: agent B). Each miner commits the image ID of its engine on-chain,
signed by its hotkey, before it earns; the auditor re-runs exactly that image.

Payload (Raw bytes, at most 128): {"e": "sha256:<64 hex>", "s": "<strategy>@<version>"}.
Written with Commitments.set_commitment through the SDK's raw-call path; read back per hotkey.
"""

from __future__ import annotations

import json

import bittensor as bt

from cadrecover.chain.bootstrap import ChainError, load_state, wallet
from cadrecover.chain.setup import network_url

MAX_RAW = 128


def encode(engine_digest: str, strategy: str) -> bytes:
    if not engine_digest.startswith("sha256:") or len(engine_digest) != 71:
        raise ValueError(f"engine digest must be a docker image ID 'sha256:<64 hex>', got {engine_digest!r}")
    raw = json.dumps({"e": engine_digest, "s": strategy}, separators=(",", ":")).encode()
    if len(raw) > MAX_RAW:
        raise ValueError(f"commitment is {len(raw)} bytes; the chain takes at most {MAX_RAW}")
    return raw


def decode(value) -> dict | None:
    """Accept what the read returns (str, bytes, or a {"fields": [...]} structure) -> {"e", "s"} or None."""
    if value is None:
        return None
    if hasattr(value, "data") and not isinstance(value, (bytes, bytearray, str, dict)):  # Commitment(block, data, ...)
        d = decode(value.data)
        return {**d, "block": getattr(value, "block", None)} if d else None
    if isinstance(value, dict) and "commitment" in value:  # the SDK's decoded read row
        return decode(value["commitment"])
    if isinstance(value, dict):
        for f in value.get("fields") or []:
            f = f[0] if isinstance(f, (list, tuple)) and f else f
            if isinstance(f, dict):
                for k, v in f.items():
                    if k.startswith("Raw"):
                        return decode(bytes.fromhex(v[2:]) if isinstance(v, str) and v.startswith("0x") else v)
        return None
    if isinstance(value, (bytes, bytearray)):
        value = value.decode(errors="replace")
    if isinstance(value, str):
        if value.startswith("0x"):
            try:
                value = bytes.fromhex(value[2:]).decode()
            except ValueError:
                return None
        try:
            d = json.loads(value)
        except ValueError:
            return None
        if isinstance(d, dict) and "e" in d and "k" not in d:
            return d
        if isinstance(d, dict) and d.get("k") == "m":
            try:
                encode_model(d["r"], d["v"], d["f"])
            except (KeyError, ValueError, TypeError):
                return None
            return d
        return None
    return None


def commit_engine(wallet_name: str, engine_digest: str, strategy: str, network: str = "local") -> dict:
    raw = encode(engine_digest, strategy)
    state = load_state(network)
    w = wallet(wallet_name)
    info = {"fields": [[{f"Raw{len(raw)}": "0x" + raw.hex()}]]}
    with bt.Subtensor(network_url(network)) as sub:
        res = sub.submit_call(bt.calls.Commitments.set_commitment(netuid=state["netuid"], info=info), w,
                              signer="hotkey")  # the pallet checks the hotkey is registered
        if not res.success:
            raise ChainError(f"set_commitment {wallet_name}: {getattr(res.error, 'message', res.error)}")
        back = read_commitment(w.hotkey.ss58_address, network, sub=sub)
    if not back or back["e"] != engine_digest:
        raise ChainError(f"commitment readback mismatch for {wallet_name}: {back}")
    return {"wallet": wallet_name, "hotkey": w.hotkey.ss58_address, **back}


def read_commitment(hotkey: str, network: str = "local", sub=None) -> dict | None:
    state = load_state(network)
    if sub is None:
        with bt.Subtensor(network_url(network)) as s:
            return decode(s.read("commitment", netuid=state["netuid"], hotkey_ss58=hotkey))
    return decode(sub.read("commitment", netuid=state["netuid"], hotkey_ss58=hotkey))

def encode_model(repo: str, revision: str, fingerprint: str) -> bytes:
    import re
    if not isinstance(repo,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise ValueError("repo must be owner/model")
    if not isinstance(revision,str) or not re.fullmatch(r"[a-fA-F0-9]{40}",revision):
        raise ValueError("revision must be a full 40-hex commit")
    if not isinstance(fingerprint,str) or not re.fullmatch(r"[a-f0-9]{16}|[a-f0-9]{64}",fingerprint):
        raise ValueError("fingerprint must be 16 or 64 hex characters")
    raw=json.dumps({"k":"m","r":repo,"v":revision.lower(),"f":fingerprint[:16]},
                   separators=(",",":")).encode("utf-8")
    if len(raw)>MAX_RAW:
        raise ValueError(f"model commitment is {len(raw)} bytes; maximum is {MAX_RAW}")
    return raw


def commit_model(wallet_name: str, repo: str, revision: str, fingerprint: str, network="local") -> dict:
    raw=encode_model(repo,revision,fingerprint)
    state=load_state(network)
    if not state:
        raise ChainError(f"missing {network} chain state")
    w=wallet(wallet_name)
    info={"fields":[[{f"Raw{len(raw)}":"0x"+raw.hex()}]]}
    with bt.Subtensor(network_url(network)) as sub:
        res=sub.submit_call(bt.calls.Commitments.set_commitment(netuid=state["netuid"],info=info),
                            w,signer="hotkey")
        if not res.success:
            raise ChainError("model commitment rejected by chain")
        back=read_commitment(w.hotkey.ss58_address,network,sub=sub)
    expected=json.loads(raw)
    if not back or any(back.get(k)!=v for k,v in expected.items()) or back.get("block") is None:
        raise ChainError("model commitment readback mismatch or missing commit block")
    return {"wallet":wallet_name,"hotkey":w.hotkey.ss58_address,**back}
