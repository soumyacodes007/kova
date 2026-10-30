"""Response models for the read API (owner: agent C).

Everything the API returns is declared here, so the OpenAPI schema (and the generated TypeScript types) is
exact. Timestamps are ISO-8601 UTC strings exactly as stored. Scores: `quality` is Q on 0..100; `q_s` is the
per-set Q_s on 0..1 (PRD v2.1: Q_s = V * C * (0.7 G + 0.3 D), Q = 100 * mean(Q_s)).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cadrecover.protocol import PublicChallenge
from cadrecover.protocol.hill import FailedCheckOut, ModelFile, ModelKind, SetResult

RunStatus = Literal["dispatching", "collecting", "evaluating", "done", "aborted"]
AssignmentStatus = Literal["pending", "sent", "done", "failed", "timeout"]
FailureClass = Literal["none", "miner", "validator_outage"]
ReceiptState = Literal["proposed", "submitted", "committed", "revealed", "failed", "skipped_no_qualifier"]
AuditVerdict = Literal["pass", "fail", "inconclusive"]


# ------------------------------------------------------------------ status


class Counts(BaseModel):
    challenges: int
    active_challenges: int
    runs: int
    miners: int
    assignments: int
    evaluations: int
    weight_batches: int
    receipts: int
    commitments: int
    audits: int
    events: int


class ChainInfo(BaseModel):
    """The chain this validator is bound to (from ~/.cadrecover/chain.json) and, if reachable, its head."""

    network: str | None = Field(description="'local' or 'test' (never mainnet in this build); null if unknown")
    netuid: int | None
    validator_hotkey: str | None
    commit_reveal_enabled: bool | None
    tempo: int | None
    block: int | None = Field(description="current chain head, read with a short timeout; null if unreachable")
    reachable: bool


class RunSummary(BaseModel):
    run_id: str
    challenge_id: str
    family: str | None
    status: RunStatus
    started_at: str
    deadline_at: str
    miners: int = Field(description="assignments in this run")
    evaluated: int = Field(description="assignments with a stored evaluation")
    mean_quality: float | None = Field(description="mean Q over evaluated, non-outage miners (0..100)")
    best_quality: float | None
    best_uid: int | None


class StatusOut(BaseModel):
    protocol_version: str
    scoring_version: str
    cad_engine: dict[str, str]
    quality_floor: float
    server_time: str
    chain: ChainInfo
    counts: Counts
    latest_event_id: int = Field(description="highest event_id in the log (0 when empty)")
    latest_run: RunSummary | None


# ------------------------------------------------------------------ challenges and runs


class ChallengeOut(PublicChallenge):
    """The PUBLIC challenge record only (names and ranges, never values), plus its lifecycle."""

    status: Literal["active", "retired"]
    retired_at: str | None
    drawing_url: str = Field(description="API path of the drawing PNG")


class MinerRunResult(BaseModel):
    job_id: str
    uid: int
    hotkey: str
    registered_at_block: int
    label: str | None
    assignment_status: AssignmentStatus
    sent_at: str | None
    evaluated: bool
    evaluated_at: str | None
    quality: float | None = Field(description="Q (0..100); null for a validator outage or before evaluation")
    failure_class: FailureClass | None
    failure_reason: str | None
    sets: list[SetResult]
    source_sha256: str | None
    model_id: str | None
    strategy_version: str | None
    duration_s: float | None
    received_at: str | None
    models: list[ModelFile]


class RunDetail(BaseModel):
    run: RunSummary
    challenge: ChallengeOut | None
    results: list[MinerRunResult]


# ------------------------------------------------------------------ leaderboard and miners


class AuditStatus(BaseModel):
    audit_run: str
    verdict: AuditVerdict
    at: str
    block: int | None
    engine_digest: str
    live_mean: float | None
    audit_mean: float | None
    reason: str | None


class LeaderboardRow(BaseModel):
    rank: int
    uid: int
    hotkey: str
    registered_at_block: int
    label: str | None
    samples: int = Field(description="completed tasks in the rolling window")
    mean_quality: float = Field(description="rolling mean Q (0..100)")
    above_floor: float
    weight: float = Field(description="normalised weight from the standings formula over identities in the newest run; failed audits zero it")
    latest_batch_weight: float | None = Field(description="weight the newest batch gave this uid; null if this identity was not in that batch's run")
    drawing_pass_rate: float | None = Field(description="share of tasks whose set 0 passed every check")
    edit_pass_rate: float | None = Field(description="share of hidden-edit sets (1-3) that passed every check")
    mean_geometry: float | None
    mean_dimensions: float | None
    committed_engine: str | None
    audit: AuditStatus | None


class Leaderboard(BaseModel):
    quality_floor: float
    window: int
    min_samples: int
    latest_batch_id: str | None
    rows: list[LeaderboardRow]


class MinerHistoryItem(BaseModel):
    job_id: str
    run_id: str
    challenge_id: str
    evaluated_at: str
    assignment_status: AssignmentStatus
    quality: float | None
    failure_class: FailureClass
    failure_reason: str | None
    set_q: list[float] = Field(description="Q_s for sets 0..3 (0..1)")


class MinerBatchAppearance(BaseModel):
    batch_id: str
    created_at: str
    mean_quality: float
    samples: int
    latest_state: ReceiptState | None


class MinerIdentity(BaseModel):
    hotkey: str
    registered_at_block: int
    uid: int
    label: str | None
    first_seen: str


class MinerDetail(BaseModel):
    hotkey: str
    identities: list[MinerIdentity] = Field(description="one per registration; a recycled UID starts fresh")
    standing: LeaderboardRow | None
    history: list[MinerHistoryItem]
    commitments: list[CommitmentOut]
    audits: list[AuditOut]
    batches: list[MinerBatchAppearance]


# ------------------------------------------------------------------ chain: weights, commitments, audits


class ReceiptOut(BaseModel):
    receipt_id: int
    state: ReceiptState
    block: int | None
    extrinsic: str | None
    readback: dict[int, float] | None = Field(description="weights read back from chain (uid -> weight)")
    error: str | None
    at: str


class WeightBatchOut(BaseModel):
    batch_id: str
    run_id: str | None
    network: Literal["local", "test"]
    netuid: int
    validator_hotkey: str
    floor: float
    created_at: str
    mean_quality: dict[str, float]
    samples: dict[str, int]
    weights: dict[int, float] = Field(description="uid -> normalised weight; empty means no update")
    latest_state: ReceiptState | None
    receipts: list[ReceiptOut] = Field(description="every transition, oldest first; commit and reveal stay separate")


class CommitmentOut(BaseModel):
    hotkey: str
    registered_at_block: int
    uid: int | None
    label: str | None
    engine_digest: str
    strategy_version: str | None
    block: int
    latest: bool = Field(description="the newest commitment for this identity")


class AuditTask(BaseModel):
    audit_id: str
    task_index: int | None
    challenge_id: str
    quality: float | None
    passed: bool
    error: str | None


class AuditOut(BaseModel):
    audit_run: str
    hotkey: str
    uid: int | None
    label: str | None
    engine_digest: str
    verdict: AuditVerdict
    reason: str | None
    live_mean: float | None
    audit_mean: float | None
    margin: float | None
    block: int | None
    at: str
    commitment: dict[str, Any] | None = Field(description="the on-chain commitment that was audited")
    tasks: list[AuditTask]


# ------------------------------------------------------------------ events


class EventOut(BaseModel):
    event_id: int
    at: str
    kind: str
    run_id: str | None
    payload: dict[str, Any]


class EventsPage(BaseModel):
    events: list[EventOut]
    next_after: int = Field(description="pass this as `after` to continue; unchanged when nothing new")
    latest_event_id: int


class Health(BaseModel):
    ok: bool
    db: str
MinerDetail.model_rebuild()
