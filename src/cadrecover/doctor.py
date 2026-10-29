"""`cadrecover doctor`: is this machine ready to run the subnet? (owner: agent C)

Every check is read-only. Each returns a `Check`; `fail` makes the command exit non-zero,
`warn` is shown but does not. Checks that need the chain are skipped (and say why) when the
localnet is unreachable, so one outage does not bury the rest of the report.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from cadrecover import paths

SANDBOX_IMAGE = "cadrecover-sandbox:build123d-0.13.0"
ARTIFACT_PORT = 8790
API_PORT = 8000
DEFAULT_ENGINES = ["mock-oracle", "mock-noisy", "diag-constant", "diag-wrong-holes", "diag-crash"]

ENV_IMPORTS = {
    "services": "import bittensor, fastapi, httpx, pydantic, rich, uvicorn, cadrecover.protocol",
    "cad": "import build123d, cadrecover.protocol",
    "drawing": "import build123d, draftwright, pymupdf, cadrecover.protocol",
}


@dataclass
class Check:
    name: str
    status: str  # ok | fail | warn | skip
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "fail"


def _sh(cmd: list[str], timeout: float = 10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def port_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


# ------------------------------------------------------------------ individual checks


def check_env(env: str) -> Check:
    py = paths.env_python(env)
    name = f"env {env}"
    if not py.exists():
        return Check(name, "fail", f"{py} missing: run `make envs`")
    try:
        r = _sh([str(py), "-c", ENV_IMPORTS[env]], timeout=90)
    except subprocess.TimeoutExpired:
        return Check(name, "fail", "import timed out")
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["import failed"])[-1]
        return Check(name, "fail", last[:160])
    return Check(name, "ok", "imports its libraries")


def check_docker() -> Check:
    if not shutil.which("docker"):
        return Check("docker", "fail", "docker not on PATH")
    try:
        r = _sh(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=15)
    except subprocess.TimeoutExpired:
        return Check("docker", "fail", "daemon did not answer in 15 s")
    if r.returncode != 0:
        return Check("docker", "fail", "daemon not reachable")
    return Check("docker", "ok", f"server {r.stdout.strip()}")


def _image_id(ref: str) -> str | None:
    try:
        r = _sh(["docker", "image", "inspect", "--format", "{{.Id}}", ref])
    except (subprocess.TimeoutExpired, OSError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def check_sandbox_image() -> Check:
    iid = _image_id(SANDBOX_IMAGE)
    if iid:
        return Check("sandbox image", "ok", f"{SANDBOX_IMAGE} {iid[7:19]}")
    return Check("sandbox image", "fail", f"{SANDBOX_IMAGE} missing: docker build -t {SANDBOX_IMAGE} images/cad-worker")


def miner_labels() -> list[str]:
    try:
        from cadrecover.validator.discovery import MINERS_FILE

        labels = [m.get("label") for m in json.loads(MINERS_FILE.read_text())]
        labels = [x for x in labels if x]
        return list(dict.fromkeys(labels)) or DEFAULT_ENGINES
    except (OSError, ValueError):
        return DEFAULT_ENGINES


def check_engine_images() -> Check:
    labels = miner_labels()
    have, missing = [], []
    for s in labels:
        (have if _image_id(f"cadrecover-engine:{s}") else missing).append(s)
    if missing:
        return Check("engine images", "fail", f"missing {', '.join(missing)}: bash scripts/build-engines.sh {' '.join(missing)}")
    return Check("engine images", "ok", f"{len(have)} built ({', '.join(have)})")


def check_wallets() -> Check:
    missing = [n for n in ("owner", "validator", "miner1") if not (paths.WALLETS / n / "coldkey").exists()]
    if missing:
        return Check("dev wallets", "fail", f"missing {', '.join(missing)}: cadrecover setup wallets")
    return Check("dev wallets", "ok", str(paths.WALLETS))


def check_sqlite() -> Check:
    db = paths.DB
    try:
        if not db.exists():
            ok = os.access(db.parent, os.W_OK) if db.parent.exists() else os.access(paths.HOME, os.W_OK)
            return Check("sqlite", "ok" if ok else "fail", f"{db} will be created" if ok else f"{db.parent} not writable")
        con = sqlite3.connect(db, timeout=5)
        try:
            con.execute("BEGIN IMMEDIATE")
            con.rollback()
        finally:
            con.close()
        return Check("sqlite", "ok", f"{db} writable")
    except sqlite3.Error as e:
        return Check("sqlite", "fail", f"{db}: {e}")


def check_port(port: int, what: str, fatal: bool) -> Check:
    if port_listening(port):
        return Check(f"port {port}", "fail" if fatal else "warn", f"in use ({what})")
    return Check(f"port {port}", "ok", f"free ({what})")


def check_chain(network: str = "local") -> tuple[list[Check], dict]:
    """Chain-dependent checks; returns (checks, context for the miner check)."""
    from cadrecover.chain.bootstrap import STATE_FILE, load_state

    out: list[Check] = []
    ctx: dict = {"miners": None}
    if network == "local" and not port_listening(9944):
        out.append(Check("localnet", "fail", "ws://127.0.0.1:9944 not reachable: make localnet"))
        out.append(Check("chain.json", "skip", "needs the localnet"))
        return out, ctx
    try:
        from cadrecover.chain.setup import chain_heartbeat

        hb = chain_heartbeat(network, 1.5)
        out.append(Check("localnet", "ok" if hb["producing"] else "fail",
                         f"block {hb['first']} -> {hb['second']}" + ("" if hb["producing"] else " (not producing)")))
    except Exception as e:  # noqa: BLE001
        out.append(Check("localnet", "fail", f"{type(e).__name__}: {str(e)[:120]}"))
        return out, ctx

    state = load_state()
    if "netuid" not in state:
        out.append(Check("chain.json", "fail", f"{STATE_FILE} missing or without netuid: cadrecover chain bootstrap"))
        return out, ctx
    netuid = state["netuid"]
    out.append(Check("chain.json", "ok", f"netuid {netuid}, started={state.get('started')}, "
                     f"commit-reveal {'on' if state.get('commit_reveal_enabled') else 'off'}"))
    try:
        import bittensor as bt

        from cadrecover.chain.setup import network_url

        vhot = state["neurons"]["validator"]["hotkey"]
        with bt.Subtensor(network_url(network)) as sub:
            mg = sub.subnets.metagraph(netuid=netuid, commitments=False)
        v = next((n for n in mg.neurons if n.hotkey == vhot), None)
        if v is None:
            out.append(Check("validator permit", "fail", f"validator hotkey {vhot[:10]}… not registered on netuid {netuid}"))
        else:
            out.append(Check("validator permit", "ok" if v.validator_permit else "fail",
                             f"uid {v.uid}, stake {v.total_stake}" + ("" if v.validator_permit else " (no permit: stake the validator)")))
    except Exception as e:  # noqa: BLE001
        out.append(Check("validator permit", "fail", f"{type(e).__name__}: {str(e)[:120]}"))
    try:
        from cadrecover.chain.neurons import metagraph_miners

        labels = _labels_by_hotkey()
        ctx["miners"] = [(m.uid, labels.get(m.hotkey, ""), m.url)
                         for m in metagraph_miners(network, exclude_hotkeys={vhot})]
    except Exception as e:  # noqa: BLE001
        out.append(Check("metagraph miners", "fail", f"{type(e).__name__}: {str(e)[:120]}"))
    return out, ctx


def _labels_by_hotkey() -> dict[str, str]:
    try:
        from cadrecover.validator.discovery import static_miners

        return {m.hotkey: m.label or "" for m in static_miners()}
    except Exception:  # noqa: BLE001
        return {}


def check_miners(known: list[tuple[int, str, str]] | None) -> Check:
    """GET /v1/health on every miner axon from the metagraph (miners.json when there is no chain)."""
    import httpx

    source = "metagraph"
    if known is None:
        source = "miners.json"
        try:
            from cadrecover.validator.discovery import static_miners

            known = [(m.uid, m.label or "", m.url) for m in static_miners()]
        except Exception as e:  # noqa: BLE001
            return Check("miners", "fail", f"no miner list ({e}): bash scripts/run-miners.sh")
    if not known:
        return Check("miners", "fail", "no miner serving an axon: bash scripts/run-miners.sh")
    bad, good = [], []
    for uid, label, url in known:
        try:
            r = httpx.get(f"{url}/v1/health", timeout=3)
            (good if r.status_code == 200 else bad).append((uid, label, f"HTTP {r.status_code}"))
        except httpx.HTTPError as e:
            bad.append((uid, label, type(e).__name__))
    if bad:
        return Check("miners", "fail", f"{len(good)}/{len(known)} healthy via {source}; down: "
                     + ", ".join(f"uid {u} {l} ({why})" for u, l, why in bad))
    return Check("miners", "ok", f"{len(good)}/{len(known)} healthy via {source} ({', '.join(f'uid {u} {l}'.strip() for u, l, _ in good)})")


# ------------------------------------------------------------------ the whole report


def run_checks(network: str = "local") -> list[Check]:
    with ThreadPoolExecutor(max_workers=6) as pool:
        envs = [pool.submit(check_env, e) for e in ENV_IMPORTS]
        docker = pool.submit(check_docker)
        chain = pool.submit(check_chain, network)
        checks: list[Check] = [f.result() for f in envs]
        d = docker.result()
        checks.append(d)
        if d.ok:
            checks.append(check_sandbox_image())
            checks.append(check_engine_images())
        else:
            checks += [Check("sandbox image", "skip", "needs docker"), Check("engine images", "skip", "needs docker")]
        chain_checks, ctx = chain.result()
    checks.append(check_wallets())
    checks += chain_checks
    checks.append(check_miners(ctx["miners"]))
    checks.append(check_sqlite())
    checks.append(check_port(ARTIFACT_PORT, "artifact server, used during rounds", fatal=True))
    checks.append(check_port(API_PORT, "API; fine if `cadrecover api serve` is already running", fatal=False))
    return checks


MARK = {"ok": ("✓", "green"), "fail": ("✗", "bold red"), "warn": ("!", "yellow"), "skip": ("-", "dim")}


def render(checks: list[Check], console=None) -> None:
    from rich.console import Console
    from rich.markup import escape

    console = console or Console(highlight=False, soft_wrap=True)
    width = max(len(c.name) for c in checks)
    for c in checks:
        mark, style = MARK[c.status]
        console.print(f"[{style}]{mark}[/] {c.name:<{width}}  [dim]{escape(c.detail)}[/]")
    failed = [c for c in checks if c.status == "fail"]
    if failed:
        console.print(f"\n[bold red]{len(failed)} check(s) failed[/]")
    else:
        console.print("\n[bold green]all checks passed[/]")


def to_json(checks: list[Check]) -> str:
    return json.dumps([asdict(c) for c in checks], indent=1)


def exit_code(checks: list[Check]) -> int:
    return 1 if any(c.status == "fail" for c in checks) else 0

