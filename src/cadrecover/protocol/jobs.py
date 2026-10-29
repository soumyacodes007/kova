"""Validator <-> miner job messages (owner: agent C).

Transport: the miner's own FastAPI server; every request and response is signed
with `bittensor.http_auth` (headers), so signatures are not part of these bodies.
POST /v1/jobs returns 202 + JobAccepted; GET /v1/jobs/{job_id} returns JobStatus.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from cadrecover.protocol.challenge import PublicChallenge
from cadrecover.protocol.version import PROTOCOL_VERSION

MAX_SOURCE_BYTES = 64 * 1024


class JobRequest(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    job_id: str  # idempotent: a retried POST with the same job_id never starts a second model run
    challenge: PublicChallenge
    drawing_url: str  # where the miner fetches the drawing PNG (hash pinned in challenge.drawing)
    deadline_at: datetime


class JobAccepted(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"] = "queued"


class JobResult(BaseModel):
    """The result envelope. A valid signature proves who sent it, not that it is correct."""

    protocol_version: str = PROTOCOL_VERSION
    job_id: str
    challenge_id: str
    entry_point: str = "build_part"
    source: str = Field(max_length=MAX_SOURCE_BYTES)
    source_sha256: str
    model_id: str | None = None  # e.g. the VLM used; recorded, never trusted
    strategy_version: str | None = None
    duration_s: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _hash_matches(self) -> "JobResult":
        if hashlib.sha256(self.source.encode()).hexdigest() != self.source_sha256:
            raise ValueError("source_sha256 does not match source")
        return self

    @classmethod
    def for_source(cls, *, job_id: str, challenge_id: str, source: str, **kw) -> "JobResult":
        return cls(job_id=job_id, challenge_id=challenge_id, source=source,
                   source_sha256=hashlib.sha256(source.encode()).hexdigest(), **kw)


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    result: JobResult | None = None
    error: str | None = None
