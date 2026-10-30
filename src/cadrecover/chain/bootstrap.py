"""Put CADRecover on a local chain (owner: agent B). Idempotent: re-running skips finished steps.

  fund dev wallets from //Alice (localnet only) -> register the subnet (owner) -> StartCall
  -> burn-register validator + miners -> stake on the validator (permit) -> save chain.json

Every step is an SDK intent: planned, executed, and read back. State lives in
~/.cadrecover/chain.json so the validator, miners and auditor share one netuid.
"""

from __future__ import annotations

import json
import time

import bittensor as bt
from bittensor.keyfiles import Keypair

from cadrecover import paths
from cadrecover.chain.setup import WALLET_NAMES, network_url

STATE_FILE = paths.HOME / "chain.json"
FUNDING = {"owner": 3000.0, "validator": 2000.0}  # TAO; miners get MINER_FUNDING each
MINER_FUNDING = 100.0
VALIDATOR_STAKE = 100.0  # a new subnet's AMM pool is thin: 1000 TAO fails slippage protection
DRAND_GENESIS, DRAND_PERIOD = 1692803367, 3  # drand quicknet, which commit-reveal timelocks against
DRAND_MAX_LAG = 100  # rounds (~5 min)


class ChainError(RuntimeError):
    pass


def load_state(network: str = "local") -> dict:
    # Keep testnet isolated from local bootstrap; never create or register neurons here.
    network_url(network)
    file = STATE_FILE if network == "local" else paths.HOME / "chain-test.json"
    state = json.loads(file.read_text()) if file.exists() else {}
    if network == "test" and state:
        state.setdefault("neurons", {}).setdefault("validator", {
            "uid": 0, "hotkey": state["owner_hotkey"]})
    return state


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=1))


def wallet(name: str) -> bt.Wallet:
    return bt.Wallet(name, "default", path=str(paths.WALLETS))


def _ok(result, what: str):
    if not result.success:
        err = result.error
        raise ChainError(f"{what} failed: {getattr(err, 'code', '')} {getattr(err, 'message', err)}")
    return result


def _event(result, name: str):
    for e in result.events or []:
        if e.get("event_id") == name:
            return e.get("attributes")
    return None


def _first_int(attrs) -> int | None:
    """NetworkAdded decodes as a tuple (netuid, mechanism) or a dict, depending on metadata."""
    if isinstance(attrs, dict):
        attrs = attrs.get("netuid", next(iter(attrs.values()), None))
    if isinstance(attrs, (list, tuple)):
        attrs = attrs[0] if attrs else None
    return int(attrs) if attrs is not None else None


def owned_subnet(sub, owner_coldkey: str) -> int | None:
    """Recover our netuid after an interrupted run: the newest subnet whose owner is our owner coldkey."""
    for info in sorted(sub.read("subnets"), key=lambda s: -s.netuid):
        if info.netuid == 0:
            continue
        if sub.query(bt.storage.SubtensorModule.SubnetOwner, [info.netuid]) == owner_coldkey:
            return info.netuid
    return None


def drand_lag(sub) -> int:
    """How many drand rounds the chain's beacon is behind real time. Timelocked weight commits only
    reveal once the chain stores the pulse for their reveal round; a stalled beacon means they expire."""
    last = int(sub.query(bt.storage.Drand.LastStoredRound, []) or 0)
    return int((time.time() - DRAND_GENESIS) // DRAND_PERIOD) + 1 - last


def set_commit_reveal(sub, netuid: int, enabled: bool) -> None:
    """Owner hyperparameter. Only bootstrap (localnet) calls this."""
    call = bt.calls.AdminUtils.sudo_set_commit_reveal_weights_enabled(netuid=netuid, enabled=enabled)
    for _ in range(30):  # admin calls are refused inside the protected window around each epoch
        res = sub.submit_call(call, wallet("owner"))
        if res.success or "protected weights window" not in str(getattr(res.error, "message", res.error)):
            break
        time.sleep(1)
    _ok(res, "set commit_reveal_weights_enabled")


def bootstrap(network: str = "local", log=print) -> dict:
    if network != "local":
        raise ChainError("bootstrap funds wallets from //Alice and only runs on the local chain; "
                         "on testnet, fund and register by hand (see notes/agent-b.md)")
    state = load_state()
    state.setdefault("network", network)
    sub = bt.Subtensor(network_url(network))
    alice = Keypair.create_from_uri("//Alice")

    # 1. funding
    for name in WALLET_NAMES:
        w = wallet(name)
        want = FUNDING.get(name, MINER_FUNDING)
        have = sub.balances.get(w.coldkeypub.ss58_address).tao
        if have < want / 2:
            _ok(sub.execute(bt.Transfer(dest_ss58=w.coldkeypub.ss58_address, amount_tao=want), alice), f"fund {name}")
            log(f"funded {name}: {sub.balances.get(w.coldkeypub.ss58_address)}")

    # 2. subnet
    owner = wallet("owner")
    if "netuid" not in state:
        netuid = owned_subnet(sub, owner.coldkeypub.ss58_address)
        if netuid is not None:
            log(f"found our existing subnet: netuid {netuid}")
        else:
            cost = sub.read("subnet_registration_cost")
            log(f"subnet registration cost: {cost}")
            res = _ok(sub.execute(bt.RegisterSubnet(hotkey_ss58=owner.hotkey.ss58_address), owner), "register subnet")
            netuid = _first_int(_event(res, "NetworkAdded"))
            if netuid is None:
                raise ChainError(f"no NetworkAdded event in the result: {[e.get('event_id') for e in res.events]}")
        state["netuid"] = netuid
        state["registered_at_block"] = sub.block
        save_state(state)
        log(f"registered subnet netuid {netuid}")
    netuid = state["netuid"]

    # 3. start call (owner), once the chain allows it
    if not state.get("started"):
        sched = sub.read("subnet_start_schedule", netuid=netuid)
        earliest = (sched or {}).get("earliest_start_block") if isinstance(sched, dict) else None
        while earliest is not None and sub.block < earliest:
            log(f"waiting for start_call: block {sub.block} < {earliest}")
            time.sleep(2)
        res = sub.execute(bt.StartCall(netuid=netuid), owner)
        if not res.success and "already" not in str(res.error).lower():
            _ok(res, "start call")
        state["started"] = True
        save_state(state)
        log("subnet started")

    # 4. neurons
    state.setdefault("neurons", {})
    for name in ["validator"] + [n for n in WALLET_NAMES if n.startswith("miner")]:
        w = wallet(name)
        uid = sub.read("uid", hotkey_ss58=w.hotkey.ss58_address, netuid=netuid)
        if uid is None:
            # The SDK forces the MEV shield for BurnedRegister, and this single-node localnet never
            # decrypts shielded extrinsics ("not included before its era expired"). On localnet only,
            # submit the raw call in the clear via the SDK's escape hatch; testnet keeps the intent.
            call = bt.calls.SubtensorModule.burned_register(netuid=netuid, hotkey=w.hotkey.ss58_address)
            _ok(sub.submit_call(call, w), f"register {name}")
            uid = sub.read("uid", hotkey_ss58=w.hotkey.ss58_address, netuid=netuid)
            log(f"registered {name} as uid {uid}")
        state["neurons"][name] = {"uid": uid, "hotkey": w.hotkey.ss58_address}
    save_state(state)

    # 5. validator stake -> permit
    v = wallet("validator")
    if not state.get("validator_staked"):
        # localnet only: accept the thin pool's slippage (no real value at stake here)
        _ok(sub.execute(bt.AddStake(hotkey_ss58=v.hotkey.ss58_address, netuid=netuid, amount_tao=VALIDATOR_STAKE,
                                    slippage_protection=False), v), "stake validator")
        state["validator_staked"] = True
        save_state(state)
        log(f"staked {VALIDATOR_STAKE} TAO on the validator")

    # 6. commit-reveal needs a live drand beacon. This localnet image's beacon is stalled (its last
    #    stored round stays fixed), so commits expire unrevealed. Localnet only: turn commit-reveal off
    #    and record why; testnet keeps it on and the round records committed -> revealed receipts.
    lag = drand_lag(sub)
    state["drand_lag_rounds"] = lag
    if lag > DRAND_MAX_LAG and sub.read("commit_reveal_enabled", netuid=netuid):
        set_commit_reveal(sub, netuid, False)
        state["commit_reveal_note"] = (f"disabled on localnet: drand beacon {lag} rounds behind real time, "
                                       "timelocked commits cannot reveal")
        log(f"commit-reveal off: {state['commit_reveal_note']}")

    # readback: what the chain says about our neurons
    mg = sub.subnets.metagraph(netuid=netuid, commitments=False)
    state["metagraph"] = {n.uid: {"hotkey": n.hotkey, "validator_permit": n.validator_permit,
                                  "block_at_registration": n.block_at_registration,
                                  "total_stake": str(n.total_stake)} for n in mg.neurons}
    state["commit_reveal_enabled"] = sub.read("commit_reveal_enabled", netuid=netuid)
    state["tempo"] = mg.tempo
    save_state(state)
    return state
