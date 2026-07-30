from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from twelvelabs import TwelveLabs
from twelvelabs.core import ApiError

from .domain import Behavior, DataGap, EvidenceKind, Observation
from .ids import observation_id, stable_id

PROVIDER_PROMPT = """
Observe only visible animal behavior in this video interval. Return timestamped
observations that match the JSON schema. State uncertainty when identity or
behavior is unclear. Do not assign severity, diagnose a condition, recommend
treatment, infer intent, or claim an event when the visual evidence is absent.
Timestamps must be seconds relative to the start of this supplied video.
""".strip()


class ProviderObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior: Behavior
    relative_start_seconds: float = Field(ge=0)
    relative_end_seconds: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=1000)
    provider_item_id: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> ProviderObservation:
        if self.relative_end_seconds <= self.relative_start_seconds:
            raise ValueError("relative end must be after relative start")
        return self


class ProviderBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ProviderObservation]
    coverage_complete: bool
    uncertainty: list[str] = Field(default_factory=list)


class VideoChunkContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    animal_id: str
    enclosure_id: str
    start_ts: datetime
    end_ts: datetime

    @model_validator(mode="after")
    def validate_interval(self) -> VideoChunkContext:
        if self.start_ts.tzinfo is None or self.end_ts.tzinfo is None:
            raise ValueError("chunk timestamps must be timezone-aware")
        if self.end_ts <= self.start_ts:
            raise ValueError("chunk end must be after chunk start")
        return self

    @property
    def duration_seconds(self) -> float:
        return (self.end_ts - self.start_ts).total_seconds()


class ProviderAnalysis(BaseModel):
    observations: list[Observation]
    data_gap: DataGap | None = None
    uncertainty: list[str] = Field(default_factory=list)


def normalize_batch(
    batch: ProviderBatch,
    chunk: VideoChunkContext,
    *,
    provider: str,
    provider_model: str,
    timestamp_tolerance_seconds: float = 0.5,
) -> list[Observation]:
    normalized = []
    for ordinal, item in enumerate(batch.observations):
        if item.relative_end_seconds > chunk.duration_seconds + timestamp_tolerance_seconds:
            raise ValueError("provider observation exceeds the source chunk")
        relative_end = min(item.relative_end_seconds, chunk.duration_seconds)
        stable_observation_id = observation_id(
            chunk.chunk_id,
            item.behavior,
            provider_item_id=item.provider_item_id,
            ordinal=ordinal,
        )
        normalized.append(
            Observation(
                observation_id=stable_observation_id,
                animal_id=chunk.animal_id,
                enclosure_id=chunk.enclosure_id,
                chunk_id=chunk.chunk_id,
                behavior=item.behavior,
                start_ts=chunk.start_ts + timedelta(seconds=item.relative_start_seconds),
                end_ts=chunk.start_ts + timedelta(seconds=relative_end),
                confidence=item.confidence,
                evidence=item.evidence,
                provider=provider,
                provider_model=provider_model,
                provider_item_id=item.provider_item_id,
                evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            )
        )
    return normalized


def _is_retryable_provider_error(error: BaseException) -> bool:
    if isinstance(error, (OSError, TimeoutError)):
        return True
    return isinstance(error, ApiError) and int(getattr(error, "status_code", 0) or 0) >= 500


class TwelveLabsAnalyzer:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "pegasus1.5",
        client: Any | None = None,
    ):
        self.model = model
        self.client = client or TwelveLabs(api_key=api_key)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception(_is_retryable_provider_error),
        reraise=True,
    )
    def _analyze(self, video: dict[str, str]) -> ProviderBatch:
        response = self.client.analyze(
            model_name=self.model,
            video=video,
            prompt=PROVIDER_PROMPT,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": provider_response_schema(),
            },
            max_tokens=3000,
        )
        if getattr(response, "finish_reason", None) == "length":
            raise ValueError("provider response was truncated")
        data = getattr(response, "data", None)
        if not data:
            raise ValueError("provider returned no structured analysis")
        return ProviderBatch.model_validate_json(data)

    def analyze_url(self, video_url: str, chunk: VideoChunkContext) -> ProviderBatch:
        del chunk
        return self._analyze({"type": "url", "url": video_url})

    def analyze_file(self, path: str | Path, chunk: VideoChunkContext) -> ProviderBatch:
        del chunk
        source = Path(path)
        if source.stat().st_size > 22 * 1024 * 1024:
            raise ValueError("local video is too large for the provider base64 limit")
        encoded = base64.b64encode(source.read_bytes()).decode("ascii")
        return self._analyze({"type": "base64_string", "base64_string": encoded})

    def safe_analyze_url(self, video_url: str, chunk: VideoChunkContext) -> ProviderAnalysis:
        return self._safe_analyze(lambda: self.analyze_url(video_url, chunk), chunk)

    def safe_analyze_file(
        self,
        path: str | Path,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis:
        return self._safe_analyze(lambda: self.analyze_file(path, chunk), chunk)

    def _safe_analyze(
        self,
        analyze: Any,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis:
        try:
            batch = analyze()
            return ProviderAnalysis(
                observations=normalize_batch(
                    batch,
                    chunk,
                    provider="twelvelabs",
                    provider_model=self.model,
                ),
                uncertainty=batch.uncertainty,
                data_gap=None
                if batch.coverage_complete
                else _provider_gap(chunk, "provider_reported_incomplete_coverage"),
            )
        except Exception as error:
            return ProviderAnalysis(
                observations=[],
                data_gap=_provider_gap(
                    chunk,
                    "provider_analysis_failed",
                    detail=f"{type(error).__name__}: structured analysis unavailable",
                ),
            )


def _provider_gap(
    chunk: VideoChunkContext,
    reason: str,
    *,
    detail: str | None = None,
) -> DataGap:
    return DataGap(
        gap_id=stable_id("gap", chunk.chunk_id, reason),
        enclosure_id=chunk.enclosure_id,
        chunk_id=chunk.chunk_id,
        start_ts=chunk.start_ts,
        end_ts=chunk.end_ts,
        reason=reason,
        detail=detail,
    )


def fixture_batch(payload: str | bytes | dict[str, object]) -> ProviderBatch:
    if isinstance(payload, dict):
        return ProviderBatch.model_validate(payload)
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return ProviderBatch.model_validate(json.loads(payload))


def provider_response_schema() -> dict[str, object]:
    schema = ProviderBatch.model_json_schema()
    unsupported_constraint_keywords = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }

    def clean(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: clean(item)
                for key, item in value.items()
                if key not in unsupported_constraint_keywords
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(schema)
