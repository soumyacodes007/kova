"""Track B public records; mirrors docs/api/hill-contract.md, protocol 0.3.0."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from cadrecover.protocol.challenge import Family

class HillRecord(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


ModelStatus = Literal["submitted", "prechecked", "queued", "evaluating", "scored", "champion", "defeated", "rejected"]

class ModelCommitment(HillRecord):
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    revision: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    weight_bytes: int = Field(ge=1)
    base_model: str | None = None

class FailedCheckOut(HillRecord):
    name: str
    message: str
    location: tuple[float, float, float] | None


class SetResult(HillRecord):
    """One scored parameter set: s0 (the drawing's values) or one of three hidden edits."""

    index: int = Field(ge=0, le=3)
    valid: bool = Field(description="V_s: the build ran and produced a valid solid")
    critical_ok: bool = Field(description="C_s: every critical feature present and in place")
    geometry: float = Field(description="G_s: solid IoU against the reference, 0..1")
    dimensions: float = Field(description="D_s: fraction of dimensions within tolerance, 0..1")
    q_s: float = Field(description="Q_s = V * C * (0.7 G + 0.3 D), 0..1")
    passed: bool = Field(description="valid, critical features ok and no failed checks")
    failed_check_count: int
    failed_checks: list[FailedCheckOut] = Field(
        description="empty while the challenge is active: failed checks name hidden edits and carry true values")
    values: dict[str, float] | None = Field(
        description="the parameter values this set was built with; null until the challenge is retired")
    revealed: bool = Field(description="false while the challenge is active (hidden values withheld)")


ModelKind = Literal["candidate", "reference"]


class ModelFile(HillRecord):
    set_index: int
    kind: ModelKind
    url: str = Field(description="API path of the GLB (served read-only)")



class Progress(HillRecord):
    done: int = Field(ge=0)
    total: int = Field(ge=1)

class Fee(HillRecord):
    amount_tao: float = Field(ge=0)
    simulated: bool

class Model(HillRecord):
    fingerprint: str
    name: str
    source: Literal["catalog", "miner"]
    repo: str | None = None
    revision: str | None = None
    base_model: str | None = None
    hotkey: str | None = None
    uid: int | None = None
    commit_block: int | None = None
    submitted_at: str
    status: ModelStatus
    reject_reason: str | None = None
    progress: Progress | None = None
    mean_quality: float | None = Field(default=None, ge=0, le=100)
    per_family: dict[Family, float] = Field(default_factory=dict)
    critical_pass_rate: float | None = Field(default=None, ge=0, le=1)
    edit_pass_rate: float | None = Field(default=None, ge=0, le=1)
    recent_tasks: list[float] = Field(default_factory=list)
    matches_won: int = 0
    matches_lost: int = 0
    mean_latency_s: float | None = None
    tee: bool = False
    chutes_url: str | None = None
    hf_url: str | None = None
    fee: Fee | None = None

class ModelRef(HillRecord):
    fingerprint: str
    name: str

class MatchSeed(HillRecord):
    block_hash: str
    drand_round: int
    value: int = Field(ge=0, le=2**32-1)

class MatchSummary(HillRecord):
    match_id: str
    challenger: ModelRef
    champion: ModelRef | None
    status: Literal["running", "decided"]
    seed: MatchSeed | None
    tasks_total: int
    tasks_done: int = 0
    challenger_mean: float | None = None
    champion_mean: float | None = None
    margin: float = 2.0
    verdict: Literal["crowned", "defended"] | None = None
    decided_block: int | None = None
    started_at: str

class Entry(HillRecord):
    quality: float | None = None
    latency_s: float | None = None
    error: str | None = None
    sets: list[SetResult] = Field(default_factory=list)
    models: list[ModelFile] = Field(default_factory=list)

class MatchTask(HillRecord):
    index: int
    challenge_id: str
    family: Family
    drawing_url: str
    challenger: Entry
    champion: Entry | None

class LineageEntry(HillRecord):
    rev: str
    fingerprint: str
    name: str
    crowned_at_block: int
    crowned_at: str
    score: float
    dethroned_at_block: int | None = None
