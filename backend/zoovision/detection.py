"""Spatial localization and media probing for fixed-camera welfare footage.

YOLO provides sampled object-candidate boxes while MOG2 supplies a clearly
labeled motion fallback for wildlife outside COCO. TwelveLabs separately
produces temporal observations. Spatial detections never enter deterministic
welfare triage.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from itertools import batched
from math import ceil
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .domain import BoundingBox, Detection, DetectionSource
from .ids import stable_id


class MediaToolingError(RuntimeError):
    """A required media tool is missing from PATH.

    Distinct from a bad video: the operator needs to install something, not
    replace the footage, and an ingest job should say which.
    """


def run_media_tool(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg/ffprobe, turning an absent binary into a clear failure."""
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise MediaToolingError(
            f"{args[0]} is required for video ingest but was not found on PATH"
        ) from error


class ObjectDetectorError(RuntimeError):
    """YOLO could not load or complete inference for a video segment."""


@dataclass(frozen=True)
class SampledFrame:
    """One decoded frame plus its offset from the start of the chunk."""

    relative_seconds: float
    image: np.ndarray


class VideoProbe(BaseModel):
    """Container facts measured from a real file, never assumed."""

    model_config = ConfigDict(extra="forbid")

    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_rate: float = Field(gt=0)


class DetectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Five samples per second keeps fast wildlife boxes responsive without
    # pretending that the spatial review aid is a full-frame-rate tracker.
    sample_fps: float = Field(default=5.0, gt=0, le=30)
    yolo_enabled: bool = True
    yolo_model: str = Field(default="yolo11m.pt", min_length=1, max_length=200)
    yolo_device: str = Field(default="auto", min_length=1, max_length=40)
    yolo_confidence: float = Field(default=0.15, ge=0.01, le=1)
    yolo_iou: float = Field(default=0.45, ge=0, le=1)
    yolo_image_size: int = Field(default=640, ge=320, le=1280, multiple_of=32)
    yolo_batch_size: int = Field(default=8, ge=1, le=64)
    yolo_max_detections: int = Field(default=20, ge=1, le=100)
    frame_max_edge: int = Field(default=960, ge=320, le=2160)
    # COCO bird through giraffe. Restricting inference prevents people,
    # vehicles, and furniture from being shown as animal candidates.
    yolo_classes: tuple[int, ...] = tuple(range(14, 24))
    motion_enabled: bool = True
    min_area_ratio: float = Field(default=0.0003, gt=0, le=1)
    max_area_ratio: float = Field(default=0.5, gt=0, le=1)
    max_regions_per_frame: int = Field(default=6, ge=1, le=20)
    min_fill_ratio: float = Field(default=0.12, ge=0, le=1)
    motion_box_padding_ratio: float = Field(default=0.5, ge=0, le=4)
    motion_min_box_width: float = Field(default=0.025, ge=0, le=0.5)
    motion_min_box_height: float = Field(default=0.04, ge=0, le=0.5)
    warmup_frames: int = Field(default=5, ge=0)
    history: int = Field(default=90, ge=1)
    var_threshold: float = Field(default=32.0, gt=0)
    #: Explicit MOG2 adaptation rate. OpenCV's automatic rate is derived from
    #: how many frames it has seen, so a short segment adapts almost instantly
    #: and absorbs the body it is supposed to find: a 10-second segment
    #: surfaced 1 of 21 frames where a fixed rate surfaced all 20. Pinning it
    #: makes sensitivity a property of the configuration, not of segment length.
    learning_rate: float = Field(default=0.002, gt=0, le=1)
    iou_match_threshold: float = Field(default=0.15, ge=0, le=1)
    center_match_max_distance: float = Field(default=0.12, ge=0, le=1)
    center_match_max_area_ratio: float = Field(default=2.25, ge=1, le=100)
    center_match_max_gap_seconds: float = Field(default=0.45, gt=0, le=2)
    track_gap_tolerance_seconds: float = Field(default=2.0, ge=0)


class MotionRegionDetector:
    """Turns sampled frames into normalized, track-linked motion boxes."""

    def __init__(self, config: DetectorConfig | None = None):
        self.config = config or DetectorConfig()

    def detect(self, frames: Iterable[SampledFrame], *, chunk_id: str) -> list[Detection]:
        config = self.config
        subtractor = cv2.createBackgroundSubtractorMOG2(
            history=config.history,
            varThreshold=config.var_threshold,
            detectShadows=True,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        detections: list[Detection] = []
        tracks: list[_Track] = []

        for index, frame in enumerate(frames):
            gray = _to_gray(frame.image)
            mask = subtractor.apply(gray, learningRate=config.learning_rate)
            if index < config.warmup_frames:
                continue
            # MOG2 paints shadows at 127; keep only confident foreground.
            _, binary = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            claimed: set[str] = set()
            for box, score in self._regions(binary):
                track_id = self._assign_track(
                    tracks,
                    box,
                    frame.relative_seconds,
                    chunk_id,
                    claimed,
                )
                claimed.add(track_id)
                detections.append(
                    Detection(
                        detection_id=stable_id(
                            "det",
                            chunk_id,
                            round(frame.relative_seconds, 3),
                            round(box.x, 5),
                            round(box.y, 5),
                            round(box.width, 5),
                            round(box.height, 5),
                        ),
                        chunk_id=chunk_id,
                        track_id=track_id,
                        relative_seconds=round(frame.relative_seconds, 3),
                        box=box,
                        score=score,
                        source=DetectionSource.MOTION_REGION,
                    )
                )
        return detections

    def _regions(self, binary: np.ndarray) -> list[tuple[BoundingBox, float]]:
        config = self.config
        height, width = binary.shape[:2]
        frame_area = float(height * width)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found: list[tuple[BoundingBox, float, float]] = []
        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            if box_width <= 0 or box_height <= 0:
                continue
            area_ratio = (box_width * box_height) / frame_area
            if not config.min_area_ratio <= area_ratio <= config.max_area_ratio:
                continue
            contour_area = float(cv2.contourArea(contour))
            # How compactly the outline fills its own box. A body reads as a
            # roughly convex blob and scores high; ragged, elongated, or
            # L-shaped outlines from swaying foliage and branch edges score low.
            # Contours are external, so this measures outline shape rather than
            # interior density.
            fill = contour_area / float(box_width * box_height)
            if fill < config.min_fill_ratio:
                continue
            raw_box = BoundingBox(
                x=_clamp(x / width),
                y=_clamp(y / height),
                width=_clamp_span(box_width / width, _clamp(x / width)),
                height=_clamp_span(box_height / height, _clamp(y / height)),
            )
            found.append(
                (
                    _expand_motion_box(raw_box, config),
                    round(min(max(fill, 0.0), 1.0), 4),
                    contour_area / frame_area,
                )
            )
        # Rank by moved-pixel mass so the dominant body survives the per-frame
        # cap, then restore spatial order so output is stable across runs.
        found.sort(key=lambda item: (-item[2], item[0].x, item[0].y))
        capped = found[: config.max_regions_per_frame]
        capped.sort(key=lambda item: (item[0].x, item[0].y))
        return [(box, score) for box, score, _ in capped]

    def _assign_track(
        self,
        tracks: list[_Track],
        box: BoundingBox,
        relative_seconds: float,
        chunk_id: str,
        claimed: set[str],
    ) -> str:
        best = _matching_track(
            tracks,
            box,
            relative_seconds,
            claimed,
            self.config,
        )
        if best is not None:
            best.last_box = box
            best.last_seen = relative_seconds
            return best.track_id
        track_id = stable_id("trk", chunk_id, len(tracks))
        tracks.append(_Track(track_id=track_id, last_box=box, last_seen=relative_seconds))
        return track_id


class YoloV8ObjectDetector:
    """Turns a full frame stream into labeled, track-linked YOLO candidates."""

    def __init__(self, config: DetectorConfig | None = None, *, model: Any | None = None):
        self.config = config or DetectorConfig()
        self._model = model

    def detect(self, frames: Iterable[SampledFrame], *, chunk_id: str) -> list[Detection]:
        if not self.config.yolo_enabled:
            return []
        try:
            model = self._model or _load_yolo_model(self.config.yolo_model)
            detections: list[Detection] = []
            tracks: list[_ObjectTrack] = []
            for frame_batch in batched(frames, self.config.yolo_batch_size):
                results = model.predict(
                    source=[frame.image for frame in frame_batch],
                    stream=True,
                    verbose=False,
                    conf=self.config.yolo_confidence,
                    iou=self.config.yolo_iou,
                    imgsz=self.config.yolo_image_size,
                    batch=self.config.yolo_batch_size,
                    max_det=self.config.yolo_max_detections,
                    classes=list(self.config.yolo_classes),
                    agnostic_nms=True,
                    device=_resolve_yolo_device(self.config.yolo_device),
                )
                detections.extend(self._normalize_results(results, frame_batch, chunk_id, tracks))
            return detections
        except ObjectDetectorError:
            raise
        except Exception as error:
            raise ObjectDetectorError(
                f"{self.config.yolo_model} object detection failed: {error}"
            ) from error

    def _normalize_results(
        self,
        results: Iterable[Any],
        frames: tuple[SampledFrame, ...],
        chunk_id: str,
        tracks: list[_ObjectTrack],
    ) -> list[Detection]:
        detections: list[Detection] = []
        result_count = 0
        for result, frame in zip(results, frames, strict=False):
            result_count += 1
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            coordinates = _as_numpy(boxes.xyxy)
            scores = _as_numpy(boxes.conf).reshape(-1)
            classes = _as_numpy(boxes.cls).astype(int).reshape(-1)
            names = getattr(result, "names", {})
            height, width = frame.image.shape[:2]
            claimed: set[str] = set()
            for coordinates_row, score, class_id in zip(
                coordinates,
                scores,
                classes,
                strict=True,
            ):
                box = _normalized_box(coordinates_row, width=width, height=height)
                if box is None:
                    continue
                track_id = self._assign_track(
                    tracks,
                    box,
                    frame.relative_seconds,
                    chunk_id,
                    claimed,
                    int(class_id),
                )
                claimed.add(track_id)
                detections.append(
                    Detection(
                        detection_id=stable_id(
                            "yolo-det",
                            chunk_id,
                            round(frame.relative_seconds, 3),
                            int(class_id),
                            round(box.x, 5),
                            round(box.y, 5),
                            round(box.width, 5),
                            round(box.height, 5),
                        ),
                        chunk_id=chunk_id,
                        track_id=track_id,
                        relative_seconds=round(frame.relative_seconds, 3),
                        box=box,
                        score=round(float(score), 4),
                        source=DetectionSource.YOLOV8_OBJECT,
                        label=_class_label(names, int(class_id)),
                        class_id=int(class_id),
                        model=Path(self.config.yolo_model).name,
                    )
                )
        if result_count != len(frames):
            raise ObjectDetectorError(
                f"{self.config.yolo_model} returned {result_count} results for "
                f"{len(frames)} sampled frames"
            )
        return detections

    def _assign_track(
        self,
        tracks: list[_ObjectTrack],
        box: BoundingBox,
        relative_seconds: float,
        chunk_id: str,
        claimed: set[str],
        class_id: int,
    ) -> str:
        best = _matching_track(
            tracks,
            box,
            relative_seconds,
            claimed,
            self.config,
            expected_class_id=class_id,
        )
        if best is not None:
            best.last_box = box
            best.last_seen = relative_seconds
            return best.track_id
        track_id = stable_id("yolo-trk", chunk_id, len(tracks))
        tracks.append(
            _ObjectTrack(
                track_id=track_id,
                last_box=box,
                last_seen=relative_seconds,
                class_id=class_id,
            )
        )
        return track_id


@dataclass
class _Track:
    track_id: str
    last_box: BoundingBox
    last_seen: float


@dataclass
class _ObjectTrack:
    track_id: str
    last_box: BoundingBox
    last_seen: float
    class_id: int


def _matching_track(
    tracks: Iterable[_Track | _ObjectTrack],
    box: BoundingBox,
    relative_seconds: float,
    claimed: set[str],
    config: DetectorConfig,
    *,
    expected_class_id: int | None = None,
) -> _Track | _ObjectTrack | None:
    """Link a fast body without merging distinct same-frame animals.

    IoU remains authoritative. The center-and-size fallback only covers bodies
    that move beyond their previous box between samples. Bounded distance and
    area-ratio gates prevent a nearby small bird from joining a much larger
    animal, while ``claimed`` preserves one detection per track and frame.
    """
    best_overlap: _Track | _ObjectTrack | None = None
    best_iou = config.iou_match_threshold
    nearest: _Track | _ObjectTrack | None = None
    nearest_distance = config.center_match_max_distance
    for track in tracks:
        if track.track_id in claimed:
            continue
        if expected_class_id is not None and (
            not isinstance(track, _ObjectTrack) or track.class_id != expected_class_id
        ):
            continue
        elapsed = relative_seconds - track.last_seen
        if elapsed < 0 or elapsed > config.track_gap_tolerance_seconds:
            continue
        overlap = _iou(track.last_box, box)
        if overlap >= best_iou:
            best_overlap = track
            best_iou = overlap
            continue
        if elapsed > config.center_match_max_gap_seconds:
            continue
        area_ratio = max(track.last_box.area, box.area) / min(track.last_box.area, box.area)
        if area_ratio > config.center_match_max_area_ratio:
            continue
        distance = _center_distance(track.last_box, box)
        if distance <= nearest_distance:
            nearest = track
            nearest_distance = distance
    return best_overlap or nearest


@lru_cache(maxsize=4)
def _load_yolo_model(model_name: str) -> Any:
    try:
        from ultralytics import YOLO

        return YOLO(model_name)
    except Exception as error:
        raise ObjectDetectorError(f"could not load YOLO model {model_name}: {error}") from error


@lru_cache(maxsize=8)
def _resolve_yolo_device(configured: str) -> str:
    if configured.lower() != "auto":
        return configured
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except (AttributeError, ImportError):
        pass
    return "cpu"


def probe_video(path: str | Path) -> VideoProbe:
    """Measure real container facts with ffprobe.

    Duration is read from the container rather than derived from a frame count,
    because the project's own fixtures include files whose first packet starts
    hours into the timeline.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"video not found: {source}")
    completed = run_media_tool(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate:format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=0",
            str(source),
        ],
        timeout=60,
    )
    if completed.returncode != 0:
        raise ValueError(f"ffprobe could not read {source.name}")
    fields: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        key, _, value = line.partition("=")
        if value:
            fields[key.strip()] = value.strip()
    try:
        width = int(fields["width"])
        height = int(fields["height"])
        duration = float(fields["duration"])
    except (KeyError, ValueError) as error:
        raise ValueError(f"ffprobe returned no usable video stream for {source.name}") from error
    numerator, _, denominator = fields.get("avg_frame_rate", "0/0").partition("/")
    try:
        frame_rate = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        frame_rate = 0.0
    if frame_rate <= 0:
        frame_rate = 25.0
    if duration <= 0:
        raise ValueError(f"{source.name} reports a non-positive duration")
    return VideoProbe(
        duration_seconds=duration,
        width=width,
        height=height,
        frame_rate=frame_rate,
    )


def sample_video_frames(
    path: str | Path,
    *,
    sample_fps: float = 5.0,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
    max_frames: int | None = None,
    max_edge: int = 480,
) -> Iterator[SampledFrame]:
    """Yield evenly spaced frames from a real file.

    Frames are downscaled before detection: motion regions are normalized, so
    the boxes are resolution independent, and a smaller frame keeps a long
    overnight segment inside a predictable time budget.
    """
    source = Path(path)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {source.name}")
    try:
        native_fps = capture.get(cv2.CAP_PROP_FPS)
        if not native_fps or native_fps <= 0 or native_fps > 240:
            native_fps = 25.0
        sample_interval = 1.0 / min(sample_fps, native_fps)
        first_index = max(0, int(round(start_seconds * native_fps)))
        last_index_exclusive = (
            None
            if duration_seconds is None
            else first_index + max(1, ceil(duration_seconds * native_fps))
        )
        if first_index:
            capture.set(cv2.CAP_PROP_POS_FRAMES, first_index)
        index = first_index
        emitted = 0
        next_sample_seconds = 0.0
        while max_frames is None or emitted < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            if last_index_exclusive is not None and index >= last_index_exclusive:
                break
            relative_seconds = (index - first_index) / native_fps
            if relative_seconds + 1e-9 >= next_sample_seconds:
                yield SampledFrame(
                    relative_seconds=relative_seconds,
                    image=_downscale(frame, max_edge),
                )
                emitted += 1
                next_sample_seconds += sample_interval
                while next_sample_seconds <= relative_seconds + 1e-9:
                    next_sample_seconds += sample_interval
            index += 1
    finally:
        capture.release()


def detections_for_chunk(
    path: str | Path,
    *,
    chunk_id: str,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
    config: DetectorConfig | None = None,
) -> list[Detection]:
    """Read the entire requested segment and return spatial review candidates."""
    resolved = config or DetectorConfig()
    detections: list[Detection] = []
    if resolved.yolo_enabled:
        detections.extend(
            YoloV8ObjectDetector(resolved).detect(
                sample_video_frames(
                    path,
                    sample_fps=resolved.sample_fps,
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    max_edge=resolved.frame_max_edge,
                ),
                chunk_id=chunk_id,
            )
        )
    if resolved.motion_enabled:
        detections.extend(
            MotionRegionDetector(resolved).detect(
                sample_video_frames(
                    path,
                    sample_fps=resolved.sample_fps,
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    max_edge=resolved.frame_max_edge,
                ),
                chunk_id=chunk_id,
            )
        )
    return sorted(
        detections,
        key=lambda detection: (
            detection.relative_seconds,
            detection.source.value,
            detection.box.x,
        ),
    )


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _normalized_box(
    coordinates: Any,
    *,
    width: int,
    height: int,
) -> BoundingBox | None:
    x0, y0, x1, y1 = (float(value) for value in coordinates[:4])
    x0 = min(max(x0 / width, 0.0), 1.0)
    y0 = min(max(y0 / height, 0.0), 1.0)
    x1 = min(max(x1 / width, 0.0), 1.0)
    y1 = min(max(y1 / height, 0.0), 1.0)
    if x1 <= x0 or y1 <= y0:
        return None
    origin_x = _clamp(x0)
    origin_y = _clamp(y0)
    return BoundingBox(
        x=origin_x,
        y=origin_y,
        width=_clamp_span(x1 - x0, origin_x),
        height=_clamp_span(y1 - y0, origin_y),
    )


def _expand_motion_box(box: BoundingBox, config: DetectorConfig) -> BoundingBox:
    """Add bounded visual context around a changed-pixel contour.

    Background subtraction often finds only the part of an animal that moved.
    Optional padding and minimum extents let a reviewed reprocessing pass show
    the whole small animal while preserving the measured region at its center.
    """
    target_width = min(
        1.0,
        max(box.width * (1 + 2 * config.motion_box_padding_ratio), config.motion_min_box_width),
    )
    target_height = min(
        1.0,
        max(
            box.height * (1 + 2 * config.motion_box_padding_ratio),
            config.motion_min_box_height,
        ),
    )
    center_x = box.x + box.width / 2
    center_y = box.y + box.height / 2
    origin_x = min(max(center_x - target_width / 2, 0.0), 1.0 - target_width)
    origin_y = min(max(center_y - target_height / 2, 0.0), 1.0 - target_height)
    return BoundingBox(
        x=_clamp(origin_x),
        y=_clamp(origin_y),
        width=_clamp_span(target_width, _clamp(origin_x)),
        height=_clamp_span(target_height, _clamp(origin_y)),
    )


def _class_label(
    names: Mapping[int, str] | list[str] | tuple[str, ...],
    class_id: int,
) -> str:
    if isinstance(names, Mapping):
        return str(names.get(class_id, f"class {class_id}"))
    if 0 <= class_id < len(names):
        return str(names[class_id])
    return f"class {class_id}"


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _downscale(frame: np.ndarray, max_edge: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(height, width)
    if longest <= max_edge:
        return frame
    scale = max_edge / longest
    return cv2.resize(
        frame,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _clamp(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), 5)


def _clamp_span(span: float, origin: float) -> float:
    # Keep the box inside the frame after the origin has been rounded.
    return round(min(max(span, 1e-4), max(1.0 - origin, 1e-4)), 5)


def _iou(left: BoundingBox, right: BoundingBox) -> float:
    x0 = max(left.x, right.x)
    y0 = max(left.y, right.y)
    x1 = min(left.x + left.width, right.x + right.width)
    y1 = min(left.y + left.height, right.y + right.height)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    overlap = (x1 - x0) * (y1 - y0)
    union = left.area + right.area - overlap
    return overlap / union if union > 0 else 0.0


def _center_distance(left: BoundingBox, right: BoundingBox) -> float:
    left_x = left.x + left.width / 2
    left_y = left.y + left.height / 2
    right_x = right.x + right.width / 2
    right_y = right.y + right.height / 2
    return float(np.hypot(left_x - right_x, left_y - right_y))
