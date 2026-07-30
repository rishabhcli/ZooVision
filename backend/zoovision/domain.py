from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    NONE = "NONE"


class Behavior(StrEnum):
    FIGHTING = "fighting"
    ESCAPE_ATTEMPT = "escape_attempt"
    VOMITING = "vomiting"
    PACING = "pacing"
    INACTIVITY = "inactivity"
    WATER_BOWL_TIPPED = "water_bowl_tipped"
    DRINKING = "drinking"
    RESTING = "resting"
    EATING = "eating"
    GROOMING = "grooming"
    OTHER = "other"


class ShiftMode(StrEnum):
    DAY = "day"
    NIGHT = "night"


class BaselineState(StrEnum):
    LEARNING = "learning"
    SHADOW = "shadow"
    ACTIVE = "active"
    PAUSED = "paused"


class AckState(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    CLOSED = "closed"


class AlertAction(StrEnum):
    WELFARE_CHECK = "welfare_check"
    VERIFY_WATER = "verify_water"
    OBSERVE = "observe"


class EvidenceKind(StrEnum):
    PROVIDER_STRUCTURED = "provider_structured"
    HUMAN_REVIEWED = "human_reviewed"
    SYNTHETIC_SCENARIO = "synthetic_scenario"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    animal_id: str
    enclosure_id: str
    chunk_id: str
    behavior: Behavior
    start_ts: datetime
    end_ts: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=2000)
    provider: str
    provider_model: str
    provider_item_id: str | None = None
    evidence_kind: EvidenceKind = EvidenceKind.PROVIDER_STRUCTURED

    @model_validator(mode="after")
    def validate_interval(self) -> Observation:
        if self.start_ts.tzinfo is None or self.end_ts.tzinfo is None:
            raise ValueError("observation timestamps must be timezone-aware")
        if self.end_ts <= self.start_ts:
            raise ValueError("end_ts must be after start_ts")
        return self

    @property
    def duration_minutes(self) -> float:
        return (self.end_ts - self.start_ts).total_seconds() / 60


class StitchedObservation(BaseModel):
    animal_id: str
    enclosure_id: str
    behavior: Behavior
    start_ts: datetime
    end_ts: datetime
    confidence: float
    evidence: list[str]
    source_observation_ids: list[str]
    source_chunk_ids: list[str]

    @property
    def duration_minutes(self) -> float:
        return (self.end_ts - self.start_ts).total_seconds() / 60


class TriageInput(BaseModel):
    animal_id: str
    behavior: Behavior
    continuous_duration_minutes: float = Field(ge=0)
    hours_since_water_contact: float | None = Field(default=None, ge=0)
    inactivity_z: float | None = None
    baseline_delta_z: float | None = None
    evidence_sufficient: bool = True
    source_observation_ids: list[str] = Field(min_length=1)


class TriageDecision(BaseModel):
    severity: Severity
    rule_fired: str | None
    action: AlertAction | None
    explanation_facts: list[str]
    rule_version: str


class ShiftMetric(BaseModel):
    shift_id: str
    animal_id: str
    behavior: Behavior
    mode: ShiftMode
    shift_start: datetime
    duration_minutes: float = Field(ge=0)
    frequency: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_shift(self) -> ShiftMetric:
        if self.shift_start.tzinfo is None:
            raise ValueError("shift_start must be timezone-aware")
        return self


class BaselineProfile(BaseModel):
    animal_id: str
    behavior: Behavior
    state: BaselineState
    duration_mean: float | None
    duration_std: float | None
    frequency_mean: float | None
    frequency_std: float | None
    n_day_shifts: int
    window_size: int
    updated_at: datetime


class EventRecord(BaseModel):
    event_id: str
    animal_id: str
    enclosure_id: str
    behavior: Behavior
    start_ts: datetime
    end_ts: datetime
    severity: Severity
    rule_fired: str | None
    action: AlertAction | None
    confidence: float
    baseline_delta_z: float | None = None
    source_observation_ids: list[str] = Field(min_length=1)
    explanation_facts: list[str]
    rule_version: str
    shift_mode: ShiftMode
    review_state: ReviewState = ReviewState.UNREVIEWED
    created_at: datetime

    @model_validator(mode="after")
    def validate_auditable_severity(self) -> EventRecord:
        if self.severity is not Severity.NONE and not self.rule_fired:
            raise ValueError("non-NONE events require rule_fired")
        return self


class DataGap(BaseModel):
    gap_id: str
    enclosure_id: str
    chunk_id: str | None = None
    start_ts: datetime
    end_ts: datetime
    reason: str
    detail: str | None = None
