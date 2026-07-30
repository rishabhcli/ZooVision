from datetime import UTC, datetime, timedelta

from zoovision.domain import Behavior, Observation
from zoovision.stitching import stitch_observations

START = datetime(2026, 7, 30, 2, 0, tzinfo=UTC)


def observation(identifier: str, chunk: str, start_minute: float, end_minute: float):
    return Observation(
        observation_id=identifier,
        animal_id="animal-rex",
        enclosure_id="enc-07",
        chunk_id=chunk,
        behavior=Behavior.PACING,
        start_ts=START + timedelta(minutes=start_minute),
        end_ts=START + timedelta(minutes=end_minute),
        confidence=0.9,
        evidence="Repeated walking along the same route.",
        provider="fixture",
        provider_model="fixture-v1",
    )


def test_cross_chunk_observations_stitch_into_one_continuous_event():
    stitched = stitch_observations(
        [
            observation("obs-1", "chunk-1", 0, 14.9),
            observation("obs-2", "chunk-2", 15, 22),
        ]
    )
    assert len(stitched) == 1
    assert stitched[0].duration_minutes == 22
    assert stitched[0].source_chunk_ids == ["chunk-1", "chunk-2"]


def test_gap_breaks_continuity():
    stitched = stitch_observations(
        [
            observation("obs-1", "chunk-1", 0, 5),
            observation("obs-2", "chunk-2", 6, 12),
        ]
    )
    assert len(stitched) == 2
