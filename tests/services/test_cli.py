"""Phase 8 CLI: argument parsing, `task sample` leaking only public files, readable logs, doctor and status rendering.

No chain, Docker or CAD environment is touched: those pieces are replaced by fakes.
"""

import json
import shutil
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from cadrecover import cli, cli_logs, doctor, status
from cadrecover.cli_task import write_sample

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "public" / "sample_plate"


def _plain(renderable) -> str:
    buf = StringIO()
    Console(file=buf, force_terminal=False, width=140, highlight=False).print(renderable)
    return buf.getvalue()


# ------------------------------------------------------------------ task sample


def _fake_new_challenge(tmp_path):
    """Mimics pipeline.new_challenge: a private store with ground truth and a public store with two files."""
    def new_challenge(family="plate", **_):
        cid = "ch_testsample0001"
        private = tmp_path / "private" / cid
        public = tmp_path / "public" / cid
        private.mkdir(parents=True)
        public.mkdir(parents=True)
        (private / "private.json").write_text('{"secret": "ground truth"}')
        (private / "s0.step").write_text("STEP")
        (private / "drawing.svg").write_text("<svg/>")
        record = json.loads((FIXTURE / "challenge.json").read_text())
        record["challenge_id"] = cid
        (public / "challenge.json").write_text(json.dumps(record))
        shutil.copyfile(FIXTURE / "drawing.png", public / "drawing.png")
        return {"challenge_id": cid, "family": family, "drawing_png": str(public / "drawing.png"),
                "public_record": str(public / "challenge.json"), "private_record": str(private / "private.json")}
    return new_challenge


def test_task_sample_writes_only_public_files_and_retires(tmp_path):
    retired = []
    out = tmp_path / "dev"
    res = write_sample("plate", out, new_challenge=_fake_new_challenge(tmp_path), retire=retired.append)
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == ["ch_testsample0001/challenge.json", "ch_testsample0001/drawing.png"]
    assert "ground truth" not in "".join(p.read_text() for p in out.rglob("*.json"))
    assert retired == ["ch_testsample0001"]  # a handed-out drawing can never be a live round
    assert Path(res["drawing_png"]).exists() and Path(res["public_record"]).exists()


def test_task_sample_cli_prints_paths(tmp_path, monkeypatch, capsys):
    from cadrecover import cli_task

    monkeypatch.setattr(cli_task, "write_sample", lambda family, out: {
        "challenge_id": "ch_x", "family": family, "dir": str(out), "public_record": f"{out}/ch_x/challenge.json",
        "drawing_png": f"{out}/ch_x/drawing.png"})
    cli.main(["task", "sample", "--family", "plate", "--out", str(tmp_path / "o")])
    text = capsys.readouterr().out
    assert "ch_x/drawing.png" in text and "ch_x/challenge.json" in text


def test_task_sample_family_is_not_hardcoded():
    # another agent adds families to `challenge new`; `task sample` accepts any name and lets the pipeline validate it
    a = cli_args(["task", "sample", "--family", "flange"])
    assert a.family == "flange" and a.out == Path("cadrecover-sample")


def cli_args(argv):
    """Parse without running the command."""
    captured = {}
    import argparse

    orig = argparse.ArgumentParser.parse_args

    def grab(self, args=None, namespace=None):
        ns = orig(self, args, namespace)
        captured["ns"] = ns
        ns.fn = lambda _a: None
        return ns

    argparse.ArgumentParser.parse_args = grab
    try:
        cli.main(argv)
    finally:
        argparse.ArgumentParser.parse_args = orig
    return captured["ns"]


def test_parsing_new_commands():
    a = cli_args(["status", "--watch", "--interval", "5", "--no-chain"])
    assert (a.watch, a.interval, a.no_chain, a.network) == (True, 5.0, True, "local")
    assert cli_args(["api", "serve"]).port == 8000
    assert cli_args(["api", "serve", "--port", "9001"]).port == 9001
    assert cli_args(["doctor", "--json"]).json is True
    assert cli_args(["validator", "run", "--rounds", "2", "--plain"]).plain is True
    assert cli_args(["auditor", "run", "--top", "1"]).plain is False


def test_challenge_new_family_line_still_there():
    assert cli_args(["challenge", "new", "--family", "plate"]).family == "plate"


# ------------------------------------------------------------------ api serve


def test_api_serve_is_loopback_factory(monkeypatch):
    import importlib.util

    import uvicorn

    calls = {}
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.update(args=a, kw=kw))
    cli.main(["api", "serve", "--port", "8123"])
    assert calls["args"] == ("cadrecover.api.app:create_app",)
    assert calls["kw"]["factory"] is True and calls["kw"]["host"] == "127.0.0.1" and calls["kw"]["port"] == 8123


def test_api_serve_without_app_exits_cleanly(monkeypatch):
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    with pytest.raises(SystemExit) as e:
        cli.main(["api", "serve"])
    assert "does not exist yet" in str(e.value)


# ------------------------------------------------------------------ logs


def test_log_styles_grade_q_and_verdicts():
    assert cli_logs.q_style(100) == "bold green" and cli_logs.q_style(60) == "yellow" and cli_logs.q_style(0) == "bold red"
    line = "  uid 2   mock-oracle            done     Q 100.0  sets [100, 100, 100, 100]"
    assert "[bold green]100.0[/]" in cli_logs.style_line(line)
    assert "[bold red]0.0[/]" in cli_logs.style_line("  uid 6   diag-crash             failed   Q   0.0  sets [0, 0, 0, 0]")
    assert "[bold green]PASS[/]" in cli_logs.style_line("[audit] 5CfNDBfTnf… engine a6f5b5bba590 live 100.0 audit 100.0 -> PASS")
    assert "[bold red]FAIL[/]" in cli_logs.style_line("[audit] x… engine y live 100.0 audit 25.0 -> FAIL (audit mean low)")


def test_rich_logger_keeps_text_and_brackets():
    buf = StringIO()
    log = cli_logs.rich_logger(Console(file=buf, force_terminal=False, width=200, highlight=False))
    lines = ["[round] run_ab: challenge ch_1 · 5 miners · deadline 180s",
             "  uid 3   mock-noisy            done     Q  25.0  sets [100, 0, 0, 0]",
             "[chain] weights committed at block 42",
             "[chain] weights failed at block 42: boom [x]",
             "[audit] ab… engine 9f3a live 94.0 audit 93.0 -> PASS"]
    for ln in lines:
        log(ln)
    assert buf.getvalue().splitlines() == [ln.rstrip() for ln in lines]


def test_validator_run_passes_a_logger_and_keeps_json(monkeypatch, capsys):
    from cadrecover.validator import round as rnd

    seen = {}

    def fake_run_round(**kw):
        seen.update(kw)
        kw["log"]("[round] hello")
        return {"run_id": "run_1"}

    monkeypatch.setattr(rnd, "run_round", fake_run_round)
    cli.main(["validator", "run", "--rounds", "1", "--json", "--plain", "--static"])
    out = capsys.readouterr().out
    assert callable(seen["log"]) and seen["static"] is True
    assert "[round] hello" in out and '"run_id": "run_1"' in out


# ------------------------------------------------------------------ doctor


def test_doctor_exit_code_and_render(monkeypatch, capsys):
    checks = [doctor.Check("env services", "ok", "imports its libraries"),
              doctor.Check("port 8000", "warn", "in use"),
              doctor.Check("miners", "fail", "0/5 healthy")]
    monkeypatch.setattr(doctor, "run_checks", lambda network="local": checks)
    with pytest.raises(SystemExit) as e:
        cli.main(["doctor"])
    assert e.value.code == 1
    text = capsys.readouterr().out
    assert "✓ env services" in text and "✗ miners" in text and "! port 8000" in text and "1 check(s) failed" in text

    monkeypatch.setattr(doctor, "run_checks", lambda network="local": checks[:2])
    with pytest.raises(SystemExit) as e:
        cli.main(["doctor", "--json"])
    assert e.value.code == 0  # warnings do not fail the command
    assert json.loads(capsys.readouterr().out)[1]["status"] == "warn"


def test_doctor_port_check(monkeypatch):
    monkeypatch.setattr(doctor, "port_listening", lambda port, host="127.0.0.1": port == 8790)
    assert doctor.check_port(8790, "artifacts", fatal=True).status == "fail"
    assert doctor.check_port(8000, "api", fatal=False).status == "ok"
    monkeypatch.setattr(doctor, "port_listening", lambda port, host="127.0.0.1": True)
    assert doctor.check_port(8000, "api", fatal=False).status == "warn"


def test_doctor_sqlite_check(tmp_path, monkeypatch):
    import sqlite3

    from cadrecover import paths

    monkeypatch.setattr(paths, "DB", tmp_path / "x.sqlite")
    assert doctor.check_sqlite().status == "ok"  # not created yet, directory writable
    sqlite3.connect(paths.DB).execute("CREATE TABLE t (a)").connection.close()
    assert "writable" in doctor.check_sqlite().detail


# ------------------------------------------------------------------ status


def _data():
    return {
        "chain": {"network": "local", "reachable": True, "block": 24306, "netuid": 2, "commit_reveal": False,
                  "note": "disabled on localnet", "axons": {}, "engines": {}},
        "miners": [{"uid": 2, "label": "mock-oracle", "hotkey": "5Cf", "axon": "http://127.0.0.1:8101",
                    "last_q": 100.0, "samples": 2, "mean_q": 100.0, "engine": "sha256:" + "a6f5" + "0" * 57 + "b50"},
                   {"uid": 6, "label": "diag-crash", "hotkey": "5GN", "axon": None, "last_q": 0.0, "samples": 2,
                    "mean_q": 0.0, "engine": None}],
        "run": {"run_id": "run_1", "challenge_id": "ch_1", "status": "done", "started_at": "2026-10-29T05:54:15+00:00",
                "miners": 5, "evaluated": 5, "best_q": 100.0, "mean_q": 40.0},
        "batch": {"batch_id": "wb_1", "network": "local", "netuid": 2, "created_at": "2026-10-29T05:56:31+00:00",
                  "weights": {2: 1.0}, "receipts": [
                      {"state": "proposed", "block": None, "error": None, "at": "2026-10-29T05:56:31+00:00"},
                      {"state": "revealed", "block": 15596, "error": None, "at": "2026-10-29T05:56:34+00:00"}]},
        "audits": [{"hotkey": "5Cf", "uid": 2, "engine": "sha256:" + "9f3a" + "0" * 57 + "c21", "verdict": "pass",
                    "live": 100.0, "audit": 100.0, "reason": None, "block": 23834, "at": "2026-10-29T06:00:00+00:00"}],
    }


def test_status_render_shows_everything():
    text = _plain(status.render(_data()))
    for needle in ("block 24,306", "netuid 2", "commit-reveal off", "note: disabled on localnet", "mock-oracle",
                   "http://127.0.0.1:8101", "a6f5…b50", "run_1", "5/5 evaluated", "wb_1", "revealed", "15596",
                   "PASS", "9f3a…c21", "reproduced"):
        assert needle in text, needle


def test_status_render_when_chain_down_and_db_empty():
    data = {"chain": {"network": "local", "reachable": False, "block": None, "netuid": None, "axons": {}},
            "miners": [], "run": None, "batch": None, "audits": []}
    text = _plain(status.render(data))
    assert "chain unreachable" in text and "no audits yet" in text and "none yet" in text


def test_status_collect_reads_sqlite_without_writing(tmp_path, monkeypatch):
    from cadrecover import paths
    from cadrecover.storage import db

    monkeypatch.setattr(paths, "DB", tmp_path / "s.sqlite")
    con = db.connect()
    db.upsert_miner(con, "5Cfhot", 10, 2, "mock-oracle")
    db.save_audit(con, "audit_a-0", "5Cfhot", "sha256:" + "ab" * 32, "ch_1", 100.0, True, 77,
                  {"audit_run": "audit_a", "verdict": "pass", "live_mean": 100.0, "audit_mean": 100.0})
    con.close()
    data = status.collect("local", chain=False)
    assert data["miners"][0]["uid"] == 2 and data["miners"][0]["samples"] == 0
    assert data["audits"][0]["verdict"] == "pass" and data["audits"][0]["uid"] == 2
    assert data["run"] is None and data["batch"] is None


def test_status_cli_json(monkeypatch, capsys):
    monkeypatch.setattr(status, "collect", lambda network="local", chain=True: _data())
    cli.main(["status", "--json", "--no-chain"])
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == "run_1"


def test_events_feed_prints_job_and_audit_events(tmp_path, monkeypatch):
    from cadrecover import paths
    from cadrecover.storage import db

    monkeypatch.setattr(paths, "DB", tmp_path / "e.sqlite")
    con = db.connect()
    db.upsert_miner(con, "5Cfhot", 10, 2, "mock-oracle")
    db.add_event(con, "challenge.created", {"challenge_id": "ch_1"})
    db.add_event(con, "job.evaluated", {"uid": 2, "quality": 100.0, "sets": [100, 100, 100, 100]}, "run_1")
    db.add_event(con, "audit.pass", {"hotkey": "5Cfhot", "engine": "sha256:" + "9f3a" + "0" * 57 + "c21",
                                     "live_mean": 100.0, "audit_mean": 99.0, "block": 7})
    con.close()
    buf = StringIO()
    status.follow_events(follow=False, console=Console(file=buf, force_terminal=False, width=160, highlight=False))
    text = buf.getvalue()
    assert "job.evaluated" in text and "uid 2 mock-oracle" in text and "Q 100.0" in text
    assert "audit.pass" in text and "9f3a…c21" in text
    assert "challenge.created" not in text  # noise filtered out
