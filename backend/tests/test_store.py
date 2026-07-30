from datetime import UTC, datetime, timedelta

from zoovision.domain import (
    AlertAction,
    Behavior,
    BoundingBox,
    Detection,
    DetectionSource,
    EventRecord,
    Severity,
    ShiftMode,
)
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
        explanation_facts=["Continuous pacing lasted 14.0 minutes."],
        rule_version="2026-07-30.v1",
        shift_mode=ShiftMode.NIGHT,
        created_at=datetime.now(UTC),
    )
    store.save_event(event)
    store.save_event(event)
    assert store.event_count() == 1
    assert store.dump_table("event_sources") == [
        {"event_id": "evt-stable", "observation_id": "obs-1"}
    ]


def test_yolo_detection_provenance_round_trips(tmp_path):
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    store.upsert_video_chunk(
        chunk_id="chunk-1",
        enclosure_id="ENC-01",
        camera_id="CAM-01",
        start_ts="2026-07-30T02:00:00+00:00",
        end_ts="2026-07-30T02:02:00+00:00",
        source_path="fixtures/cat.mp4",
        source_offset_seconds=0,
        content_sha256="sha",
        status="ready",
    )
    store.save_detections(
        [
            Detection(
                detection_id="det-yolo-1",
                chunk_id="chunk-1",
                track_id="track-cat-1",
                relative_seconds=4.5,
                box=BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4),
                score=0.91,
                source=DetectionSource.YOLOV8_OBJECT,
                label="cat",
                class_id=15,
                model="yolov8n.pt",
            )
        ]
    )

    row = store.detections_for_chunk("chunk-1")[0]

    assert row["source"] == "yolov8_object"
    assert row["label"] == "cat"
    assert row["class_id"] == 15
    assert row["model"] == "yolov8n.pt"
