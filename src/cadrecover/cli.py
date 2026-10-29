"""cadrecover command line (owner: agent C; commands added by the phase that needs them).

  cadrecover setup wallets                      # [B, phase 1] dev wallets (local/test only)
  cadrecover chain heartbeat [--network local]  # [B, phase 1] local chain produces blocks
  cadrecover challenge new [--family plate] [--seed N]   # [A, phase 2] hidden part + drawing
  cadrecover challenge show ID                  # [A, phase 2] public record + where the drawing is
"""

from __future__ import annotations

import argparse
import json
import sys


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

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
