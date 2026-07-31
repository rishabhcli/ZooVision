from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from zoovision.domain import Behavior
from zoovision.providers import (
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
