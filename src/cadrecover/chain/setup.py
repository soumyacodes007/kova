"""Dev wallets and local-chain checks (owner: agent B).

Networks are `local` or `test` only in this build. Dev wallets are created
without passwords for unattended local runs; their mnemonics go to a 0600 file
under ~/.cadrecover/wallets, never into the repo. Don't put real funds on them.
"""

from __future__ import annotations

import os
import time

import bittensor as bt

from cadrecover import paths

NETWORKS = {"local": "ws://127.0.0.1:9944", "test": "test"}
WALLET_NAMES = ["owner", "validator", "miner1", "miner2", "miner3", "miner4", "miner5"]


def network_url(network: str) -> str:
    if network not in NETWORKS:
        raise ValueError(f"network must be one of {sorted(NETWORKS)} (never mainnet in this build)")
    return NETWORKS[network]


def create_dev_wallets(names: list[str] = WALLET_NAMES) -> dict[str, dict[str, str]]:
    """Create any missing wallets; return {name: {coldkey, hotkey}} ss58 addresses."""
    paths.ensure()
    mnemonic_file = paths.WALLETS / "MNEMONICS.local-dev.txt"

    def keep(name: str):
        def on_mnemonic(kind: str, words: str) -> None:
            fd = os.open(mnemonic_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a") as f:
                f.write(f"{name}.{kind}: {words}\n")
        return on_mnemonic

    out = {}
    for name in names:
        if (paths.WALLETS / name / "coldkey").exists():
            wallet = bt.Wallet(name, "default", path=str(paths.WALLETS))
        else:
            wallet = bt.wallets.create(name, "default", path=str(paths.WALLETS), use_password=False,
                                       on_mnemonic=keep(name))
        out[name] = {"coldkey": wallet.coldkeypub.ss58_address, "hotkey": wallet.hotkey.ss58_address}
    return out


def chain_heartbeat(network: str = "local", wait_s: float = 3.0) -> dict:
    """Read the head twice; a producing chain advances in between."""
    with bt.Subtensor(network_url(network)) as sub:
        first = sub.block
        time.sleep(wait_s)
        second = sub.block
        return {"network": network, "first": first, "second": second, "producing": second > first,
                "spec_version": sub.spec_version}
