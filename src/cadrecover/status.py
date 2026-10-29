"""`cadrecover status`: one screen for the whole subnet (owner: agent C).

`collect()` gathers plain data (chain, miners, latest run, latest weight batch, latest audits)
from the chain and SQLite without writing anything; `render()` turns it into Rich tables.
The chain part degrades to "unreachable" instead of failing, so the screen still shows what
the database knows when the localnet is down.
"""

from __future__ import annotations

import json
import sqlite3
import time

from rich.console import Group
from rich.table import Table
from rich.text import Text

from cadrecover import paths
from cadrecover.cli_logs import q_style
from cadrecover.doctor import port_listening

MAX_AUDITS = 6


def _db() -> sqlite3.Connection | None:
    if not paths.DB.exists():
        return None
    con = sqlite3.connect(paths.DB, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=1")
    return con


def _rows(con, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.OperationalError:  # table not created yet
        return []


def _chain(network: str) -> dict:
    from cadrecover.chain.bootstrap import load_state

    state = load_state()
    out = {"network": network, "reachable": False, "block": None, "netuid": state.get("netuid"),
           "commit_reveal": state.get("commit_reveal_enabled"), "note": state.get("commit_reveal_note"),
           "tempo": state.get("tempo"), "axons": {}, "engines": {}}
    if network == "local" and not port_listening(9944):
        return out
    try:
        import bittensor as bt

        from cadrecover.chain.neurons import _axon_url, host_ips
        from cadrecover.chain.setup import network_url

        with bt.Subtensor(network_url(network)) as sub:
            out["block"] = sub.block
            if out["netuid"] is not None:
                mg = sub.subnets.metagraph(netuid=out["netuid"], commitments=False)
                local = host_ips()
                out["axons"] = {n.hotkey: _axon_url(n.axon, local) for n in mg.neurons}
                from cadrecover.chain.commitments import read_commitment

                for n in mg.neurons:  # the engine each miner committed, read back from chain
                    if out["axons"][n.hotkey]:
                        c = read_commitment(n.hotkey, network, sub=sub)
                        if c:
                            out["engines"][n.hotkey] = c["e"]
                out["validator_uid"] = next((n.uid for n in mg.neurons
                                             if n.hotkey == state.get("neurons", {}).get("validator", {}).get("hotkey")), None)
        out["reachable"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    return out


def collect(network: str = "local", chain: bool = True) -> dict:
    data: dict = {"chain": _chain(network) if chain else {"network": network, "reachable": None, "block": None,
                                                         "netuid": None, "axons": {}},
                  "miners": [], "run": None, "batch": None, "audits": []}
    con = _db()
    if con is None:
        return data
    try:
        axons = data["chain"].get("axons", {})
        uid_of = {}
        for r in _rows(con, """
            SELECT m.hotkey, m.uid, m.label, m.registered_at_block FROM miners m
            WHERE m.registered_at_block = (SELECT max(registered_at_block) FROM miners x WHERE x.hotkey = m.hotkey)
            ORDER BY m.uid"""):
            uid_of[r["hotkey"]] = r["uid"]
            stats = _rows(con, """
                SELECT e.quality, e.failure_class FROM evaluations e
                JOIN assignments a ON a.job_id = e.job_id
                WHERE a.miner_hotkey = ? AND a.registered_at_block = ? ORDER BY e.evaluated_at DESC""",
                          (r["hotkey"], r["registered_at_block"]))
            real = [s["quality"] for s in stats if s["failure_class"] != "validator_outage"]
            eng = _rows(con, "SELECT engine_digest, strategy_version FROM commitments WHERE hotkey = ? "
                             "ORDER BY block DESC LIMIT 1", (r["hotkey"],))
            data["miners"].append({
                "uid": r["uid"], "label": r["label"], "hotkey": r["hotkey"], "axon": axons.get(r["hotkey"]),
                "last_q": (real[0] or 0.0) if real else None, "samples": len(real),
                "mean_q": (sum(q or 0.0 for q in real) / len(real)) if real else None,
                "engine": data["chain"].get("engines", {}).get(r["hotkey"]) or (eng[0]["engine_digest"] if eng else None),
            })
        run = _rows(con, "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1")
        if run:
            r = run[0]
            ev = _rows(con, """SELECT a.uid, e.quality FROM assignments a LEFT JOIN evaluations e ON e.job_id = a.job_id
                               WHERE a.run_id = ?""", (r["run_id"],))
            qs = [x["quality"] for x in ev if x["quality"] is not None]
            data["run"] = {"run_id": r["run_id"], "challenge_id": r["challenge_id"], "status": r["status"],
                           "started_at": r["started_at"], "miners": len(ev), "evaluated": len(qs),
                           "best_q": max(qs) if qs else None, "mean_q": sum(qs) / len(qs) if qs else None}
        batch = _rows(con, "SELECT * FROM weight_batches ORDER BY created_at DESC LIMIT 1")
        if batch:
            b = batch[0]
            bj = json.loads(b["batch_json"])
            data["batch"] = {"batch_id": b["batch_id"], "network": b["network"], "netuid": b["netuid"],
                             "created_at": b["created_at"], "weights": bj.get("weights", {}),
                             "receipts": [{"state": x["state"], "block": x["block"], "error": x["error"], "at": x["at"]}
                                          for x in _rows(con, "SELECT * FROM receipts WHERE batch_id = ? ORDER BY receipt_id",
                                                         (b["batch_id"],))]}
        seen: set[str] = set()
        for r in _rows(con, "SELECT * FROM audits ORDER BY at DESC"):
            d = json.loads(r["detail"] or "{}")
            key = d.get("audit_run") or r["audit_id"]
            if key in seen or "verdict" not in d:
                continue
            seen.add(key)
            data["audits"].append({"hotkey": r["miner_hotkey"], "uid": uid_of.get(r["miner_hotkey"]),
                                   "engine": r["engine_digest"], "verdict": d["verdict"], "live": d.get("live_mean"),
                                   "audit": d.get("audit_mean"), "reason": d.get("reason"), "block": r["block"],
                                   "at": r["at"]})
            if len(data["audits"]) >= MAX_AUDITS:
                break
    finally:
        con.close()
    return data


# ------------------------------------------------------------------ rendering


def short_digest(d: str | None) -> str:
    if not d or d == "none":
        return "—"
    d = d[7:] if d.startswith("sha256:") else d
    return f"{d[:4]}…{d[-3:]}"


def _hms(iso: str | None) -> str:
    return iso[11:19] if iso and len(iso) >= 19 else "—"


def _q(q: float | None) -> Text:
    return Text("—", style="dim") if q is None else Text(f"{q:.1f}", style=q_style(q))


VERDICT_STYLE = {"pass": "bold green", "fail": "bold red", "inconclusive": "bold yellow"}
RECEIPT_STYLE = {"revealed": "green", "committed": "cyan", "submitted": "cyan", "proposed": "yellow",
                 "failed": "red", "skipped_no_qualifier": "dim"}


def render(data: dict):
    ch = data["chain"]
    head = Text()
    head.append("CADRecover ", style="bold")
    head.append(f"· {ch['network']} ", style="dim")
    if ch.get("reachable") is False:
        head.append("· chain unreachable", style="bold red")
    elif ch.get("block") is not None:
        head.append(f"· block {ch['block']:,}", style="bold cyan")
    head.append(f" · netuid {ch['netuid'] if ch.get('netuid') is not None else '—'}")
    if ch.get("commit_reveal") is not None:
        head.append(" · commit-reveal ")
        head.append("on" if ch["commit_reveal"] else "off", style="green" if ch["commit_reveal"] else "yellow")
    parts: list = [head]
    if ch.get("note"):
        parts.append(Text(f"  note: {ch['note']}", style="dim"))
    if ch.get("error"):
        parts.append(Text(f"  chain error: {ch['error']}", style="red"))

    t = Table(title="Miners", title_justify="left", expand=False, header_style="bold")
    for col, kw in (("uid", {"justify": "right"}), ("strategy", {}), ("axon", {}), ("last Q", {"justify": "right"}),
                    ("mean Q", {"justify": "right"}), ("n", {"justify": "right"}), ("engine", {})):
        t.add_column(col, **kw)
    for m in data["miners"]:
        t.add_row(str(m["uid"]), m["label"] or m["hotkey"][:10], m["axon"] or "—", _q(m["last_q"]), _q(m["mean_q"]),
                  str(m["samples"]), short_digest(m["engine"]))
    if not data["miners"]:
        t.add_row("—", "no miner has been queried yet", "", "", "", "", "")
    parts.append(t)

    r = data["run"]
    if r:
        line = Text("Latest run  ", style="bold")
        line.append(f"{r['run_id']} · {r['challenge_id']} · ")
        line.append(r["status"], style="green" if r["status"] == "done" else "yellow")
        line.append(f" · {_hms(r['started_at'])} UTC · {r['evaluated']}/{r['miners']} evaluated")
        if r["best_q"] is not None:
            line.append(" · best Q ")
            line.append(f"{r['best_q']:.1f}", style=q_style(r["best_q"]))
        parts.append(line)
    else:
        parts.append(Text("Latest run  none yet", style="dim"))

    b = data["batch"]
    if b:
        weights = ", ".join(f"uid {u}: {w:.3f}" for u, w in b["weights"].items()) or "none"
        parts.append(Text.assemble(("Latest weight batch  ", "bold"),
                                   f"{b['batch_id']} · {_hms(b['created_at'])} UTC · weights {weights}"))
        wt = Table(header_style="bold")
        for col in ("receipt", "block", "at (UTC)", "detail"):
            wt.add_column(col)
        for x in b["receipts"]:
            wt.add_row(Text(x["state"], style=RECEIPT_STYLE.get(x["state"], "")), str(x["block"] or "—"), _hms(x["at"]),
                       (x["error"] or "")[:60])
        parts.append(wt)
    else:
        parts.append(Text("Latest weight batch  none yet", style="dim"))

    at = Table(title="Latest audits", title_justify="left", header_style="bold")
    for col, kw in (("uid", {"justify": "right"}), ("engine", {}), ("verdict", {}), ("live Q", {"justify": "right"}),
                    ("audit Q", {"justify": "right"}), ("block", {"justify": "right"}), ("reason", {})):
        at.add_column(col, **kw)
    for a in data["audits"]:
        at.add_row(str(a["uid"] if a["uid"] is not None else a["hotkey"][:8]), short_digest(a["engine"]),
                   Text(a["verdict"].upper(), style=VERDICT_STYLE.get(a["verdict"], "")), _q(a["live"]), _q(a["audit"]),
                   str(a["block"] or "—"), (a["reason"] or "reproduced" if a["verdict"] == "pass" else a["reason"] or "")[:60])
    if not data["audits"]:
        at.add_row("—", "", "no audits yet", "", "", "", "")
    parts.append(at)
    return Group(*parts)


def watch(network: str, interval: float, chain: bool = True) -> None:
    """Redraw in place until Ctrl-C. Imports happen once, so refreshes are cheap (unlike `watch cadrecover status`)."""
    from rich.console import Console
    from rich.live import Live

    console = Console()
    with Live(console=console, screen=True, auto_refresh=False) as live:
        try:
            while True:
                live.update(render(collect(network, chain)), refresh=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


# ------------------------------------------------------------------ event feed (the "miners" pane of the demo)

EVENT_KINDS = ("run.", "job.", "weights.", "audit.")
_KIND_STYLE = {"job.sent": "cyan", "job.done": "green", "job.failed": "red", "job.dispatch_failed": "red",
               "job.timeout": "yellow", "audit.pass": "bold green", "audit.fail": "bold red",
               "audit.inconclusive": "bold yellow", "weights.revealed": "bold green", "weights.failed": "bold red"}


def format_event(row: sqlite3.Row, labels: dict[int, str], uids: dict[str, int] | None = None) -> Text:
    """One event as a styled line: time, kind, who, and the facts that matter."""
    p = json.loads(row["payload"] or "{}")
    t = Text()
    t.append(_hms(row["at"]), style="dim")
    t.append(f"  {row['kind']:<20}", style=_KIND_STYLE.get(row["kind"], "bold" if row["kind"].startswith("run.") else ""))
    uid = p.get("uid")
    if uid is None and p.get("hotkey"):  # audit events name the hotkey
        uid = (uids or {}).get(p["hotkey"])
    if uid is not None:
        t.append(f"uid {uid} {labels.get(uid, '')}".strip().ljust(26))
    facts = []
    if p.get("quality") is not None:
        t.append("Q ")
        t.append(f"{p['quality']:.1f}  ", style=q_style(p["quality"]))
    for key in ("sets", "block", "audit_mean", "live_mean", "reason", "error", "deadline_s", "miners", "challenge_id"):
        v = p.get(key)
        if v not in (None, "", []):
            facts.append(f"{key}={str(v)[:70]}")
    if "weights" in p and isinstance(p["weights"], dict):
        facts.append("weights=" + ",".join(f"{u}:{w:.2f}" for u, w in p["weights"].items()))
    if "engine" in p:
        facts.append(f"engine={short_digest(p['engine'])}")
    t.append("  ".join(facts), style="dim")
    return t


def follow_events(*, follow: bool = True, last: int = 10, kinds: tuple[str, ...] = EVENT_KINDS, interval: float = 1.0,
                  console=None) -> None:
    """Print the newest events, then new ones as they arrive (the validator writes them as it works)."""
    from rich.console import Console

    console = console or Console(highlight=False, soft_wrap=True)
    cursor = 0
    first = True
    while True:
        con = _db()
        if con is not None:
            try:
                labels = {r["uid"]: r["label"] or "" for r in _rows(con, "SELECT uid, label FROM miners")}
                uids = {r["hotkey"]: r["uid"] for r in _rows(con, "SELECT hotkey, uid FROM miners ORDER BY registered_at_block")}
                rows = _rows(con, "SELECT * FROM events WHERE event_id > ? ORDER BY event_id", (cursor,))
            finally:
                con.close()
            if rows:
                cursor = rows[-1]["event_id"]
                rows = [r for r in rows if r["kind"].startswith(kinds)]
                if first:
                    rows = rows[-last:]
                for r in rows:
                    console.print(format_event(r, labels, uids))
            first = False
        if not follow:
            return
        time.sleep(interval)
