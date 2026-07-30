from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from zoovision.domain import Behavior, Observation


def test_observation_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Observation(
            observation_id="obs-1",
            animal_id="animal-rex",
            enclosure_id="enc-07",
            chunk_id="chunk-1",
            behavior=Behavior.PACING,
            start_ts=datetime(2026, 7, 30, 2, tzinfo=UTC),
            end_ts=datetime(2026, 7, 30, 2, 1, tzinfo=UTC),
            confidence=0.8,
            evidence="pacing",
            provider="fixture",
            provider_model="fixture-v1",
            invented_severity="HIGH",
        )


def test_observation_requires_timezone_aware_ordered_timestamps():
    with pytest.raises(ValidationError):
        Observation(
            observation_id="obs-1",
            animal_id="animal-rex",
            enclosure_id="enc-07",
            chunk_id="chunk-1",
            behavior=Behavior.PACING,
            start_ts=datetime(2026, 7, 30, 2),
            end_ts=datetime(2026, 7, 30, 2, 1),
            confidence=0.8,
            evidence="pacing",
            provider="fixture",
            provider_model="fixture-v1",
        )
