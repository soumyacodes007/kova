"""Best-effort chain head for /v1/status (owner: agent C). Short timeout, cached, null when unreachable.

Reads ~/.cadrecover/chain.json for the network and netuid (public facts), then asks a *local* node for its
head over plain JSON-RPC/HTTP, so the API never imports bittensor or opens a websocket.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from cadrecover import paths
from cadrecover.api.models import ChainInfo

LOCAL_RPC = "http://127.0.0.1:9944"  # the dev node serves JSON-RPC over HTTP on its websocket port
TTL_S = 3.0


class ChainProbe:
    def __init__(self, state_file: Path | None, rpc: str | None, timeout_s: float = 1.0):
        self.state_file, self.rpc, self.timeout_s = state_file, rpc, timeout_s
        self._cache: tuple[float, ChainInfo] | None = None

    def _state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text()) if self.state_file and self.state_file.exists() else {}
        except (OSError, ValueError):
            return {}

    def _head(self, rpc: str) -> int | None:
        try:
            r = httpx.post(rpc, json={"id": 1, "jsonrpc": "2.0", "method": "chain_getHeader", "params": []},
                           timeout=self.timeout_s)
            return int(r.json()["result"]["number"], 16)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None

    def info(self) -> ChainInfo:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < TTL_S:
            return self._cache[1]
        st = self._state()
        rpc = self.rpc  # "auto" = the local node when the state file says `local`; None = never probe
        if rpc == "auto":
            rpc = LOCAL_RPC if st.get("network") == "local" else None
        block = self._head(rpc) if rpc else None
        validator = (st.get("neurons") or {}).get("validator") or {}
        if st.get("network") == "test" and not validator:
            validator = {"hotkey": st.get("owner_hotkey")}
        info = ChainInfo(network=st.get("network"), netuid=st.get("netuid"), validator_hotkey=validator.get("hotkey"),
                         commit_reveal_enabled=st.get("commit_reveal_enabled"), tempo=st.get("tempo"),
                         block=block, reachable=block is not None)
        self._cache = (now, info)
        return info


def default_state_file(network: str = "local") -> Path:
    if network not in ("local", "test"):
        raise ValueError("network must be local or test")
    return paths.HOME / ("chain.json" if network == "local" else "chain-test.json")
