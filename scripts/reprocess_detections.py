from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from zoovision.detection import (
    DetectorConfig,
    MotionRegionDetector,
    SampledFrame,
    YoloV8ObjectDetector,
    probe_video,
    sample_video_frames,
)
from zoovision.domain import BoundingBox, Detection, DetectionSource
from zoovision.ids import stable_id
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore

MOTION_SOURCE = "motion_region"
REVIEWED_BACKGROUND_SHA256 = "ea009878017cae1cc3599b529017b5fad2346125bf070d7b680ef10ff52b36e7"
REVIEWED_BACKGROUND_MODEL = "content-bound-background-v1"
REVIEWED_BACKGROUND_SAMPLES = 61
REVIEWED_BACKGROUND_THRESHOLD = 36
REVIEWED_BACKGROUND_MIN_AREA_RATIO = 0.0015
# Content-bound regions where feeder birds can appear. They exclude foliage,
# the planter, and most high-contrast frame edges that change with sunlight.
REVIEWED_BACKGROUND_ROIS = (
    (0.08, 0.08, 0.92, 0.58),
    (0.22, 0.42, 0.90, 0.92),
)


@dataclass(frozen=True)
class SourceWork:
    source_path: str
    media_path: Path
    duration_seconds: float
    content_sha256: str
    chunks: tuple[dict, ...]


@dataclass(frozen=True)
class DetectionStats:
    total: int
    yolo: int
    motion: int
    other: int
    positive_box_seconds: int
    positive_box_seconds_coverage_percent: float
    first_box_seconds: float | None
    last_box_seconds: float | None
    largest_box_gap_seconds: float


@dataclass
class _ReferenceTrack:
    track_id: str
    box: BoundingBox
    last_seen: float


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed <= 30:
        raise argparse.ArgumentTypeError("must be greater than 0 and at most 30")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def _ratio(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return parsed


def _confidence(value: str) -> float:
    parsed = float(value)
    if not 0.01 <= parsed <= 1:
        raise argparse.ArgumentTypeError("must be between 0.01 and 1")
    return parsed


def _image_size(value: str) -> int:
    parsed = int(value)
    if not 320 <= parsed <= 1280 or parsed % 32:
        raise argparse.ArgumentTypeError("must be a multiple of 32 between 320 and 1280")
    return parsed


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild motion-region boxes for stored recordings without rerunning "
            "providers or changing observations, events, or ingest jobs."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--source",
        action="append",
        help=("Stored source path or unique basename. Repeat to select multiple recordings."),
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help="Rebuild motion regions for every stored video source.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="SQLite database path. Defaults to ZOOVISION_STORAGE_ROOT/zoovision.db.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        help="Raw-media root. Defaults to ZOOVISION_STORAGE_ROOT/raw.",
    )
    parser.add_argument(
        "--sample-fps",
        type=_positive_float,
        default=5.0,
        help="Spatial sampling rate in frames per second. Default: 5.",
    )
    parser.add_argument(
        "--max-edge",
        type=_positive_int,
        default=960,
        help="Maximum decoded frame edge used for motion analysis. Default: 960.",
    )
    parser.add_argument(
        "--min-area-ratio",
        type=_ratio,
        default=0.0002,
        help="Minimum moving-region area as a fraction of the frame. Default: 0.0002.",
    )
    parser.add_argument(
        "--min-fill-ratio",
        type=_ratio,
        default=0.12,
        help="Minimum contour fill ratio. Default: 0.12.",
    )
    parser.add_argument(
        "--max-regions",
        type=_positive_int,
        default=8,
        help="Maximum motion regions retained per sampled frame. Default: 8.",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=5,
        choices=range(0, 61),
        metavar="0-60",
        help="Background-model warmup frames per chunk. Default: 5 (one second).",
    )
    parser.add_argument(
        "--staircase-background-pass",
        action="store_true",
        help=(
            "Add the content-hash-bound median-background bird pass for the "
            "reviewed staircase recording."
        ),
    )
    parser.add_argument(
        "--rebuild-yolo",
        action="store_true",
        help=(
            "Also rebuild yolov8_object rows using the configured model; motion and "
            "other sources remain intact during the YOLO replacement."
        ),
    )
    parser.add_argument(
        "--yolo-confidence",
        type=_confidence,
        help="YOLO confidence threshold. Defaults to ZOOVISION_YOLO_CONFIDENCE.",
    )
    parser.add_argument(
        "--yolo-image-size",
        type=_image_size,
        default=1280,
        help="YOLO inference size. Default: 1280.",
    )
    return parser.parse_args(argv)


def _select_sources(
    available: Iterable[str],
    requested: Sequence[str] | None,
    *,
    select_all: bool,
) -> list[str]:
    choices = sorted(set(available))
    if select_all:
        if not choices:
            raise ValueError("the database contains no video sources")
        return choices

    selected: list[str] = []
    for raw in requested or ():
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"invalid source selector: {raw}")
        if raw in choices:
            match = raw
        else:
            matches = [source for source in choices if Path(source).name == raw]
            if not matches:
                raise ValueError(f"source is not stored in the database: {raw}")
            if len(matches) > 1:
                raise ValueError(f"source basename is ambiguous; use a stored path: {raw}")
            match = matches[0]
        if match not in selected:
            selected.append(match)
    if not selected:
        raise ValueError("select at least one source")
    return selected


def _resolve_media_path(raw_root: Path, source_path: str) -> Path:
    root = raw_root.resolve()
    candidate = (root / source_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"stored source escapes the raw-media root: {source_path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"stored media is missing: {candidate}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _chunk_duration(chunk: dict) -> float:
    start = datetime.fromisoformat(chunk["start_ts"])
    end = datetime.fromisoformat(chunk["end_ts"])
    return (end - start).total_seconds()


def _prepare_source(
    source_path: str,
    chunks: Sequence[dict],
    raw_root: Path,
) -> SourceWork:
    media_path = _resolve_media_path(raw_root, source_path)
    content_sha256 = _sha256(media_path)
    stored_hashes = {str(chunk["content_sha256"]) for chunk in chunks}
    if stored_hashes != {content_sha256}:
        raise ValueError(
            f"stored SHA-256 does not match {source_path}; refusing detection replacement"
        )

    probe = probe_video(media_path)
    ordered = sorted(chunks, key=lambda item: (item["source_offset_seconds"], item["chunk_id"]))
    previous_end = 0.0
    for index, chunk in enumerate(ordered):
        offset = float(chunk["source_offset_seconds"])
        duration = _chunk_duration(chunk)
        if offset < 0 or duration <= 0:
            raise ValueError(f"invalid chunk interval for {chunk['chunk_id']}")
        if index and offset < previous_end - 0.5:
            raise ValueError(f"overlapping stored chunks for {source_path}")
        if offset > probe.duration_seconds + 0.5:
            raise ValueError(f"chunk begins beyond the media duration: {chunk['chunk_id']}")
        if offset + duration > probe.duration_seconds + 1.0:
            raise ValueError(f"chunk extends beyond the media duration: {chunk['chunk_id']}")
        previous_end = offset + duration
    return SourceWork(
        source_path=source_path,
        media_path=media_path,
        duration_seconds=probe.duration_seconds,
        content_sha256=content_sha256,
        chunks=tuple(ordered),
    )


def _backup_database(database: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S.%f%z")
    backup = backup_root / f"{database.name}.before-motion-reprocess-{stamp}"
    source_uri = f"file:{database.resolve()}?mode=ro"
    try:
        with (
            sqlite3.connect(source_uri, uri=True) as source,
            sqlite3.connect(backup) as destination,
        ):
            source.backup(destination)
            integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"backup integrity check failed: {integrity}")
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    return backup


def _source_detections(store: SQLiteStore, chunks: Sequence[dict]) -> list[dict]:
    rows: list[dict] = []
    for chunk in chunks:
        rows.extend(store.detections_for_chunk(chunk["chunk_id"]))
    return rows


def _protected_detection_snapshot(
    rows: Iterable[dict],
    *,
    replaced_sources: set[str],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            json.dumps(row, sort_keys=True, separators=(",", ":"))
            for row in rows
            if row["source"] not in replaced_sources
        )
    )


def _detection_stats(
    rows: Sequence[dict],
    chunks: Sequence[dict],
    duration_seconds: float,
) -> DetectionStats:
    offsets = {chunk["chunk_id"]: float(chunk["source_offset_seconds"]) for chunk in chunks}
    points = sorted(
        max(0.0, min(duration_seconds, offsets[row["chunk_id"]] + row["relative_seconds"]))
        for row in rows
    )
    duration_bins = max(1, math.ceil(duration_seconds))
    positive_seconds = {min(duration_bins - 1, max(0, math.floor(point))) for point in points}
    if points:
        gaps = [points[0], duration_seconds - points[-1]]
        gaps.extend(right - left for left, right in zip(points, points[1:], strict=False))
        first = round(points[0], 3)
        last = round(points[-1], 3)
        largest_gap = round(max(gaps), 3)
    else:
        first = None
        last = None
        largest_gap = round(duration_seconds, 3)
    yolo = sum(row["source"] == "yolov8_object" for row in rows)
    motion = sum(row["source"] == MOTION_SOURCE for row in rows)
    return DetectionStats(
        total=len(rows),
        yolo=yolo,
        motion=motion,
        other=len(rows) - yolo - motion,
        positive_box_seconds=len(positive_seconds),
        positive_box_seconds_coverage_percent=round(
            len(positive_seconds) / duration_bins * 100,
            2,
        ),
        first_box_seconds=first,
        last_box_seconds=last,
        largest_box_gap_seconds=largest_gap,
    )


def _median_lab_reference(
    work: SourceWork,
    *,
    max_edge: int,
    sample_count: int = REVIEWED_BACKGROUND_SAMPLES,
) -> np.ndarray:
    sample_fps = sample_count / work.duration_seconds
    lab_frames = [
        cv2.cvtColor(frame.image, cv2.COLOR_BGR2LAB)
        for frame in sample_video_frames(
            work.media_path,
            sample_fps=sample_fps,
            duration_seconds=work.duration_seconds,
            max_frames=sample_count,
            max_edge=max_edge,
        )
    ]
    if len(lab_frames) < max(15, sample_count // 2):
        raise ValueError(f"too few reference frames decoded for {work.source_path}")
    stack = np.stack(lab_frames)
    return np.median(stack, axis=0, overwrite_input=True).astype(np.uint8)


def _activity_mask(height: int, width: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    for left, top, right, bottom in REVIEWED_BACKGROUND_ROIS:
        x0 = max(0, min(width, int(round(left * width))))
        y0 = max(0, min(height, int(round(top * height))))
        x1 = max(x0, min(width, int(round(right * width))))
        y1 = max(y0, min(height, int(round(bottom * height))))
        mask[y0:y1, x0:x1] = 255
    return mask


def _box_iou(left: BoundingBox, right: BoundingBox) -> float:
    x0 = max(left.x, right.x)
    y0 = max(left.y, right.y)
    x1 = min(left.x + left.width, right.x + right.width)
    y1 = min(left.y + left.height, right.y + right.height)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    union = left.area + right.area - intersection
    return intersection / union if union > 0 else 0.0


def _box_center_distance(left: BoundingBox, right: BoundingBox) -> float:
    left_x = left.x + left.width / 2
    left_y = left.y + left.height / 2
    right_x = right.x + right.width / 2
    right_y = right.y + right.height / 2
    return float(np.hypot(left_x - right_x, left_y - right_y))


def _reference_regions(
    frame: SampledFrame,
    reference_lab: np.ndarray,
    *,
    max_regions: int,
) -> list[tuple[BoundingBox, float]]:
    frame_lab = cv2.cvtColor(frame.image, cv2.COLOR_BGR2LAB)
    if frame_lab.shape != reference_lab.shape:
        raise ValueError("reference and sampled frame dimensions differ")
    difference = cv2.absdiff(frame_lab, reference_lab)
    strength = np.max(difference, axis=2).astype(np.uint8)
    _, binary = cv2.threshold(
        strength,
        REVIEWED_BACKGROUND_THRESHOLD,
        255,
        cv2.THRESH_BINARY,
    )
    height, width = binary.shape
    binary = cv2.bitwise_and(binary, _activity_mask(height, width))
    opening = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closing = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, opening)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, closing)

    frame_area = float(height * width)
    regions: list[tuple[BoundingBox, float, float]] = []
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_width <= 0 or box_height <= 0:
            continue
        area_ratio = box_width * box_height / frame_area
        if not REVIEWED_BACKGROUND_MIN_AREA_RATIO <= area_ratio <= 0.04:
            continue
        aspect_ratio = box_width / box_height
        if not 0.25 <= aspect_ratio <= 4.0:
            continue
        contour_area = float(cv2.contourArea(contour))
        fill_ratio = contour_area / float(box_width * box_height)
        if fill_ratio < 0.12:
            continue
        box = BoundingBox(
            x=round(x / width, 5),
            y=round(y / height, 5),
            width=round(box_width / width, 5),
            height=round(box_height / height, 5),
        )
        foreground = strength[y : y + box_height, x : x + box_width]
        active = foreground[foreground > REVIEWED_BACKGROUND_THRESHOLD]
        contrast = float(np.mean(active)) if active.size else 0.0
        score = round(min(0.99, max(0.2, 0.45 * fill_ratio + contrast / 100)), 4)
        regions.append((box, score, contour_area))

    regions.sort(key=lambda item: (-item[2], item[0].x, item[0].y))
    kept: list[tuple[BoundingBox, float]] = []
    for box, score, _ in regions:
        if any(_box_iou(box, prior) >= 0.35 for prior, _ in kept):
            continue
        kept.append((box, score))
        if len(kept) >= max_regions:
            break
    return sorted(kept, key=lambda item: (item[0].x, item[0].y))


def _reference_track_id(
    tracks: list[_ReferenceTrack],
    box: BoundingBox,
    relative_seconds: float,
    chunk_id: str,
    claimed: set[str],
    config: DetectorConfig,
) -> str:
    best_overlap: _ReferenceTrack | None = None
    best_iou = 0.12
    nearest: _ReferenceTrack | None = None
    nearest_distance = config.center_match_max_distance
    for track in tracks:
        if track.track_id in claimed:
            continue
        elapsed = relative_seconds - track.last_seen
        if elapsed < 0 or elapsed > config.track_gap_tolerance_seconds:
            continue
        overlap = _box_iou(track.box, box)
        if overlap >= best_iou:
            best_overlap = track
            best_iou = overlap
            continue
        if elapsed > config.center_match_max_gap_seconds:
            continue
        area_ratio = max(track.box.area, box.area) / min(track.box.area, box.area)
        if area_ratio > config.center_match_max_area_ratio:
            continue
        distance = _box_center_distance(track.box, box)
        if distance <= nearest_distance:
            nearest = track
            nearest_distance = distance
    best = best_overlap or nearest
    if best is not None:
        best.box = box
        best.last_seen = relative_seconds
        return best.track_id
    track_id = stable_id("content-bound-background-track", chunk_id, len(tracks))
    tracks.append(_ReferenceTrack(track_id=track_id, box=box, last_seen=relative_seconds))
    return track_id


def _reviewed_background_detections(
    work: SourceWork,
    chunk: dict,
    reference_lab: np.ndarray,
    config: DetectorConfig,
    *,
    duration_seconds: float,
    max_edge: int,
) -> list[Detection]:
    chunk_id = chunk["chunk_id"]
    tracks: list[_ReferenceTrack] = []
    detections: list[Detection] = []
    for frame in sample_video_frames(
        work.media_path,
        sample_fps=config.sample_fps,
        start_seconds=float(chunk["source_offset_seconds"]),
        duration_seconds=duration_seconds,
        max_edge=max_edge,
    ):
        claimed: set[str] = set()
        for box, score in _reference_regions(
            frame,
            reference_lab,
            max_regions=config.max_regions_per_frame,
        ):
            track_id = _reference_track_id(
                tracks,
                box,
                frame.relative_seconds,
                chunk_id,
                claimed,
                config,
            )
            claimed.add(track_id)
            detections.append(
                Detection(
                    detection_id=stable_id(
                        "content-bound-background-detection",
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
                    label="bird",
                    class_id=None,
                    model=REVIEWED_BACKGROUND_MODEL,
                )
            )
    return detections


def _combine_motion_detections(
    mog: Sequence[Detection],
    content_bound: Sequence[Detection],
    *,
    max_regions: int,
) -> list[Detection]:
    by_time: dict[float, list[Detection]] = {}
    for detection in content_bound:
        by_time.setdefault(detection.relative_seconds, []).append(detection)
    mog_by_time: dict[float, list[Detection]] = {}
    for detection in mog:
        mog_by_time.setdefault(detection.relative_seconds, []).append(detection)

    combined: list[Detection] = []
    for relative_seconds in sorted(set(by_time) | set(mog_by_time)):
        preferred = sorted(
            by_time.get(relative_seconds, []),
            key=lambda item: (-item.score, item.box.x),
        )
        remaining = sorted(
            mog_by_time.get(relative_seconds, []),
            key=lambda item: (-item.score, item.box.x),
        )
        frame_detections = preferred[:max_regions]
        for candidate in remaining:
            if len(frame_detections) >= max_regions:
                break
            if any(_box_iou(candidate.box, kept.box) >= 0.3 for kept in frame_detections):
                continue
            frame_detections.append(candidate)
        combined.extend(sorted(frame_detections, key=lambda item: item.box.x))
    return combined


def _reprocess_source(
    store: SQLiteStore,
    work: SourceWork,
    config: DetectorConfig,
    *,
    max_edge: int,
    staircase_background_pass: bool,
    yolo_config: DetectorConfig | None,
) -> tuple[DetectionStats, DetectionStats]:
    before_rows = _source_detections(store, work.chunks)
    replaced_sources = {MOTION_SOURCE}
    if yolo_config is not None:
        replaced_sources.add(DetectionSource.YOLOV8_OBJECT.value)
    protected_before = _protected_detection_snapshot(
        before_rows,
        replaced_sources=replaced_sources,
    )
    before = _detection_stats(before_rows, work.chunks, work.duration_seconds)

    detector = MotionRegionDetector(config)
    yolo_detector = YoloV8ObjectDetector(yolo_config) if yolo_config is not None else None
    reference_lab = (
        _median_lab_reference(work, max_edge=max_edge) if staircase_background_pass else None
    )
    for index, chunk in enumerate(work.chunks, start=1):
        offset = float(chunk["source_offset_seconds"])
        duration = min(_chunk_duration(chunk), work.duration_seconds - offset)
        mog_detections = detector.detect(
            sample_video_frames(
                work.media_path,
                sample_fps=config.sample_fps,
                start_seconds=offset,
                duration_seconds=duration,
                max_edge=max_edge,
            ),
            chunk_id=chunk["chunk_id"],
        )
        content_bound_detections = (
            _reviewed_background_detections(
                work,
                chunk,
                reference_lab,
                config,
                duration_seconds=duration,
                max_edge=max_edge,
            )
            if reference_lab is not None
            else []
        )
        detections = _combine_motion_detections(
            mog_detections,
            content_bound_detections,
            max_regions=config.max_regions_per_frame,
        )
        yolo_detections = (
            yolo_detector.detect(
                sample_video_frames(
                    work.media_path,
                    sample_fps=yolo_config.sample_fps,
                    start_seconds=offset,
                    duration_seconds=duration,
                    max_edge=yolo_config.yolo_image_size,
                ),
                chunk_id=chunk["chunk_id"],
            )
            if yolo_detector is not None and yolo_config is not None
            else []
        )
        if yolo_config is not None:
            store.replace_chunk_spatial_detections(
                chunk["chunk_id"],
                [*detections, *yolo_detections],
            )
        else:
            store.replace_chunk_motion_detections(chunk["chunk_id"], detections)
        print(
            json.dumps(
                {
                    "source": work.source_path,
                    "status": "processing",
                    "chunk": index,
                    "chunks": len(work.chunks),
                    "motion_detections": len(detections),
                    "content_bound_bird_detections": len(content_bound_detections),
                    "yolo_detections": len(yolo_detections),
                }
            ),
            flush=True,
        )

    after_rows = _source_detections(store, work.chunks)
    if (
        _protected_detection_snapshot(
            after_rows,
            replaced_sources=replaced_sources,
        )
        != protected_before
    ):
        raise RuntimeError(f"protected detections changed for {work.source_path}")
    after = _detection_stats(after_rows, work.chunks, work.duration_seconds)
    return before, after


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _arguments(argv)
    settings = get_settings()
    database = (arguments.database or settings.database_path).resolve()
    raw_root = (arguments.raw_root or settings.storage_root / "raw").resolve()
    if not database.is_file():
        raise SystemExit(f"database is missing: {database}")

    store = SQLiteStore(database)
    all_chunks = store.dump_table("video_chunks")
    selected = _select_sources(
        (chunk["source_path"] for chunk in all_chunks),
        arguments.source,
        select_all=arguments.all,
    )
    work_items = [
        _prepare_source(
            source_path,
            [chunk for chunk in all_chunks if chunk["source_path"] == source_path],
            raw_root,
        )
        for source_path in selected
    ]
    if arguments.staircase_background_pass and not any(
        work.content_sha256 == REVIEWED_BACKGROUND_SHA256 for work in work_items
    ):
        raise ValueError(
            "--staircase-background-pass requires the reviewed staircase content SHA-256"
        )
    if arguments.rebuild_yolo and not settings.yolo_enabled:
        raise ValueError("--rebuild-yolo requires ZOOVISION_YOLO_ENABLED=true")

    backup = _backup_database(database, raw_root / "backups")
    print(json.dumps({"database_backup": str(backup)}), flush=True)

    config = DetectorConfig(
        sample_fps=arguments.sample_fps,
        yolo_enabled=False,
        motion_enabled=True,
        min_area_ratio=arguments.min_area_ratio,
        min_fill_ratio=arguments.min_fill_ratio,
        max_regions_per_frame=arguments.max_regions,
        warmup_frames=arguments.warmup_frames,
    )
    yolo_config = (
        DetectorConfig(
            sample_fps=arguments.sample_fps,
            yolo_enabled=True,
            yolo_model=settings.yolo_model,
            yolo_device=settings.yolo_device,
            yolo_confidence=(
                arguments.yolo_confidence
                if arguments.yolo_confidence is not None
                else settings.yolo_confidence
            ),
            yolo_image_size=arguments.yolo_image_size,
            yolo_batch_size=settings.yolo_batch_size,
            motion_enabled=False,
        )
        if arguments.rebuild_yolo
        else None
    )
    for work in work_items:
        use_staircase_background = bool(
            arguments.staircase_background_pass
            and work.content_sha256 == REVIEWED_BACKGROUND_SHA256
        )
        before, after = _reprocess_source(
            store,
            work,
            config,
            max_edge=arguments.max_edge,
            staircase_background_pass=use_staircase_background,
            yolo_config=yolo_config,
        )
        print(
            json.dumps(
                {
                    "source": work.source_path,
                    "status": "complete",
                    "duration_seconds": round(work.duration_seconds, 3),
                    "chunks": len(work.chunks),
                    "content_sha256": work.content_sha256,
                    "config": {
                        "sample_fps": config.sample_fps,
                        "max_edge": arguments.max_edge,
                        "min_area_ratio": config.min_area_ratio,
                        "min_fill_ratio": config.min_fill_ratio,
                        "max_regions_per_frame": config.max_regions_per_frame,
                        "warmup_frames": config.warmup_frames,
                        "content_bound_background": use_staircase_background,
                        "content_bound_background_model": (
                            REVIEWED_BACKGROUND_MODEL if use_staircase_background else None
                        ),
                        "rebuild_yolo": yolo_config is not None,
                        "yolo_model": (
                            Path(yolo_config.yolo_model).name if yolo_config is not None else None
                        ),
                        "yolo_confidence": (
                            yolo_config.yolo_confidence if yolo_config is not None else None
                        ),
                        "yolo_image_size": (
                            yolo_config.yolo_image_size if yolo_config is not None else None
                        ),
                    },
                    "before": asdict(before),
                    "after": asdict(after),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
