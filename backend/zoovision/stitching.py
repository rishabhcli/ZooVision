from __future__ import annotations

from datetime import timedelta

from .domain import Observation, StitchedObservation


def stitch_observations(
    observations: list[Observation],
    *,
    maximum_gap: timedelta = timedelta(seconds=30),
) -> list[StitchedObservation]:
    if not observations:
        return []

    ordered = sorted(
        observations,
        key=lambda item: (item.animal_id, item.behavior.value, item.start_ts, item.end_ts),
    )
    stitched: list[StitchedObservation] = []

    for observation in ordered:
        previous = stitched[-1] if stitched else None
        can_join = (
            previous is not None
            and previous.animal_id == observation.animal_id
            and previous.enclosure_id == observation.enclosure_id
            and previous.behavior is observation.behavior
            and observation.start_ts <= previous.end_ts + maximum_gap
        )

        if not can_join:
            stitched.append(
                StitchedObservation(
                    animal_id=observation.animal_id,
                    enclosure_id=observation.enclosure_id,
                    behavior=observation.behavior,
                    start_ts=observation.start_ts,
                    end_ts=observation.end_ts,
                    confidence=observation.confidence,
                    evidence=[observation.evidence],
                    source_observation_ids=[observation.observation_id],
                    source_chunk_ids=[observation.chunk_id],
                )
            )
            continue

        previous.end_ts = max(previous.end_ts, observation.end_ts)
        previous.confidence = min(previous.confidence, observation.confidence)
        previous.evidence.append(observation.evidence)
        previous.source_observation_ids.append(observation.observation_id)
        if observation.chunk_id not in previous.source_chunk_ids:
            previous.source_chunk_ids.append(observation.chunk_id)

    return stitched
