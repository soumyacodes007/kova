import sqlite3
import subprocess

import pytest

from cadrecover.validator.hill.budget import BudgetExceeded, BudgetGuard
from cadrecover.validator.hill.deploy import DeployUnavailable, DeploymentPlan, deployed


def plan(**kwargs):
    return DeploymentPlan("owner/vision-model", "a" * 40, "user", .12, **kwargs)


def test_dry_run_exact_commands_revision_and_gpu():
    text = plan().dry_run()
    assert "revision=" + repr("a" * 40) in text
    assert "gpu_count=1, min_vram_gb_per_gpu=24" in text
    assert "concurrency=4" in text
    assert "chutes build hill_chute:chute --wait" in text
    assert "chutes deploy hill_chute:chute --accept-fee" in text
    assert "chutes chutes delete owner/vision-model" in text
    assert plan().fee_usd == pytest.approx(.36)
    assert plan().reservation_usd == pytest.approx(.38)


def test_disabled_default_no_commands_or_spend(monkeypatch, tmp_path):
    monkeypatch.delenv("CHUTES_DEPLOY_ENABLED", raising=False)
    budget = BudgetGuard(sqlite3.connect(":memory:"))
    with pytest.raises(DeployUnavailable, match="deploy disabled on this network"):
        with deployed(plan(), budget, "m", tmp_path, run=lambda *a, **k: pytest.fail("no command")):
            pytest.fail("not deployed")
    assert budget.totals() == 0


@pytest.mark.parametrize("config,message", [
    ({}, "explicit OK"),
    ({"allow_live": True, "verified_balance_usd": 5}, "at least"),
    ({"allow_live": True, "verified_balance_usd": 50}, "image-array"),
    ({"allow_live": True, "verified_balance_usd": 50, "vision_verified": True}, "billing"),
])
def test_enabled_still_requires_approval_balance_and_verified_controls(monkeypatch, tmp_path, config, message):
    monkeypatch.setenv("CHUTES_DEPLOY_ENABLED", "1")
    budget = BudgetGuard(sqlite3.connect(":memory:"))
    with pytest.raises(DeployUnavailable, match=message):
        with deployed(plan(), budget, "m", tmp_path, **config):
            pytest.fail("not deployed")
    assert budget.totals() == 0


def approved():
    return dict(allow_live=True, verified_balance_usd=50, vision_verified=True, billing_bound_verified=True)


def test_mock_cleanup_after_match_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("CHUTES_DEPLOY_ENABLED", "1")
    budget = BudgetGuard(sqlite3.connect(":memory:"))
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        assert kwargs["check"] and kwargs["capture_output"] and kwargs["timeout"] > 0

    with pytest.raises(ValueError, match="match failed"):
        with deployed(plan(), budget, "m", tmp_path, run=run, **approved()) as lease:
            assert lease.endpoint.endswith("/v1/chat/completions")
            raise ValueError("match failed")
    assert commands == plan().commands
    assert budget.con.execute("SELECT state FROM hill_spend").fetchone()[0] == "unknown"
    assert budget.totals() == pytest.approx(.38)


def test_mock_cleanup_after_deploy_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("CHUTES_DEPLOY_ENABLED", "1")
    budget = BudgetGuard(sqlite3.connect(":memory:"))
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if "deploy" in args:
            raise subprocess.CalledProcessError(1, args, output="never log private output")

    with pytest.raises(DeployUnavailable, match="command failed") as exc:
        with deployed(plan(), budget, "m", tmp_path, run=run, **approved()):
            pytest.fail("not deployed")
    assert "private output" not in str(exc.value)
    assert commands[-1] == plan().commands[-1]


def test_deployment_fee_obeys_shared_budget_before_build(monkeypatch, tmp_path):
    monkeypatch.setenv("CHUTES_DEPLOY_ENABLED", "1")
    budget = BudgetGuard(sqlite3.connect(":memory:"), total_cap=.2)
    with pytest.raises(BudgetExceeded):
        with deployed(plan(), budget, "m", tmp_path, run=lambda *a, **k: pytest.fail("no command"), **approved()):
            pytest.fail("not deployed")


@pytest.mark.parametrize("repo,revision", [("owner/vision;touch BAD", "a" * 40),
                                           ("owner/vision", "main")])
def test_untrusted_repo_and_revision_cannot_be_commands(repo, revision):
    with pytest.raises(ValueError):
        DeploymentPlan(repo, revision, "user", .12)
