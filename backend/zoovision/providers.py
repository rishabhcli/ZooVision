from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Any

import cv2
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from twelvelabs import TwelveLabs
from twelvelabs.core import ApiError

from .detection import sample_video_frames
from .domain import Behavior, DataGap, EvidenceKind, Observation
from .ids import observation_id, stable_id

PROVIDER_PROMPT = """
Create a dense, chronological activity log for the entire supplied enclosure
video. Cover every interval in which an animal is visibly doing something
meaningful, including routine activity such as walking, standing, resting,
eating, drinking, grooming, foraging, playing, social interaction, entering or
exiting the frame, and vocalizing when the audio clearly supports it. Also
record the constrained welfare-relevant behaviors in the schema when they are
visibly supported.

Inspect the entire frame, including edges and background, rather than following
only the most prominent animal. For each observation, state the visible animal
type, the number visibly present when it can be counted, and what each visible
animal or group is doing. Split the interval when the visible count changes or
when different animals begin different activities. Make `activity_label` a
concise keeper-readable summary such as "Three squirrels feeding on scattered
seed" rather than a generic label such as "activity" or "movement."

Use one observation per continuous activity. Split an observation whenever the
activity changes, and merge adjacent intervals only when the same activity
clearly continues. Prefer the specific behavior enum. Use `other` only when a
visible activity does not fit another enum, and then supply a short,
keeper-readable `activity_label` describing exactly what is visible. Set
`coverage_complete` to false if any part of the video could not be assessed.

Return only facts supported by visible or audible evidence. State uncertainty
when identity or behavior is unclear. Do not assign severity, diagnose a
condition, recommend treatment, infer intent, or claim an event when evidence is
absent. Timestamps must be seconds relative to the start of this supplied video.
""".strip()

OPENAI_FRAME_PROMPT = """
Create a chronological activity log from the supplied timestamped still frames.
The frames are ordered and sampled at a stated cadence from one contiguous video
window. Use only visible evidence in those frames. Do not claim audio evidence.

Cover every supplied frame. Record routine activity such as walking, standing,
resting, eating, drinking, grooming, foraging, playing, social interaction, and
entering or exiting the frame. State the visible animal type and count when they
can be supported. Treat identity as uncertain between frames unless persistent
visible features support continuity. Use `other` only when a visible activity
has no matching enum, and give it a precise keeper-readable `activity_label`.
Record the constrained welfare-relevant behavior enums when they are visibly
supported, but never assign or imply severity.

Timestamps must be seconds relative to the start of this window and must remain
within its stated duration. Copy start and end seconds exactly from the supplied
frame timestamp labels. Every observation must span at least two supplied
frames; omit a one-frame marker rather than inventing duration. Do not fill
unseen time or infer continuity beyond the frames.

`coverage_complete` records whether you reviewed every supplied frame, not
whether an animal was visible or identifiable in every frame. Set it to true
after inspecting every supplied image, including frames with no visible animal,
low light, occlusion, glare, or an uncertain identity. Put those visibility
limits in `uncertainty` and omit unsupported behavior observations. It is valid
to return `coverage_complete: true` with an empty observations list when every
frame was reviewed but no continuous animal activity was visibly supported.
Set `coverage_complete` to false only when a supplied image was missing,
corrupt, unavailable to you, or otherwise could not be inspected at all.

Do not assign severity, diagnose, recommend treatment, infer intent, or add
facts that are not visible. State identity or behavior uncertainty explicitly.
""".strip()

OPENAI_FRAME_WINDOW_SECONDS = 120.0
OPENAI_FRAME_SAMPLE_FPS = 0.25
OPENAI_FRAME_MAX_IMAGES = 32


class ProviderObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior: Behavior
    relative_start_seconds: float = Field(ge=0)
    relative_end_seconds: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=1000)
    activity_label: str | None = Field(default=None, min_length=1, max_length=160)
    provider_item_id: str | None = None


class ProviderBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[ProviderObservation]
    coverage_complete: bool
    uncertainty: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def discard_zero_length_markers(self) -> ProviderBatch:
        invalid = [
            item
            for item in self.observations
            if item.relative_end_seconds <= item.relative_start_seconds
        ]
        if invalid:
            self.observations = [
                item
                for item in self.observations
                if item.relative_end_seconds > item.relative_start_seconds
            ]
            self.uncertainty.append(f"{len(invalid)} zero-length provider marker(s) were excluded.")
        return self


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
    evidence_kind: EvidenceKind = EvidenceKind.PROVIDER_STRUCTURED,
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
                evidence_kind=evidence_kind,
                activity_label=item.activity_label,
            )
        )
    return normalized


def _is_retryable_provider_error(error: BaseException) -> bool:
    if isinstance(error, (OSError, TimeoutError)):
        return True
    status = int(getattr(error, "status_code", 0) or 0)
    return isinstance(error, ApiError) and (status == 429 or status >= 500)


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
        stop=stop_after_attempt(3),
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
            max_tokens=8000,
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
                    detail=_safe_provider_error_detail(error),
                ),
            )


class OpenAIFrameAnalyzer:
    """Analyze complete, contiguous windows from timestamped sampled frames.

    This is a deliberately labeled fallback for a video-provider outage. It
    never pretends that still frames include audio or continuous-video evidence,
    and it returns no observations unless every window succeeds.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        client: Any | None = None,
        window_seconds: float = OPENAI_FRAME_WINDOW_SECONDS,
        sample_fps: float = OPENAI_FRAME_SAMPLE_FPS,
    ):
        if window_seconds < 4:
            raise ValueError("frame-analysis windows must be at least four seconds")
        if sample_fps <= 0:
            raise ValueError("frame-analysis sample_fps must be positive")
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self.model = model
        self.client = client
        self.window_seconds = window_seconds
        self.sample_fps = sample_fps
        self.attempt_count = 0

    def safe_analyze_url(self, video_url: str, chunk: VideoChunkContext) -> ProviderAnalysis:
        del video_url
        return ProviderAnalysis(
            observations=[],
            data_gap=_provider_gap(
                chunk,
                "provider_frame_analysis_failed",
                detail="OpenAIFrameAnalyzer: local video is required",
            ),
        )

    def safe_analyze_file(
        self,
        path: str | Path,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis:
        self.attempt_count = 0
        try:
            return self._analyze_file(Path(path), chunk)
        except Exception as error:
            return ProviderAnalysis(
                observations=[],
                data_gap=_provider_gap(
                    chunk,
                    "provider_frame_analysis_failed",
                    detail=f"{type(error).__name__}: frame-sampled analysis unavailable",
                ),
            )

    def _analyze_file(self, path: Path, chunk: VideoChunkContext) -> ProviderAnalysis:
        observations: list[Observation] = []
        uncertainty: list[str] = []
        windows = _balanced_windows(chunk.duration_seconds, self.window_seconds)
        for index, (offset, duration) in enumerate(windows):
            frames = list(
                sample_video_frames(
                    path,
                    sample_fps=self.sample_fps,
                    start_seconds=offset,
                    duration_seconds=duration,
                    max_frames=OPENAI_FRAME_MAX_IMAGES,
                    max_edge=512,
                )
            )
            _validate_frame_window(frames, duration, self.sample_fps)
            if len(frames) > OPENAI_FRAME_MAX_IMAGES:
                raise ValueError("frame window exceeds the configured image limit")
            batch = self._analyze_frames(frames, duration)
            if not batch.coverage_complete:
                raise ValueError(f"frame window {index} reported incomplete coverage")

            child_chunk = VideoChunkContext(
                chunk_id=stable_id(
                    "pwin",
                    chunk.chunk_id,
                    index,
                    round(offset, 6),
                    round(duration, 6),
                ),
                animal_id=chunk.animal_id,
                enclosure_id=chunk.enclosure_id,
                start_ts=chunk.start_ts + timedelta(seconds=offset),
                end_ts=chunk.start_ts + timedelta(seconds=offset + duration),
            )
            child_observations = normalize_batch(
                batch,
                child_chunk,
                provider="openai",
                provider_model=self.model,
                evidence_kind=EvidenceKind.FRAME_SAMPLED_PROVIDER,
            )
            for child_observation in child_observations:
                observations.append(
                    child_observation.model_copy(
                        update={
                            "observation_id": stable_id(
                                "obs",
                                chunk.chunk_id,
                                "openai-frame-window",
                                index,
                                child_observation.observation_id,
                            ),
                            "chunk_id": chunk.chunk_id,
                            "evidence": ("Frame-sampled review: " + child_observation.evidence),
                        }
                    )
                )
            uncertainty.extend(f"Window {offset:.3f}s: {item}" for item in batch.uncertainty)

        observations.sort(
            key=lambda item: (
                item.start_ts,
                item.end_ts,
                item.behavior.value,
                item.observation_id,
            )
        )
        return ProviderAnalysis(observations=observations, uncertainty=uncertainty)

    def _analyze_frames(
        self,
        frames: list[Any],
        duration_seconds: float,
    ) -> ProviderBatch:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"This window is {duration_seconds:.3f} seconds long. "
                    f"Frames are sampled at approximately {self.sample_fps:.3f} fps."
                ),
            }
        ]
        for frame in frames:
            encoded = _jpeg_data_url(frame.image)
            content.extend(
                [
                    {
                        "type": "input_text",
                        "text": f"Frame t={frame.relative_seconds:.3f} seconds",
                    },
                    {
                        "type": "input_image",
                        "image_url": encoded,
                        "detail": "low",
                    },
                ]
            )

        self.attempt_count += 1
        response = self.client.responses.parse(
            model=self.model,
            instructions=OPENAI_FRAME_PROMPT,
            input=[{"role": "user", "content": content}],
            text_format=ProviderBatch,
            reasoning={"effort": "low"},
            max_output_tokens=4000,
            store=False,
        )
        batch = response.output_parsed
        if batch is None:
            raise ValueError("OpenAI returned no parsed frame analysis")
        validated = ProviderBatch.model_validate(batch)
        _validate_observation_frame_timestamps(validated, frames)
        return validated


def _balanced_windows(duration_seconds: float, maximum_seconds: float) -> list[tuple[float, float]]:
    count = max(1, ceil(duration_seconds / maximum_seconds))
    width = duration_seconds / count
    return [(index * width, width) for index in range(count)]


def _validate_frame_window(frames: list[Any], duration: float, sample_fps: float) -> None:
    if not frames:
        raise ValueError("frame window decoded no frames")
    minimum_count = max(1, int(duration * sample_fps) - 1)
    if len(frames) < minimum_count:
        raise ValueError("frame window ended before its requested duration")
    timestamps = [frame.relative_seconds for frame in frames]
    if timestamps != sorted(timestamps) or timestamps[0] > 0.1:
        raise ValueError("frame window timestamps are not contiguous")
    maximum_tail = max(1.5 / sample_fps, 0.25)
    if duration - timestamps[-1] > maximum_tail:
        raise ValueError("frame window does not reach its requested end")


def _validate_observation_frame_timestamps(
    batch: ProviderBatch,
    frames: list[Any],
) -> None:
    labeled = {round(frame.relative_seconds, 3) for frame in frames}
    for observation in batch.observations:
        start = round(observation.relative_start_seconds, 3)
        end = round(observation.relative_end_seconds, 3)
        if start not in labeled or end not in labeled:
            raise ValueError("frame observation used an unsupplied timestamp")


def _jpeg_data_url(image: Any) -> str:
    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), 78],
    )
    if not ok:
        raise ValueError("could not encode sampled frame")
    payload = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{payload}"


def _safe_provider_error_detail(error: Exception) -> str:
    status = getattr(error, "status_code", None)
    body = getattr(error, "body", None)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = None
    code = body.get("code") if isinstance(body, dict) else None
    diagnostics = []
    if isinstance(status, int):
        diagnostics.append(f"status={status}")
    if isinstance(code, str) and code.replace("_", "").isalnum():
        diagnostics.append(f"code={code}")
    prefix = f"{type(error).__name__}"
    if diagnostics:
        prefix += " " + " ".join(diagnostics)
    return f"{prefix}: structured analysis unavailable"


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
