from datetime import UTC, datetime, timedelta

from zoovision.domain import AlertAction, Behavior, EventRecord, Severity
from zoovision.store import SQLiteStore


def test_repeat_event_write_is_idempotent(tmp_path):
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    store.upsert_animal(
        animal_id="animal-rex",
        name="Rex",
        species="African painted dog",
        enclosure_id="enc-07",
        baseline_state="active",
    )
    event = EventRecord(
        event_id="evt-stable",
        animal_id="animal-rex",
        enclosure_id="enc-07",
        behavior=Behavior.PACING,
        start_ts=datetime(2026, 7, 30, 2, tzinfo=UTC),
        end_ts=datetime(2026, 7, 30, 2, tzinfo=UTC) + timedelta(minutes=14),
        severity=Severity.MODERATE,
        rule_fired="R005_PACING_10M",
        action=AlertAction.OBSERVE,
        confidence=0.9,
        source_observation_ids=["obs-1"],
        created_at=datetime.now(UTC),
    )
    store.save_event(event)
    store.save_event(event)
    assert store.event_count() == 1
    assert store.dump_table("event_sources") == [
        {"event_id": "evt-stable", "observation_id": "obs-1"}
    ]
