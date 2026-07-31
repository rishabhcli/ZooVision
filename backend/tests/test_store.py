from datetime import UTC, datetime, timedelta

import pytest
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


def test_legacy_detection_provenance_round_trips(tmp_path):
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
                detection_id="det-motion-1",
                chunk_id="chunk-1",
                track_id="track-cat-1",
                relative_seconds=4.5,
                box=BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4),
                score=0.91,
                source=DetectionSource.MOTION_REGION,
                label=None,
                class_id=None,
                model="mog2-v1",
            )
        ]
    )

    row = store.detections_for_chunk("chunk-1")[0]

    assert row["source"] == "motion_region"
    assert row["label"] is None
    assert row["class_id"] is None
    assert row["model"] == "mog2-v1"


def test_motion_replacement_preserves_yolo_and_replaces_only_motion(tmp_path):
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    store.upsert_video_chunk(
        chunk_id="chunk-1",
        enclosure_id="ENC-01",
        camera_id="CAM-01",
        start_ts="2026-07-30T02:00:00+00:00",
        end_ts="2026-07-30T02:02:00+00:00",
        source_path="uploads/birds.mp4",
        source_offset_seconds=0,
        content_sha256="sha",
        status="analyzed",
    )
    yolo = Detection(
        detection_id="det-yolo",
        chunk_id="chunk-1",
        track_id="track-yolo",
        relative_seconds=4.0,
        box=BoundingBox(x=0.1, y=0.2, width=0.2, height=0.3),
        score=0.88,
        source=DetectionSource.YOLOV8_OBJECT,
        label="bird",
        class_id=14,
        model="yolov8n.pt",
    )
    stale_motion = Detection(
        detection_id="det-motion-old",
        chunk_id="chunk-1",
        track_id="track-motion-old",
        relative_seconds=4.0,
        box=BoundingBox(x=0.4, y=0.3, width=0.1, height=0.1),
        score=0.4,
        source=DetectionSource.MOTION_REGION,
    )
    replacement = Detection(
        detection_id="det-motion-new",
        chunk_id="chunk-1",
        track_id="track-motion-new",
        relative_seconds=5.0,
        box=BoundingBox(x=0.5, y=0.4, width=0.08, height=0.09),
        score=0.72,
        source=DetectionSource.MOTION_REGION,
        label="bird",
        model="content-bound-background-v1",
    )
    store.save_detections([yolo, stale_motion])

    assert store.replace_chunk_motion_detections("chunk-1", [replacement]) == 1

    rows = store.detections_for_chunk("chunk-1")
    assert {row["detection_id"] for row in rows} == {"det-yolo", "det-motion-new"}
    assert next(row for row in rows if row["detection_id"] == "det-yolo") == {
        "detection_id": "det-yolo",
        "chunk_id": "chunk-1",
        "track_id": "track-yolo",
        "relative_seconds": 4.0,
        "box": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.3},
        "score": 0.88,
        "source": "yolov8_object",
        "label": "bird",
        "class_id": 14,
        "model": "yolov8n.pt",
    }


def test_motion_replacement_rejects_non_motion_without_changing_rows(tmp_path):
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    store.upsert_video_chunk(
        chunk_id="chunk-1",
        enclosure_id="ENC-01",
        camera_id="CAM-01",
        start_ts="2026-07-30T02:00:00+00:00",
        end_ts="2026-07-30T02:02:00+00:00",
        source_path="uploads/birds.mp4",
        source_offset_seconds=0,
        content_sha256="sha",
        status="analyzed",
    )
    yolo = Detection(
        detection_id="det-yolo",
        chunk_id="chunk-1",
        track_id="track-yolo",
        relative_seconds=4.0,
        box=BoundingBox(x=0.1, y=0.2, width=0.2, height=0.3),
        score=0.88,
        source=DetectionSource.YOLOV8_OBJECT,
        label="bird",
        class_id=14,
        model="yolov8n.pt",
    )
    store.save_detections([yolo])
    before = store.detections_for_chunk("chunk-1")

    with pytest.raises(ValueError, match="only motion_region"):
        store.replace_chunk_motion_detections("chunk-1", [yolo])

    assert store.detections_for_chunk("chunk-1") == before


def test_yolo_replacement_preserves_motion_rows(tmp_path):
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    store.upsert_video_chunk(
        chunk_id="chunk-1",
        enclosure_id="ENC-01",
        camera_id="CAM-01",
        start_ts="2026-07-30T02:00:00+00:00",
        end_ts="2026-07-30T02:02:00+00:00",
        source_path="uploads/birds.mp4",
        source_offset_seconds=0,
        content_sha256="sha",
        status="analyzed",
    )
    motion = Detection(
        detection_id="det-motion",
        chunk_id="chunk-1",
        track_id="track-motion",
        relative_seconds=5.0,
        box=BoundingBox(x=0.5, y=0.4, width=0.08, height=0.09),
        score=0.72,
        source=DetectionSource.MOTION_REGION,
        label="bird",
        model="content-bound-background-v1",
    )
    stale_yolo = Detection(
        detection_id="det-yolo-old",
        chunk_id="chunk-1",
        track_id="track-yolo-old",
        relative_seconds=4.0,
        box=BoundingBox(x=0.1, y=0.2, width=0.2, height=0.3),
        score=0.3,
        source=DetectionSource.YOLOV8_OBJECT,
        label="bear",
        class_id=21,
        model="yolov8n.pt",
    )
    replacement = stale_yolo.model_copy(
        update={
            "detection_id": "det-yolo-new",
            "track_id": "track-yolo-new",
            "score": 0.9,
            "label": "bird",
            "class_id": 14,
        }
    )
    store.save_detections([motion, stale_yolo])

    assert store.replace_chunk_yolo_detections("chunk-1", [replacement]) == 1

    rows = store.detections_for_chunk("chunk-1")
    assert {row["detection_id"] for row in rows} == {"det-motion", "det-yolo-new"}
    preserved_motion = next(row for row in rows if row["detection_id"] == "det-motion")
    assert preserved_motion["model"] == "content-bound-background-v1"
    assert preserved_motion["label"] == "bird"
