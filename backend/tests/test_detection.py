from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError
from zoovision.detection import (
    DetectorConfig,
    MediaToolingError,
    MotionRegionDetector,
    ObjectDetectorError,
    SampledFrame,
    YoloV8ObjectDetector,
    probe_video,
    run_media_tool,
)
from zoovision.domain import BoundingBox, DetectionSource

FRAME_HEIGHT = 180
FRAME_WIDTH = 320


def _static_background(seed: int = 7) -> np.ndarray:
    generator = np.random.default_rng(seed)
    return generator.integers(40, 60, (FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint8)


def _frames_with_moving_body(
    *,
    count: int = 40,
    box_size: int = 40,
    start_x: int = 20,
    step: int = 6,
) -> list[SampledFrame]:
    """Static scene for a warmup period, then one bright body crossing it."""
    background = _static_background()
    frames: list[SampledFrame] = []
    for index in range(count):
        image = background.copy()
        if index >= 10:
            left = start_x + (index - 10) * step
            top = 70
            if left + box_size < FRAME_WIDTH:
                image[top : top + box_size, left : left + box_size] = 245
        frames.append(SampledFrame(relative_seconds=index * 0.5, image=image))
    return frames


def _frames_static(count: int = 30) -> list[SampledFrame]:
    background = _static_background()
    return [SampledFrame(relative_seconds=i * 0.5, image=background.copy()) for i in range(count)]


def test_detector_localizes_a_moving_body() -> None:
    detections = MotionRegionDetector().detect(_frames_with_moving_body(), chunk_id="chunk-1")

    assert detections, "a body crossing a static scene must produce motion regions"
    assert all(d.source is DetectionSource.MOTION_REGION for d in detections)
    assert all(d.chunk_id == "chunk-1" for d in detections)
    # The body is 40px tall at y=70 in a 180px frame, so every box must sit in
    # that horizontal band rather than drifting across the whole frame.
    for detection in detections:
        assert 0.3 <= detection.box.y <= 0.55
        assert detection.box.height <= 0.45


def test_detector_follows_the_body_from_left_to_right() -> None:
    detections = MotionRegionDetector().detect(_frames_with_moving_body(), chunk_id="chunk-1")

    ordered = sorted(detections, key=lambda d: d.relative_seconds)
    assert ordered[-1].box.x > ordered[0].box.x, "boxes must track the body's direction"


def test_static_scene_produces_no_motion_regions() -> None:
    assert MotionRegionDetector().detect(_frames_static(), chunk_id="chunk-1") == []


def test_a_track_never_claims_two_boxes_in_one_frame() -> None:
    detections = MotionRegionDetector(
        DetectorConfig(min_area_ratio=0.0005, max_regions_per_frame=8, min_fill_ratio=0.05)
    ).detect(_frames_with_moving_body(), chunk_id="chunk-1")

    seen = {(d.track_id, d.relative_seconds) for d in detections}
    assert len(seen) == len(detections)


def test_detection_is_deterministic() -> None:
    frames = _frames_with_moving_body()
    first = MotionRegionDetector().detect(frames, chunk_id="chunk-1")
    second = MotionRegionDetector().detect(_frames_with_moving_body(), chunk_id="chunk-1")

    assert [d.detection_id for d in first] == [d.detection_id for d in second]
    assert [d.box.model_dump() for d in first] == [d.box.model_dump() for d in second]


def test_warmup_frames_are_never_emitted() -> None:
    config = DetectorConfig(warmup_frames=12)
    detections = MotionRegionDetector(config).detect(_frames_with_moving_body(), chunk_id="chunk-1")

    assert all(d.relative_seconds >= 12 * 0.5 for d in detections)


def test_area_bounds_reject_regions_outside_the_configured_window() -> None:
    detections = MotionRegionDetector(DetectorConfig(min_area_ratio=0.9)).detect(
        _frames_with_moving_body(), chunk_id="chunk-1"
    )

    assert detections == []


def test_fill_ratio_threshold_drops_ragged_motion_but_keeps_a_body() -> None:
    """A diagonal streak spans a wide box while filling little of it.

    This is the shape signature of swaying vegetation, as opposed to the
    compact blob a moving body produces.
    """
    background = _static_background()
    streak: list[SampledFrame] = []
    blob: list[SampledFrame] = []
    for index in range(30):
        streak_image = background.copy()
        blob_image = background.copy()
        if index >= 10:
            for row in range(60, 140):
                left = 100 + (row - 60)
                streak_image[row, left : left + 12] = 245
            blob_image[60:140, 100:180] = 245
        streak.append(SampledFrame(relative_seconds=index * 0.5, image=streak_image))
        blob.append(SampledFrame(relative_seconds=index * 0.5, image=blob_image))

    permissive = DetectorConfig(min_fill_ratio=0.0)
    strict = DetectorConfig(min_fill_ratio=0.5)

    assert MotionRegionDetector(permissive).detect(streak, chunk_id="c"), (
        "a streak is motion and must be visible without the filter"
    )
    assert MotionRegionDetector(strict).detect(streak, chunk_id="c") == []
    assert MotionRegionDetector(strict).detect(blob, chunk_id="c"), (
        "the filter must keep a compact body"
    )


def test_bounding_box_rejects_regions_outside_the_frame() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x=0.8, y=0.1, width=0.5, height=0.1)
    with pytest.raises(ValidationError):
        BoundingBox(x=0.1, y=0.8, width=0.1, height=0.5)


def test_bounding_box_requires_a_positive_extent() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x=0.1, y=0.1, width=0.0, height=0.2)


def test_probe_video_rejects_a_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        probe_video(tmp_path / "absent.mp4")


def test_probe_video_rejects_a_file_that_is_not_video(tmp_path) -> None:
    broken = tmp_path / "notes.mp4"
    broken.write_bytes(b"this is not a video container")
    with pytest.raises(ValueError):
        probe_video(broken)


def test_missing_media_tool_reports_the_tool_not_a_bad_video(monkeypatch, tmp_path) -> None:
    """An absent binary is an operator problem, not a footage problem."""

    def absent(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "ffprobe")

    monkeypatch.setattr("zoovision.detection.subprocess.run", absent)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    with pytest.raises(MediaToolingError, match="not found on PATH"):
        probe_video(source)


def test_run_media_tool_passes_through_a_normal_failure(tmp_path) -> None:
    completed = run_media_tool(["ffprobe", "-v", "error", str(tmp_path / "nope.mp4")], timeout=30)

    assert completed.returncode != 0


def test_a_short_segment_still_finds_the_body() -> None:
    """Sensitivity must not depend on how many frames a segment happens to hold.

    OpenCV's automatic MOG2 rate adapts from its own frame count, so a short
    segment absorbs the body it is meant to find. The detector pins the rate.
    """
    short = _frames_with_moving_body(count=14)

    detections = MotionRegionDetector().detect(short, chunk_id="chunk-1")

    frames_with_motion = {d.relative_seconds for d in detections}
    assert len(frames_with_motion) >= 3, (
        f"a 14-frame segment must still surface the body, got {sorted(frames_with_motion)}"
    )


class _FakeYolo:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def predict(self, **options):
        self.calls.append(options)
        return [
            SimpleNamespace(
                boxes=SimpleNamespace(
                    xyxy=np.array([[32.0, 36.0, 160.0, 126.0]], dtype=np.float32),
                    conf=np.array([0.91], dtype=np.float32),
                    cls=np.array([15], dtype=np.float32),
                ),
                names={15: "cat"},
            )
            for _ in options["source"]
        ]


def test_yolo_preserves_label_model_and_track_provenance() -> None:
    model = _FakeYolo()
    config = DetectorConfig(yolo_batch_size=2)
    frames = [
        SampledFrame(relative_seconds=0.0, image=np.zeros((180, 320, 3), dtype=np.uint8)),
        SampledFrame(relative_seconds=0.5, image=np.zeros((180, 320, 3), dtype=np.uint8)),
    ]

    detections = YoloV8ObjectDetector(config, model=model).detect(
        frames,
        chunk_id="chunk-1",
    )

    assert len(detections) == 2
    assert {item.source for item in detections} == {DetectionSource.YOLOV8_OBJECT}
    assert {item.label for item in detections} == {"cat"}
    assert {item.class_id for item in detections} == {15}
    assert {item.model for item in detections} == {"yolov8n.pt"}
    assert len({item.track_id for item in detections}) == 1
    assert model.calls[0]["classes"] == list(range(14, 24))
    assert model.calls[0]["stream"] is True


def test_yolo_streams_every_sample_in_bounded_batches() -> None:
    model = _FakeYolo()
    config = DetectorConfig(yolo_batch_size=64)
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    frames = (SampledFrame(relative_seconds=index * 0.5, image=image) for index in range(1001))

    detections = YoloV8ObjectDetector(config, model=model).detect(
        frames,
        chunk_id="chunk-full",
    )

    assert len(detections) == 1001
    assert detections[-1].relative_seconds == 500.0
    assert len(model.calls) == 16
    assert max(len(call["source"]) for call in model.calls) == 64


def test_yolo_rejects_an_incomplete_result_batch() -> None:
    model = _FakeYolo()
    model.predict = lambda **options: []
    frames = [SampledFrame(relative_seconds=0.0, image=np.zeros((180, 320, 3), dtype=np.uint8))]

    with pytest.raises(ObjectDetectorError, match="returned 0 results"):
        YoloV8ObjectDetector(model=model).detect(frames, chunk_id="chunk-1")
