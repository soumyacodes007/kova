"""cadrecover command line (owner: agent C; commands added by the phase that needs them).

  cadrecover setup wallets                      # [B, phase 1] dev wallets (local/test only)
  cadrecover chain heartbeat [--network local]  # [B, phase 1] local chain produces blocks
  cadrecover challenge new [--family plate] [--seed N]   # [A, phase 2] hidden part + drawing
  cadrecover challenge show ID                  # [A, phase 2] public record + where the drawing is
  cadrecover score my_part.py --task ID         # [A, phase 3] sandboxed rebuild at all 4 sets + breakdown
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

    ch = cmds.add_parser("challenge").add_subparsers(dest="sub", required=True)
    new = ch.add_parser("new", help="generate a hidden part and its drawing")
    new.add_argument("--family", default="plate", choices=["plate"])
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

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
