"""cadrecover command line (owner: agent C; commands added by the phase that needs them).

  cadrecover setup wallets                      # [B, phase 1] dev wallets (local/test only)
  cadrecover chain heartbeat [--network local]  # [B, phase 1] local chain produces blocks
  cadrecover chain bootstrap                    # [B, phase 6] subnet + neurons + validator stake (local)
  cadrecover chain serve-axon --wallet W --port P   # [B, phase 6] publish a miner endpoint
  cadrecover chain weights                      # [B, phase 6] the validator's on-chain weights + pending commits
  cadrecover chain commit-engine --wallet W --digest sha256:… --strategy S   # [B, phase 6] engine commitment
  cadrecover auditor run [--top N] [--hotkey H]  # [A, phase 7] re-run committed engines on hidden tasks
  cadrecover challenge new [--family plate] [--seed N]   # [A, phase 2] hidden part + drawing
  cadrecover challenge show ID                  # [A, phase 2] public record + where the drawing is
  cadrecover score my_part.py --task ID         # [A, phase 3] sandboxed rebuild at all 4 sets + breakdown
  cadrecover miner run --wallet W --strategy S --port P   # [C, phase 4] signed miner HTTP server
  cadrecover validator run [--rounds N]         # [B, phase 5] full rounds against discovered miners
  cadrecover leaderboard                        # [B, phase 5] standings and proposed weights
  cadrecover doctor [--json]                    # [C, phase 8] is this machine ready? ✓/✗ per check, exit 1 on failure
  cadrecover task sample [--family F] [--out D] # [C, phase 8] a practice drawing + public record (never private data)
  cadrecover status [--watch] [--json]          # [C, phase 8] chain, miners, latest run, weights, audits on one screen
  cadrecover events [--follow] [--last N]       # [C, phase 8] job/round/weight/audit events as they happen
  cadrecover api serve [--port 8000]            # [C, phase 8] read API on 127.0.0.1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def _setup_wallets(a) -> None:
    from cadrecover.chain.setup import create_dev_wallets

    _print(create_dev_wallets())


def _heartbeat(a) -> None:
    from cadrecover.chain.setup import chain_heartbeat

    out = chain_heartbeat(a.network, a.wait)
    _print(out)
    sys.exit(0 if out["producing"] else 1)


def _bootstrap(a) -> None:
    from cadrecover.chain.bootstrap import bootstrap

    _print(bootstrap(a.network))


def _serve_axon(a) -> None:
    from cadrecover.chain.neurons import serve_axon

    _print(serve_axon(a.wallet, a.port, ip=a.ip, network=a.network))


def _chain_weights(a) -> None:
    from cadrecover.chain.neurons import read_weights

    _print(read_weights(a.network))


def _commit_engine(a) -> None:
    from cadrecover.chain.commitments import commit_engine

    _print(commit_engine(a.wallet, a.digest, a.strategy, network=a.network))


def _logger(a):
    """Rich-styled log lines for the long-running commands; --plain keeps raw `print` (same text, no colour)."""
    from cadrecover import cli_logs

    return cli_logs.plain_logger() if getattr(a, "plain", False) else cli_logs.rich_logger()


def _auditor_run(a) -> None:
    from cadrecover.audit.auditor import run_audits

    out = run_audits(network=a.network, top=a.top, family=a.family, hotkeys=a.hotkey, log=_logger(a))
    if a.json:
        _print(out)


def _challenge_new(a) -> None:
    from cadrecover.challenges.pipeline import new_challenge

    _print(new_challenge(family=a.family, seed=a.seed, scan_look=not a.clean))


def _challenge_show(a) -> None:
    from cadrecover import paths
    from cadrecover.storage import db

    pub = db.get_public_challenge(db.connect(), a.challenge_id)
    if pub is None:
        sys.exit(f"no challenge {a.challenge_id}")
    _print({"public": pub.model_dump(mode="json"), "drawing_png": str(paths.PUBLIC / pub.drawing.path)})


def _score(a) -> None:
    import uuid

    from cadrecover.evaluation.score import score_source

    ev = score_source(a.task, a.file.read_text(), job_id=f"local-{uuid.uuid4().hex[:8]}", miner_hotkey="local")
    if a.json:
        _print(ev.model_dump(mode="json"))
        return
    print(f"task {a.task}  ·  scoring v{ev.scoring_version}  ·  failure class: {ev.failure_class}")
    if ev.failure_class == "validator_outage":
        print(f"validator outage (not your fault): {ev.failure_reason}")
        sys.exit(2)
    print(f"{'set':<4}{'what':<22}{'V':>3}{'C':>3}{'G':>8}{'D':>7}{'Q_s':>7}")
    for s in ev.sets:
        what = "as drawn" if s.index == 0 else "hidden edit " + str(s.index)
        print(f"s{s.index:<3}{what:<22}{int(s.valid):>3}{int(s.critical_ok):>3}{s.geometry:>8.3f}{s.dimensions:>7.2f}"
              f"{100 * s.q:>7.1f}")
        for fc in s.failed_checks[:4]:
            print(f"      ✗ {fc.name}: {fc.message}")
        if len(s.failed_checks) > 4:
            print(f"      … {len(s.failed_checks) - 4} more")
    print(f"Q = {ev.quality:.1f}")


def _miner_run(a) -> None:
    import bittensor as bt
    import uvicorn

    from cadrecover import paths
    from cadrecover.miner import strategies
    from cadrecover.miner.server import create_app

    wallet = bt.Wallet(a.wallet, "default", path=str(paths.WALLETS))
    allowed = set(a.validator) if a.validator else None
    app = create_app(wallet, strategies.get(a.strategy), allowed_validators=allowed)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


def _validator_run(a) -> None:
    from cadrecover.validator.round import run_round

    log = _logger(a)
    for i in range(a.rounds):
        out = run_round(family=a.family, deadline_s=a.deadline, network=a.network, static=a.static,
                        reveal_wait_s=a.reveal_wait, log=log)
        if a.json:
            _print(out)


def _leaderboard(a) -> None:
    from cadrecover.storage import db
    from cadrecover.validator.aggregate import standings

    table = standings(db.connect())
    if not table:
        print("no evaluations yet")
        return
    print(f"{'uid':>4}  {'miner':<22}{'samples':>8}{'mean Q':>9}{'weight':>9}")
    for s in table:
        print(f"{s.uid:>4}  {(s.label or s.hotkey[:10]):<22}{s.samples:>8}{s.mean_quality:>9.1f}{s.weight:>9.3f}")


def _doctor(a) -> None:
    from cadrecover import doctor

    checks = doctor.run_checks(a.network)
    if a.json:
        print(doctor.to_json(checks))
    else:
        doctor.render(checks)
    sys.exit(doctor.exit_code(checks))


def _task_sample(a) -> None:
    from cadrecover.cli_task import write_sample

    out = write_sample(a.family, a.out)
    if a.json:
        _print(out)
        return
    print(f"practice task {out['challenge_id']} ({out['family']})")
    print(f"  drawing        {out['drawing_png']}")
    print(f"  public record  {out['public_record']}")
    print("The record lists parameter names, ranges and edit rules, never their values: read the values off the drawing.")
    print("Write build_part(overrides) -> a build123d part, then check it with `cadrecover score my_part.py --task "
          f"{out['challenge_id']}` on this machine.")


def _status(a) -> None:
    from cadrecover import status

    if a.watch:
        status.watch(a.network, a.interval, chain=not a.no_chain)
        return
    data = status.collect(a.network, chain=not a.no_chain)
    if a.json:
        _print(data)
        return
    from rich.console import Console

    Console().print(status.render(data))


def _events(a) -> None:
    from cadrecover import status

    try:
        status.follow_events(follow=a.follow, last=a.last, interval=1.0)
    except KeyboardInterrupt:
        pass


def _api_serve(a) -> None:
    import importlib.util

    if importlib.util.find_spec("cadrecover.api.app") is None:
        sys.exit("cadrecover.api.app does not exist yet (phase 8 API is still being written)")
    import uvicorn

    # Loopback only: the demo never exposes a port beyond this machine.
    uvicorn.run("cadrecover.api.app:create_app", factory=True, host="127.0.0.1", port=a.port, log_level="info")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="cadrecover")
    cmds = p.add_subparsers(dest="cmd", required=True)

    setup = cmds.add_parser("setup").add_subparsers(dest="sub", required=True)
    setup.add_parser("wallets", help="create dev wallets (local/test only)").set_defaults(fn=_setup_wallets)

    chain = cmds.add_parser("chain").add_subparsers(dest="sub", required=True)
    hb = chain.add_parser("heartbeat", help="check the chain produces blocks")
    hb.add_argument("--network", default="local", choices=["local", "test"])
    hb.add_argument("--wait", type=float, default=3.0)
    hb.set_defaults(fn=_heartbeat)
    bs = chain.add_parser("bootstrap", help="fund wallets, register subnet + neurons, stake validator (local)")
    bs.add_argument("--network", default="local", choices=["local", "test"])
    bs.set_defaults(fn=_bootstrap)
    sa = chain.add_parser("serve-axon", help="publish a miner's endpoint on chain (signed by its hotkey)")
    sa.add_argument("--wallet", required=True)
    sa.add_argument("--port", type=int, required=True)
    sa.add_argument("--ip", default=None, help="advertised IP (default: this host's LAN IP; the chain rejects loopback)")
    sa.add_argument("--network", default="local", choices=["local", "test"])
    sa.set_defaults(fn=_serve_axon)
    cw = chain.add_parser("weights", help="read the validator's weights and pending commits from chain")
    cw.add_argument("--network", default="local", choices=["local", "test"])
    cw.set_defaults(fn=_chain_weights)
    ce = chain.add_parser("commit-engine", help="commit a miner's engine image ID on chain (signed by its hotkey)")
    ce.add_argument("--wallet", required=True)
    ce.add_argument("--digest", required=True, help="docker image ID, sha256:<64 hex>")
    ce.add_argument("--strategy", required=True, help="label, e.g. mock-oracle@0.1.0")
    ce.add_argument("--network", default="local", choices=["local", "test"])
    ce.set_defaults(fn=_commit_engine)

    au = cmds.add_parser("auditor").add_subparsers(dest="sub", required=True)
    ar = au.add_parser("run", help="audit top miners: re-run their committed engine on hidden tasks")
    ar.add_argument("--top", type=int, default=2)
    ar.add_argument("--hotkey", action="append", help="audit this hotkey instead of the top miners (repeatable)")
    ar.add_argument("--family", default="plate")
    ar.add_argument("--network", default="local", choices=["local", "test"])
    ar.add_argument("--json", action="store_true")
    ar.add_argument("--plain", action="store_true", help="plain log lines (no colour)")
    ar.set_defaults(fn=_auditor_run)

    ch = cmds.add_parser("challenge").add_subparsers(dest="sub", required=True)
    new = ch.add_parser("new", help="generate a hidden part and its drawing")
    new.add_argument("--family", default="plate", choices=["plate", "flange"])
    new.add_argument("--seed", type=int, default=None, help="private seed (default: random)")
    new.add_argument("--clean", action="store_true", help="skip the scan look (crisp drawing)")
    new.set_defaults(fn=_challenge_new)
    show = ch.add_parser("show", help="print a challenge's public record")
    show.add_argument("challenge_id")
    show.set_defaults(fn=_challenge_show)

    sc = cmds.add_parser("score", help="score a build_part solution against a task, exactly as validators do")
    sc.add_argument("file", type=Path)
    sc.add_argument("--task", required=True, help="challenge id")
    sc.add_argument("--json", action="store_true")
    sc.set_defaults(fn=_score)

    mi = cmds.add_parser("miner").add_subparsers(dest="sub", required=True)
    mr = mi.add_parser("run", help="run a miner HTTP server")
    mr.add_argument("--wallet", required=True)
    mr.add_argument("--strategy", required=True)
    mr.add_argument("--host", default="127.0.0.1")
    mr.add_argument("--port", type=int, required=True)
    mr.add_argument("--validator", action="append", help="allowed validator hotkey (repeatable)")
    mr.set_defaults(fn=_miner_run)

    va = cmds.add_parser("validator").add_subparsers(dest="sub", required=True)
    vr = va.add_parser("run", help="run validator rounds")
    vr.add_argument("--rounds", type=int, default=1)
    vr.add_argument("--family", default="plate")
    vr.add_argument("--deadline", type=int, default=180)
    vr.add_argument("--json", action="store_true")
    vr.add_argument("--network", default="local", choices=["local", "test"])
    vr.add_argument("--static", action="store_true", help="use miners.json, propose weights only (no chain)")
    vr.add_argument("--reveal-wait", type=float, default=120, help="seconds to wait for on-chain readback")
    vr.add_argument("--plain", action="store_true", help="plain log lines (no colour)")
    vr.set_defaults(fn=_validator_run)

    cmds.add_parser("leaderboard", help="standings from stored evaluations").set_defaults(fn=_leaderboard)

    dr = cmds.add_parser("doctor", help="check this machine: envs, docker, images, chain, miners, ports (exit 1 on failure)")
    dr.add_argument("--network", default="local", choices=["local", "test"])
    dr.add_argument("--json", action="store_true")
    dr.set_defaults(fn=_doctor)

    tk = cmds.add_parser("task").add_subparsers(dest="sub", required=True)
    ts = tk.add_parser("sample", help="make a practice task: public record + drawing PNG only")
    ts.add_argument("--family", default="plate")
    ts.add_argument("--out", type=Path, default=Path("cadrecover-sample"), help="directory to write into")
    ts.add_argument("--json", action="store_true")
    ts.set_defaults(fn=_task_sample)

    st = cmds.add_parser("status", help="chain, miners, latest run, weight receipts and audits on one screen")
    st.add_argument("--network", default="local", choices=["local", "test"])
    st.add_argument("--watch", action="store_true", help="redraw until Ctrl-C")
    st.add_argument("--interval", type=float, default=2.0)
    st.add_argument("--no-chain", action="store_true", help="database only (skip the chain)")
    st.add_argument("--json", action="store_true")
    st.set_defaults(fn=_status)

    ev = cmds.add_parser("events", help="job / round / weight / audit events from the database (--follow to stream)")
    ev.add_argument("--follow", "-f", action="store_true")
    ev.add_argument("--last", type=int, default=10, help="how many recent events to show first")
    ev.set_defaults(fn=_events)

    ap = cmds.add_parser("api").add_subparsers(dest="sub", required=True)
    aps = ap.add_parser("serve", help="run the read API on 127.0.0.1")
    aps.add_argument("--port", type=int, default=8000)
    aps.set_defaults(fn=_api_serve)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
