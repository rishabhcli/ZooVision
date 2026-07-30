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
    DataGap,
    Detection,
    EvidenceKind,
    ShiftMode,
)
from zoovision.ingest import (
    CompositeAnalyzer,
    IngestRequest,
    MotionEvidenceAnalyzer,
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


def _detection(seconds: float, track: str = "trk-1") -> Detection:
    return Detection(
        detection_id=f"det-{track}-{seconds}",
        chunk_id="chunk-1",
        track_id=track,
        relative_seconds=seconds,
        box=BoundingBox(x=0.2, y=0.2, width=0.2, height=0.2),
        score=0.6,
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


def test_motion_analyzer_reports_a_sustained_still_period() -> None:
    analyzer = MotionEvidenceAnalyzer([_detection(0.5)], min_inactivity_minutes=1.0)

    analysis = analyzer.analyze(_chunk(600))

    still = [o for o in analysis.observations if o.behavior is Behavior.INACTIVITY]
    assert len(still) == 1
    assert still[0].evidence_kind is EvidenceKind.MEASURED_MOTION
    assert still[0].provider == "zoovision-motion"
    assert "No motion region was measured" in still[0].evidence


def test_motion_analyzer_reports_measured_motion_without_naming_a_behavior() -> None:
    detections = [_detection(t) for t in (10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0)]
    analyzer = MotionEvidenceAnalyzer(detections, min_inactivity_minutes=1.0)

    analysis = analyzer.analyze(_chunk(600))

    motion = [o for o in analysis.observations if o.behavior is Behavior.OTHER]
    assert motion, "a run of motion regions must be recorded"
    # Motion alone cannot support pacing, fighting, or any named behavior.
    assert not {o.behavior for o in analysis.observations} & {
        Behavior.PACING,
        Behavior.FIGHTING,
        Behavior.VOMITING,
    }
    assert "does not identify" in motion[0].evidence


def test_motion_analyzer_on_an_empty_track_reports_the_whole_segment_as_still() -> None:
    analysis = MotionEvidenceAnalyzer([], min_inactivity_minutes=1.0).analyze(_chunk(600))

    assert [o.behavior for o in analysis.observations] == [Behavior.INACTIVITY]
    assert analysis.data_gap is None


def test_motion_observations_are_timezone_correct_and_inside_the_chunk() -> None:
    analysis = MotionEvidenceAnalyzer([_detection(5.0)], min_inactivity_minutes=1.0).analyze(
        _chunk(600)
    )

    for observation in analysis.observations:
        assert observation.start_ts.tzinfo is not None
        assert observation.start_ts >= START
        assert observation.end_ts <= START + timedelta(seconds=600)


class _StubProvider:
    def __init__(self, analysis: ProviderAnalysis):
        self.analysis = analysis

    def safe_analyze_file(self, path, chunk):  # noqa: ANN001
        del path, chunk
        return self.analysis

    def safe_analyze_url(self, video_url, chunk):  # noqa: ANN001
        del video_url, chunk
        return self.analysis


def test_composite_analyzer_keeps_provider_data_gap_and_adds_motion_evidence() -> None:
    gap = DataGap(
        gap_id="gap-1",
        enclosure_id="ENC-01",
        chunk_id="chunk-1",
        start_ts=START,
        end_ts=START + timedelta(seconds=600),
        reason="provider_analysis_failed",
    )
    composite = CompositeAnalyzer(
        primary=_StubProvider(ProviderAnalysis(observations=[], data_gap=gap)),
        motion=MotionEvidenceAnalyzer([], min_inactivity_minutes=1.0),
    )

    analysis = composite.safe_analyze_file("ignored.mp4", _chunk(600))

    assert analysis.data_gap is gap, "a provider failure must remain a recorded gap"
    assert analysis.observations, "the motion track survives a provider failure"


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
        detector_config=DetectorConfig(sample_fps=2.0, warmup_frames=1),
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
            use_provider=False,
        )
    )

    assert job.status == "complete", job.error
    assert job.total_segments >= 2
    assert job.completed_segments == job.total_segments
    assert job.analyzer == "motion"
    assert job.probe is not None and job.probe.duration_seconds > 0

    chunks = store.dump_table("video_chunks")
    assert len(chunks) == job.total_segments
    assert all(chunk["source_path"] == "uploads/any.mp4" for chunk in chunks)

    # Wall-clock provenance: each segment starts after the one before it.
    starts = [segment.start_ts for segment in job.segments]
    assert starts == sorted(starts)
    assert starts[0] == START

    assert store.dump_table("observations"), "an uploaded video must yield observations"
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
        use_provider=False,
    )

    service.run(request)
    first_chunks = len(store.dump_table("video_chunks"))
    first_observations = len(store.dump_table("observations"))
    service.run(request)

    assert len(store.dump_table("video_chunks")) == first_chunks
    assert len(store.dump_table("observations")) == first_observations


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
            use_provider=False,
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


def test_intermittent_detections_stay_one_span_instead_of_vanishing() -> None:
    """A steadily moving body is routinely missed for a few sampled frames.

    Splitting a run on the sampling step fragments continuous movement into
    slivers that the activity floor then discards, so real motion would be
    reported as no motion at all.
    """
    # Two seconds of motion, sampled at 2 fps, with single dropped samples.
    moments = [0.0, 0.5, 1.5, 2.0, 3.0, 3.5, 4.5, 5.0, 6.0, 6.5, 7.5, 8.0]
    analyzer = MotionEvidenceAnalyzer(
        [_detection(t) for t in moments],
        sample_fps=2.0,
        min_inactivity_minutes=1.0,
    )

    spans = analyzer._motion_spans(600.0)
    motion = [span for span in spans if span[0] == "motion"]

    assert len(motion) == 1, f"gaps of one sample must not split the run: {motion}"
    assert motion[0][1] == 0.0
    assert motion[0][2] >= 8.0


def test_a_genuine_pause_still_separates_two_motion_spans() -> None:
    analyzer = MotionEvidenceAnalyzer(
        [_detection(t) for t in [i * 0.5 for i in range(12)] + [60.0 + i * 0.5 for i in range(12)]],
        sample_fps=2.0,
        min_inactivity_minutes=1.0,
        merge_gap_seconds=2.0,
    )

    motion = [span for span in analyzer._motion_spans(600.0) if span[0] == "motion"]

    assert len(motion) == 2, "a minute of stillness is not one continuous movement"
