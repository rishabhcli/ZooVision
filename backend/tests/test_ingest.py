from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest
from zoovision.detection import DetectorConfig
from zoovision.domain import (
    Behavior,
    BoundingBox,
    Detection,
    DetectionSource,
    EvidenceKind,
    Observation,
    ShiftMode,
)
from zoovision.ingest import (
    IngestRequest,
    VideoIngestService,
    segment_video,
)
from zoovision.providers import ProviderAnalysis, VideoChunkContext
from zoovision.store import SQLiteStore

START = datetime(2026, 7, 30, 2, 0, tzinfo=UTC)


def _chunk(duration_seconds: float = 600.0) -> VideoChunkContext:
    return VideoChunkContext(
        chunk_id="chunk-1",
        animal_id="animal-1",
        enclosure_id="ENC-01",
        start_ts=START,
        end_ts=START + timedelta(seconds=duration_seconds),
    )


def _make_video(path: Path, *, seconds: int = 8) -> Path:
    """Write a real file containing one unmistakably moving body.

    Frames are drawn here rather than sourced from an ffmpeg synthetic pattern:
    ``testsrc`` renders differently across ffmpeg builds, so whether the
    detector found motion in it varied by machine. A bright block crossing a
    dark field is decisive on any build, which keeps this test about the ingest
    pipeline instead of about the encoder.
    """
    width, height, fps = 320, 240, 10
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():  # pragma: no cover - environment guard
        raise RuntimeError("OpenCV could not open a video writer")
    try:
        for index in range(fps * seconds):
            frame = np.full((height, width, 3), 30, dtype=np.uint8)
            left = 20 + (index * 8) % (width - 110)
            cv2.rectangle(frame, (left, 90), (left + 70, 160), (245, 245, 245), -1)
            writer.write(frame)
    finally:
        writer.release()
    return path


class _StubProvider:
    def safe_analyze_file(self, path, chunk):  # noqa: ANN001
        del path
        return self._analysis(chunk)

    def safe_analyze_url(self, video_url, chunk):  # noqa: ANN001
        del video_url
        return self._analysis(chunk)

    @staticmethod
    def _analysis(chunk: VideoChunkContext) -> ProviderAnalysis:
        return ProviderAnalysis(
            observations=[
                Observation(
                    observation_id=f"obs-{chunk.chunk_id}",
                    animal_id=chunk.animal_id,
                    enclosure_id=chunk.enclosure_id,
                    chunk_id=chunk.chunk_id,
                    behavior=Behavior.OTHER,
                    start_ts=chunk.start_ts,
                    end_ts=min(chunk.end_ts, chunk.start_ts + timedelta(seconds=4)),
                    confidence=0.9,
                    evidence="TwelveLabs observed an animal moving through the enclosure.",
                    provider="twelvelabs",
                    provider_model="pegasus1.5",
                    evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
                    activity_label="Animal moving through enclosure",
                )
            ]
        )


def _stub_detections(path, *, chunk_id, duration_seconds, config):  # noqa: ANN001
    del path, config
    return [
        Detection(
            detection_id=f"det-{chunk_id}",
            chunk_id=chunk_id,
            track_id=f"track-{chunk_id}",
            relative_seconds=min(0.25, duration_seconds / 2),
            box=BoundingBox(x=0.1, y=0.2, width=0.3, height=0.4),
            score=0.9,
            source=DetectionSource.YOLOV8_OBJECT,
            label="cat",
            class_id=15,
            model="yolov8n.pt",
        )
    ]


def test_segment_video_splits_a_real_file(tmp_path: Path) -> None:
    source = _make_video(tmp_path / "source.mp4", seconds=8)

    pieces = segment_video(
        source,
        tmp_path / "segments",
        segment_seconds=2,
        max_segments=10,
    )

    assert len(pieces) >= 2
    offsets = [offset for _, offset, _, _ in pieces]
    assert offsets == sorted(offsets)
    assert offsets[0] == 0.0
    for _, _, duration, piece in pieces:
        assert duration > 0
        assert piece.is_file()


def test_segment_video_rejects_a_file_that_is_not_video(tmp_path: Path) -> None:
    broken = tmp_path / "notes.mp4"
    broken.write_bytes(b"not a container")

    with pytest.raises(ValueError):
        segment_video(broken, tmp_path / "out", segment_seconds=2, max_segments=4)


def _service(tmp_path: Path) -> tuple[VideoIngestService, SQLiteStore]:
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    raw_root = tmp_path / "raw"
    (raw_root / "uploads").mkdir(parents=True)
    service = VideoIngestService(
        store=store,
        raw_root=raw_root,
        analyzer_factory=_StubProvider,
        detector_config=DetectorConfig(),
        detector=_stub_detections,
        now=lambda: START,
    )
    return service, store


def test_resolve_source_rejects_a_path_outside_the_upload_root(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    (tmp_path / "secret.mp4").write_bytes(b"x")

    with pytest.raises((FileNotFoundError, ValueError)):
        service.resolve_source("../secret.mp4")


def test_resolve_source_rejects_an_unknown_name(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)

    with pytest.raises(FileNotFoundError):
        service.resolve_source("absent.mp4")


def test_ingest_runs_any_video_end_to_end(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    _make_video(tmp_path / "raw" / "uploads" / "any.mp4", seconds=32)

    job = service.run(
        IngestRequest(
            source_name="any.mp4",
            animal_id="animal-1",
            animal_name="Test Subject",
            species="Unknown",
            enclosure_id="ENC-01",
            camera_id="CAM-01",
            start_ts=START,
            shift_mode=ShiftMode.NIGHT,
            segment_seconds=10,
        )
    )

    assert job.status == "complete", job.error
    assert job.total_segments >= 2
    assert job.completed_segments == job.total_segments
    assert job.analyzer == "twelvelabs+yolo"
    assert job.probe is not None and job.probe.duration_seconds > 0
    assert job.detection_count == job.total_segments
    assert all(segment.detection_count == 1 for segment in job.segments)

    chunks = store.dump_table("video_chunks")
    assert len(chunks) == job.total_segments
    assert all(chunk["source_path"] == "uploads/any.mp4" for chunk in chunks)

    # Wall-clock provenance: each segment starts after the one before it.
    starts = [segment.start_ts for segment in job.segments]
    assert starts == sorted(starts)
    assert starts[0] == START

    assert store.dump_table("observations"), "an uploaded video must yield observations"
    detections = store.dump_table("detections")
    assert {item["chunk_id"] for item in detections} == {item["chunk_id"] for item in chunks}
    track = store.video_track("uploads/any.mp4")
    expected_times = sorted(
        round(float(chunk["source_offset_seconds"]) + 0.25, 3) for chunk in chunks
    )
    assert [item["video_seconds"] for item in track["detections"]] == expected_times
    assert {item["source"] for item in track["detections"]} == {"yolov8_object"}
    assert service.status(job.job_id).status == "complete"


def test_ingest_is_idempotent_for_the_same_video(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    _make_video(tmp_path / "raw" / "uploads" / "any.mp4", seconds=32)
    request = IngestRequest(
        source_name="any.mp4",
        animal_id="animal-1",
        animal_name="Test Subject",
        species="Unknown",
        enclosure_id="ENC-01",
        camera_id="CAM-01",
        start_ts=START,
        segment_seconds=10,
    )

    service.run(request)
    first_chunks = len(store.dump_table("video_chunks"))
    first_observations = len(store.dump_table("observations"))
    first_detections = len(store.dump_table("detections"))
    service.run(request)

    assert len(store.dump_table("video_chunks")) == first_chunks
    assert len(store.dump_table("observations")) == first_observations
    assert len(store.dump_table("detections")) == first_detections


def test_ingest_records_a_failure_as_job_state(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    broken = tmp_path / "raw" / "uploads" / "broken.mp4"
    broken.write_bytes(b"not a container")

    job = service.run(
        IngestRequest(
            source_name="broken.mp4",
            animal_id="animal-1",
            animal_name="Test Subject",
            species="Unknown",
            enclosure_id="ENC-01",
            camera_id="CAM-01",
            start_ts=START,
            segment_seconds=10,
        )
    )

    assert job.status == "failed"
    assert job.error
    assert service.status(job.job_id).status == "failed"


def test_ingest_request_requires_a_timezone_aware_start() -> None:
    with pytest.raises(ValueError):
        IngestRequest(
            source_name="any.mp4",
            animal_id="animal-1",
            animal_name="Test",
            species="Unknown",
            enclosure_id="ENC-01",
            camera_id="CAM-01",
            start_ts=datetime(2026, 7, 30, 2, 0),
        )


def test_ingest_request_rejects_a_path_in_the_source_name() -> None:
    with pytest.raises(ValueError):
        IngestRequest(
            source_name="../escape.mp4",
            animal_id="animal-1",
            animal_name="Test",
            species="Unknown",
            enclosure_id="ENC-01",
            camera_id="CAM-01",
            start_ts=START,
        )
