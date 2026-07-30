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
    assert client.calls == 2
    assert result.observations == []
    assert result.data_gap is not None
    assert result.data_gap.reason == "provider_analysis_failed"
    assert "secret" not in (result.data_gap.detail or "")
