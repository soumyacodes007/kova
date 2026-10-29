"""Weight batches and chain receipts (owner: agent B).

Commit, reveal and incentive are separate states and are never collapsed in the UI.
Miner identity is hotkey + registration block, so a recycled UID starts fresh.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class MinerIdentity(BaseModel):
    hotkey: str
    registered_at_block: int
    uid: int  # current UID; may be recycled, so never the identity on its own


class WeightBatch(BaseModel):
    batch_id: str
    network: Literal["local", "test"]  # never mainnet in this build
    netuid: int
    validator_hotkey: str
    floor: float
    mean_quality: dict[str, float]  # hotkey -> rolling mean Q over completed batches
    samples: dict[str, int]  # hotkey -> completed tasks in the window
    weights: dict[int, float]  # uid -> normalized weight; empty means "no update" (nobody above the floor)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ReceiptState = Literal["proposed", "submitted", "committed", "revealed", "failed", "skipped_no_qualifier"]


class WeightReceipt(BaseModel):
    batch_id: str
    state: ReceiptState
    block: int | None = None
    extrinsic: str | None = None
    readback: dict[int, float] | None = None  # weights read back from chain for this validator
    error: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
