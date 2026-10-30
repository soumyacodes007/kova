"""The shared ledger protects caps across failures, restarts and connections."""

import sqlite3

import pytest

from cadrecover.validator.hill.budget import BudgetExceeded, BudgetGuard


def test_reservations_survive_restart_and_match_caps(tmp_path):
    path = tmp_path / "spend.sqlite"
    guard = BudgetGuard(sqlite3.connect(path), total_cap=.8, match_cap=.5)
    first = guard.reserve("m1", "model", .3)
    guard.mark_unknown(first)
    reloaded = BudgetGuard(sqlite3.connect(path), total_cap=.8, match_cap=.5)
    assert reloaded.totals("m1") == .3
    with pytest.raises(BudgetExceeded, match="match"):
        reloaded.reserve("m1", "model", .21)
    reloaded.reserve("m2", "model", .5)
    with pytest.raises(BudgetExceeded, match="lifetime"):
        guard.reserve("m3", "model", .01)
    assert reloaded.totals() == .8


def test_settled_usage_releases_only_unused_reservation():
    con = sqlite3.connect(":memory:")
    guard = BudgetGuard(con)
    item = guard.reserve("m", "model", .5)
    guard.settle(item, .01, prompt_tokens=12, completion_tokens=34)
    assert guard.totals() == .01
    assert con.execute("SELECT state, prompt_tokens, completion_tokens FROM hill_spend").fetchone() == (
        "charged", 12, 34)
    with pytest.raises(ValueError, match="once"):
        guard.settle(item, 0)


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_nonfinite_or_negative_amount_refused(amount):
    guard = BudgetGuard(sqlite3.connect(":memory:"))
    with pytest.raises(ValueError):
        guard.reserve("m", "model", amount)
    assert guard.totals() == 0


def test_exact_cap_permitted_and_rollback_leaves_connection_usable():
    guard = BudgetGuard(sqlite3.connect(":memory:"), total_cap=.5, match_cap=.5)
    item = guard.reserve("m", "model", .5)
    with pytest.raises(BudgetExceeded):
        guard.reserve("m", "model", .01)
    guard.settle(item, .25)
    guard.reserve("m", "model", .25)
    assert guard.totals() == .5


def test_pending_other_work_is_never_committed_by_reservation():
    con = sqlite3.connect(":memory:")
    guard = BudgetGuard(con)
    con.execute("CREATE TABLE other (x)")
    con.execute("INSERT INTO other VALUES (1)")
    with pytest.raises(RuntimeError, match="committed"):
        guard.reserve("m", "model", .01)
    con.rollback()
    assert con.execute("SELECT COUNT(*) FROM other").fetchone()[0] == 0


def test_settlement_cannot_increase_reservation_or_exceed_cap():
    guard = BudgetGuard(sqlite3.connect(":memory:"), total_cap=.5, match_cap=.5)
    item = guard.reserve("m", "model", .5)
    with pytest.raises(BudgetExceeded, match="reservation"):
        guard.settle(item, .51)
    assert guard.totals() == .5
    assert guard.con.execute("SELECT state FROM hill_spend").fetchone()[0] == "reserved"
