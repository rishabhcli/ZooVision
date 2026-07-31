from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from zoovision.detection import SampledFrame
from zoovision.domain import BoundingBox, Detection, DetectionSource

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "reprocess_detections.py"
SPEC = importlib.util.spec_from_file_location("reprocess_detections_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCRIPT
SPEC.loader.exec_module(SCRIPT)

REVIEWED_BACKGROUND_MODEL = SCRIPT.REVIEWED_BACKGROUND_MODEL
_arguments = SCRIPT._arguments
_combine_motion_detections = SCRIPT._combine_motion_detections
_reference_regions = SCRIPT._reference_regions
_reference_track_id = SCRIPT._reference_track_id
_select_sources = SCRIPT._select_sources


def _motion_detection(
    detection_id: str,
    *,
    box: BoundingBox,
    label: str | None = None,
    model: str | None = None,
) -> Detection:
    return Detection(
        detection_id=detection_id,
        chunk_id="chunk-1",
        track_id=f"track-{detection_id}",
        relative_seconds=10.0,
        box=box,
        score=0.8,
        source=DetectionSource.MOTION_REGION,
        label=label,
        model=model,
    )


def test_arguments_use_requested_small_animal_defaults() -> None:
    arguments = _arguments(["--source", "birds.mp4"])

    assert arguments.sample_fps == 5.0
    assert arguments.max_edge == 960
    assert arguments.min_area_ratio == 0.0002
    assert arguments.min_fill_ratio == 0.12
    assert arguments.max_regions == 8
    assert arguments.warmup_frames == 5
    assert arguments.staircase_background_pass is False
    assert arguments.rebuild_yolo is False
    assert arguments.yolo_image_size == 1280


def test_source_selection_accepts_unique_basename_and_rejects_ambiguity() -> None:
    available = ["uploads/birds.mp4", "fixtures/lion.mp4"]

    assert _select_sources(available, ["birds.mp4"], select_all=False) == ["uploads/birds.mp4"]
    assert _select_sources(available, None, select_all=True) == sorted(available)

    with pytest.raises(ValueError, match="ambiguous"):
        _select_sources(
            ["uploads/birds.mp4", "fixtures/birds.mp4"],
            ["birds.mp4"],
            select_all=False,
        )
    with pytest.raises(ValueError, match="invalid source selector"):
        _select_sources(available, ["../birds.mp4"], select_all=False)


def test_content_bound_reference_finds_roi_foreground_only() -> None:
    background = np.full((540, 960, 3), 100, dtype=np.uint8)
    frame = background.copy()
    frame[115:165, 525:595] = 220
    frame[100:170, 925:955] = 220
    reference_lab = cv2.cvtColor(background, cv2.COLOR_BGR2LAB)

    regions = _reference_regions(
        SampledFrame(relative_seconds=10.0, image=frame),
        reference_lab,
        max_regions=8,
    )

    assert len(regions) == 1
    box, score = regions[0]
    assert 0.53 <= box.x <= 0.56
    assert 0.2 <= box.y <= 0.23
    assert score > 0.5


def test_content_bound_box_wins_overlap_and_frame_cap_is_respected() -> None:
    reviewed = _motion_detection(
        "reviewed",
        box=BoundingBox(x=0.5, y=0.2, width=0.1, height=0.1),
        label="bird",
        model=REVIEWED_BACKGROUND_MODEL,
    )
    overlapping_mog = _motion_detection(
        "mog-overlap",
        box=BoundingBox(x=0.51, y=0.21, width=0.1, height=0.1),
    )
    separate_mog = _motion_detection(
        "mog-separate",
        box=BoundingBox(x=0.2, y=0.6, width=0.08, height=0.08),
    )

    combined = _combine_motion_detections(
        [overlapping_mog, separate_mog],
        [reviewed],
        max_regions=2,
    )

    assert {item.detection_id for item in combined} == {"reviewed", "mog-separate"}
    assert next(item for item in combined if item.detection_id == "reviewed").model == (
        "content-bound-background-v1"
    )


def test_content_bound_fast_birds_keep_distinct_tracks() -> None:
    config = SCRIPT.DetectorConfig()
    tracks = []
    first = _reference_track_id(
        tracks,
        BoundingBox(x=0.1, y=0.2, width=0.04, height=0.05),
        0.0,
        "chunk-1",
        set(),
        config,
    )
    second = _reference_track_id(
        tracks,
        BoundingBox(x=0.7, y=0.2, width=0.04, height=0.05),
        0.0,
        "chunk-1",
        {first},
        config,
    )

    next_first = _reference_track_id(
        tracks,
        BoundingBox(x=0.17, y=0.2, width=0.04, height=0.05),
        0.2,
        "chunk-1",
        set(),
        config,
    )
    next_second = _reference_track_id(
        tracks,
        BoundingBox(x=0.63, y=0.2, width=0.04, height=0.05),
        0.2,
        "chunk-1",
        {next_first},
        config,
    )

    assert next_first == first
    assert next_second == second
