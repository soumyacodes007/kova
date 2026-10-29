"""Evaluation records and the canonical score formula (owner: agent A).

PRD v2.1: a task is scored at four parameter sets (s0 = the drawing, s1-s3 =
hidden edits), averaged equally:

    Q_s = V_s * C_s * (0.7 * G_s + 0.3 * D_s)
    Q   = 100 * mean(Q_s)

V_s and C_s are 0/1 gates: an invalid build, or a missing or misplaced critical
feature, zeroes that set. A constant model (right only at s0) tops out at 25.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from cadrecover.protocol.version import SCORING_VERSION

N_SETS = 4
GEOMETRY_WEIGHT = 0.7
DIMENSION_WEIGHT = 0.3
QUALITY_FLOOR = 50.0  # starting floor: above the constant-model ceiling of 25; recalibrate from baselines


class FailedCheck(BaseModel):
    name: str  # e.g. "hole_2.position"
    message: str
    location: tuple[float, float, float] | None = None  # world-space, for the viewer's fly-to


class SetScore(BaseModel):
    index: int
    values: dict[str, float]
    valid: bool  # V_s
    critical_ok: bool  # C_s
    geometry: float = Field(ge=0, le=1)  # G_s: solid IoU vs the reference at this set
    dimensions: float = Field(ge=0, le=1)  # D_s: fraction of dimensions within tolerance
    failed_checks: list[FailedCheck] = Field(default_factory=list)

    @property
    def q(self) -> float:
        return set_quality(self.valid, self.critical_ok, self.geometry, self.dimensions)


def set_quality(valid: bool, critical_ok: bool, geometry: float, dimensions: float) -> float:
    """Q_s in [0, 1]."""
    return float(valid) * float(critical_ok) * (GEOMETRY_WEIGHT * geometry + DIMENSION_WEIGHT * dimensions)


def task_quality(sets: list[SetScore]) -> float:
    """Q in [0, 100]: the equal-weight mean of Q_s over all four sets."""
    if len(sets) != N_SETS:
        raise ValueError(f"a task is scored at exactly {N_SETS} parameter sets, got {len(sets)}")
    return 100.0 * sum(s.q for s in sets) / N_SETS


FailureClass = Literal["none", "miner", "validator_outage"]


class Evaluation(BaseModel):
    scoring_version: str = SCORING_VERSION
    challenge_id: str
    job_id: str
    miner_hotkey: str
    sets: list[SetScore]
    failure_class: FailureClass = "none"
    failure_reason: str | None = None

    @field_validator("sets")
    @classmethod
    def _four_sets(cls, v: list[SetScore]) -> list[SetScore]:
        if len(v) != N_SETS:
            raise ValueError(f"expected {N_SETS} sets, got {len(v)}")
        return v

    @property
    def quality(self) -> float:
        """Q. A validator outage is excluded for every miner, so it has no score."""
        if self.failure_class == "validator_outage":
            raise ValueError("validator outages are excluded from scoring")
        return task_quality(self.sets)
