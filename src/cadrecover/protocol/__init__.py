"""Shared contracts between agents. Changes are logged in notes/shared.md -> Contracts."""

from cadrecover.protocol.challenge import (
    Artifact,
    CriticalFeatureSpec,
    FeatureMeasurement,
    ParameterSet,
    ParameterSpec,
    PrivateChallenge,
    PublicChallenge,
)
from cadrecover.protocol.evaluation import (
    QUALITY_FLOOR,
    Evaluation,
    FailedCheck,
    SetScore,
    set_quality,
    task_quality,
)
from cadrecover.protocol.jobs import JobAccepted, JobRequest, JobResult, JobStatus
from cadrecover.protocol.version import CAD_ENGINE, PROTOCOL_VERSION, SCORING_VERSION
from cadrecover.protocol.weights import MinerIdentity, WeightBatch, WeightReceipt

__all__ = [
    "Artifact", "CriticalFeatureSpec", "FeatureMeasurement", "ParameterSet", "ParameterSpec",
    "PrivateChallenge", "PublicChallenge", "QUALITY_FLOOR", "Evaluation", "FailedCheck", "SetScore",
    "set_quality", "task_quality", "JobAccepted", "JobRequest", "JobResult", "JobStatus",
    "CAD_ENGINE", "PROTOCOL_VERSION", "SCORING_VERSION", "MinerIdentity", "WeightBatch", "WeightReceipt",
]

from cadrecover.protocol.hill import (ModelCommitment, ModelStatus, Model, MatchSummary, MatchTask, Entry, LineageEntry)
__all__ += ["ModelCommitment", "ModelStatus", "Model", "MatchSummary", "MatchTask", "Entry", "LineageEntry"]
