"""Challenge records (owner: agent A).

Every challenge has two records:
- PublicChallenge: what miners and the public see. No shown dimension values:
  miners must read them off the drawing.
- PrivateChallenge: the seed, parameter values, hidden edit sets, reference
  artifacts and expected measurements. Never served until the challenge is retired.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from cadrecover.protocol.version import CAD_ENGINE, PROTOCOL_VERSION, SCORING_VERSION

Family = Literal["plate", "flange", "wafer_chuck", "vacuum_chamber"]
FeatureKind = Literal["hole", "bolt_circle", "bore", "port", "slot", "length"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ParameterSpec(BaseModel):
    """A parameter the miner's build_part(params) must accept, and the range it may be edited over."""

    name: str
    description: str
    unit: Literal["mm"] = "mm"
    min: float
    max: float


class CriticalFeatureSpec(BaseModel):
    """A feature checked at every parameter set; missing or misplaced zeroes that set (PRD v2.1)."""

    name: str  # e.g. "hole_1", "bolt_circle"
    kind: FeatureKind
    description: str
    size_tolerance_mm: float  # diameters, widths, lengths
    position_tolerance_mm: float  # centres and axes


class Artifact(BaseModel):
    """A file in the public artifact store or the private runtime folder, pinned by hash."""

    path: str  # relative to the store root
    sha256: str
    media_type: str


class PublicChallenge(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    scoring_version: str = SCORING_VERSION
    challenge_id: str  # opaque; reveals nothing about the seed or family internals
    family: Family
    created_at: datetime = Field(default_factory=_now)
    deadline_s: int = 180
    units: Literal["mm"] = "mm"
    frame: str  # the coordinate frame miners must build in
    # build_part is called with {} for the part exactly as drawn, and with only the
    # *changed* parameters for each hidden edit. Every other dimension must come from
    # what the miner read off the drawing; passing all values would let a template
    # score without ever reading it.
    entry_point: str = "build_part(overrides: dict[str, float]) -> build123d.Part"
    engine: dict[str, str] = Field(default_factory=lambda: dict(CAD_ENGINE))
    parameters: list[ParameterSpec]
    edit_rules: list[str]  # how features must follow parameter changes
    critical_features: list[CriticalFeatureSpec]
    drawing: Artifact


class FeatureMeasurement(BaseModel):
    """A measured feature of a solid (reference or candidate)."""

    name: str
    kind: FeatureKind
    center: tuple[float, float, float] | None = None
    axis: tuple[float, float, float] | None = None
    diameter: float | None = None
    length: float | None = None


class ParameterSet(BaseModel):
    """One of the four sets a task is scored at: s0 (the drawing) or a hidden edit."""

    index: int  # 0 = the drawing's values; 1-3 = hidden edits
    values: dict[str, float]  # the full parameter values the reference is built with
    overrides: dict[str, float] = Field(default_factory=dict)  # what build_part receives: {} at s0, changed keys at edits
    reference: Artifact | None = None  # reference STEP rebuilt at these values
    measurements: list[FeatureMeasurement] = Field(default_factory=list)
    volume_mm3: float | None = None
    # Discriminative-edit evidence (PRD v2.1), filled for hidden edits (index >= 1):
    max_feature_shift_mm: float | None = None
    reference_self_iou: float | None = None


class PrivateChallenge(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    challenge_id: str
    family: Family
    seed: int
    created_at: datetime = Field(default_factory=_now)
    sets: list[ParameterSet]  # sets[0] is the drawing; hidden edits are appended by the edit sampler
    drawing_svg: Artifact | None = None
    drawing_lint: dict | None = None
    status: Literal["active", "retired"] = "active"

    @property
    def shown(self) -> ParameterSet:
        return self.sets[0]
