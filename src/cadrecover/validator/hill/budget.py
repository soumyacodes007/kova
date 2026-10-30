"""Persistent, fail-closed accounting for every paid hill request.

Reservations count as spent before a request leaves the process. Trustworthy
usage replaces the reservation with token cost; an ambiguous failure keeps the
full reservation. Pending reservations survive process restarts.
"""

from __future__ import annotations

import math
import sqlite3
import uuid
from datetime import datetime, timezone


SPEND_SCHEMA = """
CREATE TABLE IF NOT EXISTS hill_spend (
    id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'inference',
    reserved_usd REAL NOT NULL CHECK(reserved_usd >= 0),
    cost_usd REAL NOT NULL CHECK(cost_usd >= 0),
    state TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at TEXT NOT NULL
);
"""


class BudgetExceeded(RuntimeError):
    """The next request cannot fit within the configured spend caps."""


def _amount(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("USD amount must be finite and nonnegative")
    return value


class BudgetGuard:
    def __init__(self, con: sqlite3.Connection, *, total_cap: float = 3.0, match_cap: float = 0.50):
        self.con = con
        self.total_cap = _amount(total_cap)
        self.match_cap = _amount(match_cap)
        self.con.executescript(SPEND_SCHEMA)

    def totals(self, match_id: str | None = None) -> float:
        if match_id is None:
            row = self.con.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM hill_spend").fetchone()
        else:
            row = self.con.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM hill_spend WHERE match_id = ?", (match_id,)
            ).fetchone()
        return float(row[0])

    def reserve(self, match_id: str, model_id: str, amount_usd: float, *, kind: str = "inference") -> str:
        """Atomically reserve a request's upper-bound charge across connections."""
        amount = _amount(amount_usd)
        if not match_id or not model_id:
            raise ValueError("Reservations require a match and model")
        if self.con.in_transaction:
            raise RuntimeError("Budget reservations require a committed database connection")
        self.con.execute("BEGIN IMMEDIATE")
        try:
            if self.totals() + amount > self.total_cap:
                raise BudgetExceeded("Chutes lifetime budget exceeded")
            if self.totals(match_id) + amount > self.match_cap:
                raise BudgetExceeded("Chutes match budget exceeded")
            spend_id = "spend_" + uuid.uuid4().hex
            self.con.execute(
                "INSERT INTO hill_spend "
                "(id, match_id, model_id, kind, reserved_usd, cost_usd, state, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?)",
                (spend_id, match_id, model_id, kind, amount, amount, datetime.now(timezone.utc).isoformat()),
            )
            self.con.commit()
            return spend_id
        except BaseException:
            self.con.rollback()
            raise

    def settle(self, spend_id: str, actual_usd: float, *, prompt_tokens: int | None = None,
               completion_tokens: int | None = None) -> None:
        actual = _amount(actual_usd)
        row = self.con.execute("SELECT state, reserved_usd FROM hill_spend WHERE id = ?", (spend_id,)).fetchone()
        if row is None:
            raise KeyError(spend_id)
        if row[0] != "reserved":
            raise ValueError("A spend reservation may only be settled once")
        if actual > row[1]:
            raise BudgetExceeded("Actual charge exceeds its reservation; reservation retained")
        self.con.execute(
            "UPDATE hill_spend SET cost_usd = ?, state = 'charged', prompt_tokens = ?, completion_tokens = ? "
            "WHERE id = ?", (actual, prompt_tokens, completion_tokens, spend_id),
        )
        self.con.commit()

    def mark_unknown(self, spend_id: str) -> None:
        """An unconfirmed charge retains its full reservation indefinitely."""
        self.con.execute("UPDATE hill_spend SET state = 'unknown' WHERE id = ? AND state = 'reserved'", (spend_id,))
        self.con.commit()
