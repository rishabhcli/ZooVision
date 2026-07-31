from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError
from twelvelabs.core import ApiError
from zoovision.domain import Behavior, EvidenceKind
from zoovision.providers import (
    OPENAI_FRAME_MAX_IMAGES,
    OPENAI_FRAME_PROMPT,
    OpenAIFrameAnalyzer,
    ProviderBatch,
    TwelveLabsAnalyzer,
    VideoChunkContext,
    fixture_batch,
    normalize_batch,
    provider_response_schema,
)


@pytest.fixture
def chunk():
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    return VideoChunkContext(
        chunk_id="chunk-1",
        animal_id="animal-1",
        enclosure_id="ENC-01",
        start_ts=start,
        end_ts=start + timedelta(minutes=15),
    )


def test_provider_timestamps_are_normalized_with_chunk_provenance(chunk):
    batch = fixture_batch(
        {
            "observations": [
                {
                    "behavior": "pacing",
                    "relative_start_seconds": 30,
                    "relative_end_seconds": 90,
                    "confidence": 0.8,
                    "evidence": "Repeated route was visible.",
                    "activity_label": "Boundary patrol",
                    "provider_item_id": "segment-a",
                }
            ],
            "coverage_complete": True,
            "uncertainty": [],
        }
    )
    observations = normalize_batch(
        batch,
        chunk,
        provider="fixture",
        provider_model="strict-v1",
    )
    assert observations[0].chunk_id == "chunk-1"
    assert observations[0].start_ts == chunk.start_ts + timedelta(seconds=30)
    assert observations[0].provider_item_id == "segment-a"
    assert observations[0].activity_label == "Boundary patrol"


def test_provider_cannot_return_severity():
    with pytest.raises(ValidationError):
        ProviderBatch.model_validate(
            {
                "observations": [],
                "coverage_complete": True,
                "uncertainty": [],
                "severity": "HIGH",
            }
        )


def test_provider_schema_removes_live_unsupported_numeric_constraints():
    rendered = str(provider_response_schema())
    for keyword in (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    ):
        assert keyword not in rendered


def test_openai_frame_prompt_separates_review_coverage_from_visibility():
    assert "whether you reviewed every supplied frame" in OPENAI_FRAME_PROMPT
    assert "no visible animal" in OPENAI_FRAME_PROMPT
    assert "empty observations list" in OPENAI_FRAME_PROMPT
    assert "could not be inspected at all" in OPENAI_FRAME_PROMPT


def test_observation_outside_chunk_is_rejected(chunk):
    batch = ProviderBatch.model_validate(
        {
            "observations": [
                {
                    "behavior": Behavior.RESTING,
                    "relative_start_seconds": 850,
                    "relative_end_seconds": 950,
                    "confidence": 0.9,
                    "evidence": "Stationary posture.",
                }
            ],
            "coverage_complete": True,
        }
    )
    with pytest.raises(ValueError, match="exceeds"):
        normalize_batch(batch, chunk, provider="fixture", provider_model="strict-v1")


def test_subsecond_provider_overshoot_is_clamped_to_chunk_end(chunk):
    batch = ProviderBatch.model_validate(
        {
            "observations": [
                {
                    "behavior": Behavior.OTHER,
                    "relative_start_seconds": 899,
                    "relative_end_seconds": 900.2,
                    "confidence": 0.8,
                    "evidence": "Visible movement at the end of the clip.",
                }
            ],
            "coverage_complete": True,
        }
    )
    observation = normalize_batch(
        batch,
        chunk,
        provider="fixture",
        provider_model="strict-v1",
    )[0]
    assert observation.end_ts == chunk.end_ts


def test_zero_length_provider_marker_is_excluded_with_uncertainty():
    batch = ProviderBatch.model_validate(
        {
            "observations": [
                {
                    "behavior": Behavior.EXITING_FRAME,
                    "relative_start_seconds": 29,
                    "relative_end_seconds": 29,
                    "confidence": 0.7,
                    "evidence": "The animal reaches the frame boundary.",
                }
            ],
            "coverage_complete": True,
        }
    )

    assert batch.observations == []
    assert "zero-length" in batch.uncertainty[0]


class FailingAnalyzeClient:
    def __init__(self):
        self.calls = 0

    def analyze(self, **_kwargs):
        self.calls += 1
        raise OSError("secret provider response")


def test_provider_failure_becomes_data_gap_without_leaking_detail(chunk):
    client = FailingAnalyzeClient()
    result = TwelveLabsAnalyzer("unused", client=client).safe_analyze_url(
        "https://example.com/video.mp4",
        chunk,
    )
    assert client.calls == 3
    assert result.observations == []
    assert result.data_gap is not None
    assert result.data_gap.reason == "provider_analysis_failed"
    assert "secret" not in (result.data_gap.detail or "")


def test_local_provider_file_enforces_base64_size_limit(tmp_path, chunk):
    path = tmp_path / "too-large.mp4"
    with path.open("wb") as handle:
        handle.truncate(22 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        TwelveLabsAnalyzer("unused", client=FailingAnalyzeClient()).analyze_file(path, chunk)


class _FakeFrameResponses:
    def __init__(
        self,
        *,
        incomplete_call: int | None = None,
        invalid_timestamp_call: int | None = None,
    ):
        self.calls: list[dict] = []
        self.incomplete_call = incomplete_call
        self.invalid_timestamp_call = invalid_timestamp_call

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        complete = len(self.calls) != self.incomplete_call
        labels = [
            item["text"]
            for item in kwargs["input"][0]["content"]
            if item["type"] == "input_text" and item["text"].startswith("Frame t=")
        ]
        first = float(labels[0].split("=")[1].split()[0])
        second = float(labels[1].split("=")[1].split()[0])
        if len(self.calls) == self.invalid_timestamp_call:
            second = first + 0.005
        return SimpleNamespace(
            output_parsed=ProviderBatch.model_validate(
                {
                    "observations": [
                        {
                            "behavior": "walking",
                            "relative_start_seconds": first,
                            "relative_end_seconds": second,
                            "confidence": 0.8,
                            "evidence": "A squirrel is visible moving between two positions.",
                            "activity_label": "Squirrel crossing the visible frame",
                        }
                    ],
                    "coverage_complete": complete,
                    "uncertainty": [],
                }
            )
        )


class _FakeFrameClient:
    def __init__(
        self,
        *,
        incomplete_call: int | None = None,
        invalid_timestamp_call: int | None = None,
    ):
        self.responses = _FakeFrameResponses(
            incomplete_call=incomplete_call,
            invalid_timestamp_call=invalid_timestamp_call,
        )


def _sampled_frames(
    *_args,
    duration_seconds,
    sample_fps,
    max_frames,
    **_kwargs,
):
    count = min(max_frames, max(2, int(duration_seconds * sample_fps)))
    for index in range(count):
        yield SimpleNamespace(
            relative_seconds=(duration_seconds - 0.5) * index / (count - 1),
            image=np.full((32, 48, 3), index, dtype=np.uint8),
        )


def test_openai_frame_analysis_covers_every_bounded_window(monkeypatch, tmp_path):
    monkeypatch.setattr("zoovision.providers.sample_video_frames", _sampled_frames)
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    parent = VideoChunkContext(
        chunk_id="parent-chunk",
        animal_id="animal-squirrel",
        enclosure_id="ENC-BACKYARD",
        start_ts=start,
        end_ts=start + timedelta(seconds=125),
    )
    client = _FakeFrameClient()
    analyzer = OpenAIFrameAnalyzer(
        "unused",
        model="gpt-5.6-luna",
        client=client,
    )

    result = analyzer.safe_analyze_file(tmp_path / "unused.mp4", parent)

    assert result.data_gap is None
    assert analyzer.attempt_count == 2
    assert len(result.observations) == 2
    assert len({item.observation_id for item in result.observations}) == 2
    assert all(item.chunk_id == parent.chunk_id for item in result.observations)
    assert all(item.provider == "openai" for item in result.observations)
    assert all(
        item.evidence_kind is EvidenceKind.FRAME_SAMPLED_PROVIDER for item in result.observations
    )
    assert all(item.evidence.startswith("Frame-sampled review:") for item in result.observations)
    assert result.observations[0].start_ts == parent.start_ts
    assert result.observations[-1].start_ts > parent.start_ts + timedelta(seconds=60)
    for call in client.responses.calls:
        content = call["input"][0]["content"]
        images = [item for item in content if item["type"] == "input_image"]
        assert 1 <= len(images) <= OPENAI_FRAME_MAX_IMAGES
        for position, item in enumerate(content):
            if item["type"] == "input_image":
                assert content[position - 1]["text"].startswith("Frame t=")
        assert call["text_format"] is ProviderBatch
        assert call["store"] is False


def test_openai_frame_analysis_keeps_a_gap_when_one_window_is_incomplete(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr("zoovision.providers.sample_video_frames", _sampled_frames)
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    parent = VideoChunkContext(
        chunk_id="parent-chunk",
        animal_id="animal-squirrel",
        enclosure_id="ENC-BACKYARD",
        start_ts=start,
        end_ts=start + timedelta(seconds=125),
    )
    client = _FakeFrameClient(incomplete_call=2)
    analyzer = OpenAIFrameAnalyzer(
        "unused",
        model="gpt-5.6-luna",
        client=client,
    )

    result = analyzer.safe_analyze_file(tmp_path / "unused.mp4", parent)

    assert analyzer.attempt_count == 2
    assert result.observations == []
    assert result.data_gap is not None
    assert result.data_gap.chunk_id == parent.chunk_id
    assert result.data_gap.start_ts == parent.start_ts
    assert result.data_gap.end_ts == parent.end_ts
    assert result.data_gap.reason == "provider_frame_analysis_failed"


def test_openai_frame_analysis_rejects_unsupplied_model_timestamps(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr("zoovision.providers.sample_video_frames", _sampled_frames)
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    parent = VideoChunkContext(
        chunk_id="parent-chunk",
        animal_id="animal-squirrel",
        enclosure_id="ENC-BACKYARD",
        start_ts=start,
        end_ts=start + timedelta(seconds=116.78345),
    )
    client = _FakeFrameClient(invalid_timestamp_call=1)
    analyzer = OpenAIFrameAnalyzer(
        "unused",
        model="gpt-5.6-luna",
        client=client,
    )

    result = analyzer.safe_analyze_file(tmp_path / "unused.mp4", parent)

    assert analyzer.attempt_count == 1
    assert result.observations == []
    assert result.data_gap is not None
    assert result.data_gap.reason == "provider_frame_analysis_failed"


def test_twelvelabs_capacity_error_keeps_only_sanitized_status_and_code(chunk):
    class CapacityClient:
        def analyze(self, **_kwargs):
            raise ApiError(
                status_code=422,
                body={
                    "code": "usage_limit_exceeded",
                    "message": "private account detail",
                },
            )

    result = TwelveLabsAnalyzer("unused", client=CapacityClient()).safe_analyze_url(
        "https://example.com/video.mp4",
        chunk,
    )

    assert result.data_gap is not None
    assert result.data_gap.detail == (
        "ApiError status=422 code=usage_limit_exceeded: structured analysis unavailable"
    )
    assert "private account detail" not in result.data_gap.detail
