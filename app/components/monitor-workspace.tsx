"use client";

import "./monitor-target.css";

import {
  Activity,
  AlertTriangle,
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  Footprints,
  Maximize2,
  Moon,
  Pause,
  Play,
  ShieldCheck,
  SkipBack,
  SkipForward,
  Sparkles,
  Route,
  ScanLine,
  Video,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import {
  CSSProperties,
  ChangeEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  api,
  type VideoDetection,
  type VideoSource,
  type VideoTrack,
} from "../lib/api";

const PLAYBACK_SPEEDS = [0.5, 1, 2] as const;
const COVERAGE_BINS = 72;
const DETECTION_HOLD_SECONDS = 2.25;
const DETECTION_FUTURE_TOLERANCE_SECONDS = 0.35;
const DETECTION_OVERLAP_IOU = 0.16;
const DETECTION_OVERLAP_CONTAINMENT = 0.42;
const MAX_VISIBLE_DETECTIONS_PER_SOURCE = 10;
const POSTER_BY_SOURCE_PATH: Record<string, string> = {
  "uploads/backyard-squirrel-staircase.mp4":
    "/camera-posters/source-backyard-squirrel-staircase.jpg",
  "uploads/backyard-squirrels-and-birds.mp4":
    "/camera-posters/source-backyard-squirrels-and-birds.jpg",
  "uploads/badger-provider-probe-30s.mp4":
    "/camera-posters/source-badger-provider-probe-30s.jpg",
  "uploads/enc03_mountain_gorilla_15m.mp4":
    "/camera-posters/source-enc03_mountain_gorilla_15m.jpg",
  "uploads/enc03_trailcam_night_15m.mp4":
    "/camera-posters/source-enc03_trailcam_night_15m.jpg",
  "uploads/enc05_condor_nest_15m.mp4":
    "/camera-posters/source-enc05_condor_nest_15m.jpg",
  "uploads/enc05_elephant_15m.mp4":
    "/camera-posters/source-enc05_elephant_15m.jpg",
  "uploads/enc07_badger_night_30m.mp4":
    "/camera-posters/source-enc07_badger_night_30m.jpg",
  "uploads/enc07_lion_night_30m.mp4":
    "/camera-posters/source-enc07_lion_night_30m.jpg",
  "uploads/lion-provider-probe-30s.mp4":
    "/camera-posters/source-lion-provider-probe-30s.jpg",
};

const RULE_LABELS: Record<string, string> = {
  R001_FIGHTING: "Fighting observed",
  R002_ESCAPE_ATTEMPT: "Escape attempt observed",
  R003_VOMITING: "Vomiting observed",
  R004_PACING_20M_NO_WATER_6H:
    "Sustained pacing with no recent water visit",
  R005_PACING_10M: "Sustained pacing",
  R006_INACTIVITY_2SD: "Activity well below the daytime baseline",
  R007_BASELINE_DELTA_2_5: "Large change from the daytime baseline",
  R008_WATER_BOWL_TIPPED: "Water bowl appears tipped",
};

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function formatBehavior(value?: string | null) {
  if (!value) return "No notable event";
  return value
    .split("_")
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function formatRule(value?: string | null) {
  if (!value) return "No welfare rule fired";
  if (RULE_LABELS[value]) return RULE_LABELS[value];
  return value
    .replace(/^rule[_-]?/i, "")
    .split(/[_-]+/)
    .filter(Boolean)
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function confidenceSummary(value?: number | null) {
  if (value == null) return "Confidence was not supplied; keeper review required";
  const percent = Math.round(value * 100);
  if (percent >= 85) return `Strong supporting evidence (${percent}%)`;
  if (percent >= 65) return `Moderate supporting evidence (${percent}%)`;
  return `Limited supporting evidence (${percent}%); verify the clip`;
}

function formatDuration(seconds: number | null | undefined) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "--";
  const safeSeconds = Math.max(0, Math.round(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainder = safeSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(
      remainder,
    ).padStart(2, "0")}`;
  }
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function finiteMetric(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function readableEvidenceDetail(value: string) {
  return value.replace(
    /^(?:demo|sample|fixture|synthetic)\s+(?:annotation|scenario|evidence)\s*:\s*/i,
    "",
  );
}

function readableObservationSource(
  provider: string,
  evidenceKind: string,
) {
  if (
    provider.toLowerCase() === "fixture" ||
    evidenceKind.toLowerCase() === "synthetic_scenario"
  ) {
    return "Evidence annotation · Reviewed evidence";
  }
  return `${provider} · ${formatBehavior(evidenceKind)}`;
}

function analysisLabel(source: VideoSource) {
  if (source.analysis_status === "complete") return "Full analysis";
  if (source.analysis_status === "analyzing") {
    const progress = segmentProgressLabel(source);
    return progress ? `Analyzing · ${progress}` : "Analyzing";
  }
  const gapCount = finiteMetric(source.data_gap_count);
  if (source.analysis_status === "incomplete") {
    return gapCount && gapCount > 0
      ? `Incomplete · ${gapCount} gap${gapCount === 1 ? "" : "s"}`
      : "Incomplete analysis";
  }
  return "Analysis available";
}

function segmentProgressLabel(source: VideoSource) {
  const completed = finiteMetric(source.completed_segments);
  const total = finiteMetric(source.total_segments);
  return completed !== null && total !== null && total > 0
    ? `${Math.max(0, completed)}/${total} segments`
    : null;
}

function analysisProgressDetail(source: VideoSource) {
  const analyzed = finiteMetric(source.analyzed_duration_seconds);
  const probed = finiteMetric(source.probe_duration_seconds);
  const coverage = finiteMetric(source.coverage_percent);
  if (analyzed !== null && probed !== null && probed > 0 && coverage !== null) {
    const safeCoverage = Math.max(0, Math.min(100, coverage));
    return `${formatDuration(analyzed)} analyzed of ${formatDuration(probed)} · ${safeCoverage}% semantic coverage`;
  }
  const segments = segmentProgressLabel(source);
  return segments ? `${segments} processed` : null;
}

function sourceDurationLabel(source: VideoSource) {
  const analyzed = finiteMetric(source.analyzed_duration_seconds);
  const probed = finiteMetric(source.probe_duration_seconds);
  return analyzed !== null && probed !== null && probed > 0
    ? `${formatDuration(analyzed)} / ${formatDuration(probed)}`
    : `${source.chunk_count} evidence chunk${source.chunk_count === 1 ? "" : "s"}`;
}

function sourceIsFullyAnalyzed(source: VideoSource) {
  return typeof source.is_fully_analyzed === "boolean"
    ? source.is_fully_analyzed
    : source.analysis_status === "complete";
}

function emptyEventMessage(source: VideoSource) {
  if (sourceIsFullyAnalyzed(source)) {
    return "Review observations below. This recording has no deterministic welfare event.";
  }
  return source.analysis_status
    ? "Rule evaluation is still incomplete. Events finalize after full source analysis."
    : "Review observations below. No deterministic welfare event is available.";
}

function formatWallClock(start: string, offsetSeconds: number) {
  const value = new Date(new Date(start).getTime() + offsetSeconds * 1000);
  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function maximumTrackSeconds(track: VideoTrack) {
  return Math.max(
    1,
    ...track.events.map((item) => item.end_seconds),
    ...track.observations.map((item) => item.end_seconds),
    ...track.chunks.map((chunk) => {
      const value = Number(chunk.source_offset_seconds ?? 0);
      const start = new Date(String(chunk.start_ts ?? 0)).getTime();
      const end = new Date(String(chunk.end_ts ?? 0)).getTime();
      const duration = Number.isFinite(start) && Number.isFinite(end)
        ? Math.max(0, (end - start) / 1000)
        : 0;
      return value + duration;
    }),
  );
}

function authoritativeSourceDuration(
  probeDurationSeconds: number | undefined,
  track: VideoTrack,
) {
  const probed = finiteMetric(probeDurationSeconds);
  return probed !== null && probed > 0 ? probed : maximumTrackSeconds(track);
}

function boundedTimelineSpan(
  startSeconds: number,
  endSeconds: number,
  durationSeconds: number,
  minimumWidth: number,
) {
  const boundedStart = clamp(startSeconds, 0, durationSeconds);
  const boundedEnd = clamp(Math.max(endSeconds, boundedStart), boundedStart, durationSeconds);
  const width = Math.min(
    100,
    Math.max(minimumWidth, ((boundedEnd - boundedStart) / durationSeconds) * 100),
  );
  return {
    left: clamp((boundedStart / durationSeconds) * 100, 0, 100 - width),
    width,
  };
}

function initialEvidenceSeconds(track: VideoTrack) {
  const event = track.events[0];
  if (event) {
    return event.start_seconds + Math.min(5, Math.max(0, event.end_seconds - event.start_seconds) / 2);
  }
  const observation = track.observations[0];
  if (observation) {
    return (
      observation.start_seconds +
      Math.min(5, Math.max(0, observation.end_seconds - observation.start_seconds) / 2)
    );
  }
  return 0;
}

function nearestByStart<T extends { start_seconds: number }>(
  items: T[],
  currentSeconds: number,
) {
  if (items.length === 0) return null;
  return items.reduce((nearest, item) =>
    Math.abs(item.start_seconds - currentSeconds) <
    Math.abs(nearest.start_seconds - currentSeconds)
      ? item
      : nearest,
  );
}

function observationAtTime(
  observations: VideoTrack["observations"],
  currentSeconds: number,
) {
  const active = observations
    .filter(
      (observation) =>
        currentSeconds >= observation.start_seconds &&
        currentSeconds <= observation.end_seconds,
    )
    .sort((left, right) => {
      const leftLive = left.provider === "twelvelabs" ? 1 : 0;
      const rightLive = right.provider === "twelvelabs" ? 1 : 0;
      if (leftLive !== rightLive) return rightLive - leftLive;
      return (
        left.end_seconds -
        left.start_seconds -
        (right.end_seconds - right.start_seconds)
      );
    });
  return active[0] ?? nearestByStart(observations, currentSeconds);
}

function detectionsAtTime(
  detections: VideoTrack["detections"],
  currentSeconds: number,
) {
  function candidatesFor(source: string) {
    return detections.filter(
      (item) =>
        item.source === source &&
        item.video_seconds <=
          currentSeconds + DETECTION_FUTURE_TOLERANCE_SECONDS &&
        currentSeconds - item.video_seconds <= DETECTION_HOLD_SECONDS,
    );
  }

  function latestFrame(source: string) {
    const candidates = candidatesFor(source);
    if (candidates.length === 0) return [];
    const frameSeconds = candidates.reduce(
      (nearest, item) =>
        Math.abs(item.video_seconds - currentSeconds) <
        Math.abs(nearest - currentSeconds)
          ? item.video_seconds
          : nearest,
      candidates[0].video_seconds,
    );
    return candidates.filter(
      (item) => Math.abs(item.video_seconds - frameSeconds) < 0.001,
    );
  }

  function latestTracks(source: string) {
    const candidates = candidatesFor(source);
    if (candidates.length === 0) return [];

    // Animals do not move on the same sampled frame. Hold the freshest box for
    // each track, then collapse track churn that still occupies one region.
    const byTrack = new Map<string, VideoDetection>();
    for (const candidate of candidates) {
      const previous = byTrack.get(candidate.track_id);
      const candidateDistance = Math.abs(
        candidate.video_seconds - currentSeconds,
      );
      const previousDistance = previous
        ? Math.abs(previous.video_seconds - currentSeconds)
        : Number.POSITIVE_INFINITY;
      if (
        !previous ||
        candidateDistance < previousDistance ||
        (candidateDistance === previousDistance &&
          candidate.video_seconds > previous.video_seconds)
      ) {
        byTrack.set(candidate.track_id, candidate);
      }
    }

    const kept: VideoDetection[] = [];
    for (const candidate of [...byTrack.values()].sort(
      (left, right) =>
        right.video_seconds - left.video_seconds || right.score - left.score,
    )) {
      if (
        kept.some((existing) =>
          detectionBoxesOverlap(candidate.box, existing.box),
        )
      ) {
        continue;
      }
      kept.push(candidate);
      if (kept.length >= MAX_VISIBLE_DETECTIONS_PER_SOURCE) break;
    }
    return kept;
  }

  const yolo = latestFrame("yolov8_object");
  const motion = latestTracks("motion_region");
  const unmatchedMotion = motion.filter(
    (motionDetection) =>
      !yolo.some((objectDetection) =>
        detectionBoxesOverlap(motionDetection.box, objectDetection.box),
      ),
  );
  return [...yolo, ...unmatchedMotion].sort((left, right) => {
    if (left.source !== right.source) {
      return left.source === "yolov8_object" ? -1 : 1;
    }
    return left.box.x - right.box.x || left.box.y - right.box.y;
  });
}

function detectionBoxesOverlap(
  left: VideoDetection["box"],
  right: VideoDetection["box"],
) {
  const x0 = Math.max(left.x, right.x);
  const y0 = Math.max(left.y, right.y);
  const x1 = Math.min(left.x + left.width, right.x + right.width);
  const y1 = Math.min(left.y + left.height, right.y + right.height);
  if (x1 <= x0 || y1 <= y0) return false;
  const intersection = (x1 - x0) * (y1 - y0);
  const leftArea = left.width * left.height;
  const rightArea = right.width * right.height;
  const union = leftArea + rightArea - intersection;
  const iou = union > 0 ? intersection / union : 0;
  const containment = intersection / Math.max(0.000001, Math.min(leftArea, rightArea));
  return (
    iou >= DETECTION_OVERLAP_IOU ||
    containment >= DETECTION_OVERLAP_CONTAINMENT
  );
}

function detectionBoxContains(
  outer: VideoDetection["box"],
  inner: VideoDetection["box"],
) {
  const x0 = Math.max(outer.x, inner.x);
  const y0 = Math.max(outer.y, inner.y);
  const x1 = Math.min(outer.x + outer.width, inner.x + inner.width);
  const y1 = Math.min(outer.y + outer.height, inner.y + inner.height);
  if (x1 <= x0 || y1 <= y0) return false;
  const intersection = (x1 - x0) * (y1 - y0);
  const outerArea = outer.width * outer.height;
  const innerArea = inner.width * inner.height;
  return intersection / innerArea >= 0.78 && outerArea >= innerArea * 1.5;
}

function activeObservationText(
  observations: VideoTrack["observations"],
  currentSeconds: number,
) {
  return observations
    .filter(
      (observation) =>
        currentSeconds >= observation.start_seconds &&
        currentSeconds <= observation.end_seconds,
    )
    .map(
      (observation) =>
        `${observation.activity_label ?? ""} ${observation.evidence}`,
    )
    .join(" ")
    .toLowerCase();
}

function curateVisibleDetections(
  detections: VideoDetection[],
  sourcePath: string,
  observationText: string,
) {
  const sourceName = sourcePath.split("/").at(-1) ?? sourcePath;
  if (sourceName === "backyard-squirrel-staircase.mp4") {
    return detections.sort((left, right) => {
      if (left.source !== right.source) {
        return left.source === "yolov8_object" ? -1 : 1;
      }
      return left.box.x - right.box.x || left.box.y - right.box.y;
    });
  }

  if (sourceName === "backyard-squirrels-and-birds.mp4") {
    const labeled = detections.map((detection) => ({
      detection,
      label: canonicalDetectionLabel(detection, sourcePath, observationText),
    }));
    const squirrelDetections = labeled.filter(
      ({ label }) => label === "Squirrel",
    );
    return labeled
      .filter(
        ({ detection, label }) =>
          label !== "Bird" ||
          !squirrelDetections.some(({ detection: squirrel }) =>
            detectionBoxContains(squirrel.box, detection.box),
          ),
      )
      .map(({ detection }) => detection);
  }

  if (sourceName === "enc05_condor_nest_15m.mp4") {
    return detections.filter(
      (detection) =>
        detection.source !== "yolov8_object" ||
        (detection.box.width * detection.box.height >= 0.002 &&
          detection.box.x + detection.box.width / 2 < 0.9),
    );
  }

  return detections;
}

const SOURCE_CANONICAL_LABELS: Record<string, string> = {
  "backyard-squirrel-staircase.mp4": "Bird",
  "badger-provider-probe-30s.mp4": "Badger",
  "enc03_mountain_gorilla_15m.mp4": "Mountain gorilla",
  "enc03_trailcam_night_15m.mp4": "Wildlife",
  "enc05_condor_nest_15m.mp4": "Andean condor",
  "enc05_elephant_15m.mp4": "Elephant",
  "enc07_badger_night_30m.mp4": "Badger",
  "enc07_lion_night_30m.mp4": "African lion",
  "lion-provider-probe-30s.mp4": "African lion",
};

function canonicalDetectionLabel(
  detection: VideoDetection,
  sourcePath: string,
  observationText: string,
) {
  const explicitLabel = [
    detection.display_label,
    detection.canonical_label,
    detection.animal_label,
    detection.animal_name,
  ].find((value) => typeof value === "string" && value.trim().length > 0);
  if (explicitLabel) return formatBehavior(explicitLabel.trim());

  const sourceName = sourcePath.split("/").at(-1) ?? sourcePath;
  const sourceLabel = SOURCE_CANONICAL_LABELS[sourceName];
  if (sourceLabel) return sourceLabel;

  if (sourceName === "backyard-squirrels-and-birds.mp4") {
    const rawLabel = detection.label?.trim().toLowerCase() ?? "";
    const area = detection.box.width * detection.box.height;
    const subjectText = observationText.replace(/\bbird feeder\b/g, "");
    const birdVisible =
      /\b(?:bird|birds|sparrow|sparrows)\b/.test(subjectText) &&
      !/\bno (?:visible )?(?:bird|birds|sparrow|sparrows)\b/.test(subjectText);
    const squirrelVisible =
      /\b(?:squirrel|squirrels)\b/.test(subjectText) &&
      !/\bno (?:visible )?(?:squirrel|squirrels)\b/.test(subjectText);

    if (birdVisible && !squirrelVisible) return "Bird";
    if (squirrelVisible && !birdVisible) return "Squirrel";
    if (birdVisible && squirrelVisible) {
      if (rawLabel === "bird" && area <= 0.04) return "Bird";
      if (rawLabel && rawLabel !== "bird") return "Squirrel";
      return area > 0.04 ? "Squirrel" : "Bird";
    }
    if (rawLabel === "bird" && area <= 0.04) return "Bird";
    if (rawLabel) return "Squirrel";
    return area > 0.04 ? "Squirrel" : "Bird";
  }

  return "Animal";
}

type LabeledDetection = VideoDetection & {
  displayLabel: string;
  provenanceTitle: string;
};

function labelVisibleDetections(
  detections: VideoDetection[],
  sourcePath: string,
  observationText: string,
): LabeledDetection[] {
  const baseLabels = detections.map((detection) =>
    canonicalDetectionLabel(detection, sourcePath, observationText),
  );
  const grouped = new Map<string, number[]>();
  baseLabels.forEach((label, index) => {
    grouped.set(label, [...(grouped.get(label) ?? []), index]);
  });

  const numberedLabels = [...baseLabels];
  for (const [label, indices] of grouped) {
    if (indices.length < 2) continue;
    indices
      .sort(
        (left, right) =>
          detections[left].box.x - detections[right].box.x ||
          detections[left].box.y - detections[right].box.y,
      )
      .forEach((detectionIndex, index) => {
        numberedLabels[detectionIndex] = `${label} ${index + 1}`;
      });
  }

  return detections.map((detection, index) => {
    const rawLabel = detection.label
      ? `Raw model label: ${formatBehavior(detection.label)}`
      : "No raw model class label";
    const source = detection.annotation_source
      ? formatBehavior(detection.annotation_source)
      : detection.source === "yolov8_object"
        ? "Object localization"
        : "Measured movement";
    const model = detection.model ? `Model: ${detection.model}` : null;
    const instance = detection.instance_id
      ? `Track instance: ${detection.instance_id}`
      : `Track: ${detection.track_id}`;
    return {
      ...detection,
      displayLabel: numberedLabels[index],
      provenanceTitle: [
        numberedLabels[index],
        source,
        rawLabel,
        model,
        instance,
        `${Math.round(detection.score * 100)}% localization score`,
      ]
        .filter(Boolean)
        .join(" · "),
    };
  });
}

function detectionTimelineBins(
  detections: VideoTrack["detections"],
  durationSeconds: number,
) {
  const bins = Array.from({ length: COVERAGE_BINS }, () => 0);
  for (const detection of detections) {
    const index = clamp(
      Math.floor((detection.video_seconds / durationSeconds) * COVERAGE_BINS),
      0,
      COVERAGE_BINS - 1,
    );
    bins[index] += 1;
  }
  return bins;
}

function containedVideoBounds(
  stage: HTMLDivElement,
  video: HTMLVideoElement,
) {
  const stageWidth = stage.clientWidth;
  const stageHeight = stage.clientHeight;
  if (
    stageWidth <= 0 ||
    stageHeight <= 0 ||
    video.videoWidth <= 0 ||
    video.videoHeight <= 0
  ) {
    return { left: 0, top: 0, width: stageWidth, height: stageHeight };
  }
  const mediaRatio = video.videoWidth / video.videoHeight;
  const stageRatio = stageWidth / stageHeight;
  if (mediaRatio > stageRatio) {
    const height = stageWidth / mediaRatio;
    return {
      left: 0,
      top: (stageHeight - height) / 2,
      width: stageWidth,
      height,
    };
  }
  const width = stageHeight * mediaRatio;
  return {
    left: (stageWidth - width) / 2,
    top: 0,
    width,
    height: stageHeight,
  };
}

function emptyVideoTrack(source: VideoSource): VideoTrack {
  return {
    source_path: source.source_path,
    media_url: source.media_url,
    chunks: [],
    detections: [],
    events: [],
    observations: [],
    rule_checks: [],
  };
}

function EvidenceTimeline({
  durationSeconds,
  loading,
  onSelectEvent,
  onSelectObservation,
  onSeek,
  progress,
  selectedEventId,
  track,
}: {
  durationSeconds: number;
  loading: boolean;
  onSelectEvent: (id: string, seconds: number) => void;
  onSelectObservation: (id: string, seconds: number) => void;
  onSeek: (seconds: number) => void;
  progress: number;
  selectedEventId?: string;
  track: VideoTrack;
}) {
  const spatialDetections = track.detections;
  const spatialDetectionBins = useMemo(
    () => detectionTimelineBins(spatialDetections, durationSeconds),
    [durationSeconds, spatialDetections],
  );
  const ruleChecks = track.rule_checks ?? [];
  const spatialDetectionPeak = Math.max(1, ...spatialDetectionBins);
  const timeTicks = Array.from({ length: 5 }, (_, index) =>
    (durationSeconds / 4) * index,
  );

  function handleRange(event: ChangeEvent<HTMLInputElement>) {
    onSeek((Number(event.target.value) / 1000) * durationSeconds);
  }

  return (
    <section
      className="evidence-timeline"
      aria-label="Recorded evidence timeline"
      aria-busy={loading}
      style={{ "--timeline-progress": progress / 100 } as CSSProperties}
    >
      <header className="timeline-heading">
        <div>
          <span>Recorded evidence</span>
          <strong>Shift timeline</strong>
        </div>
        <p>
          <span className="legend-swatch animal-box" />
          Animal boxes
          <span className="legend-swatch observation" />
          Observation
          <span className="legend-swatch check" />
          Rule check
          <span className="legend-swatch event" />
          Fired events
        </p>
      </header>

      <div className="timeline-ruler">
        <span />
        {timeTicks.map((seconds) => (
          <time
            key={seconds}
            style={{ left: `${(seconds / durationSeconds) * 100}%` }}
          >
            {formatDuration(seconds)}
          </time>
        ))}
      </div>

      <div
        className="timeline-row"
        aria-label={`${spatialDetections.length} spatial animal box samples`}
      >
        <span className="timeline-label">
          <ScanLine size={14} />
          <span className="timeline-label-long">Animal boxes</span>
          <span className="timeline-label-short">Boxes</span>
        </span>
        <div className="timeline-track detection-heatmap animal-box-heatmap">
          {spatialDetections.length === 0 ? (
            <span className="empty-track">
              {loading ? "Loading animal boxes" : "No animal boxes"}
            </span>
          ) : (
            spatialDetectionBins.map((count, index) => (
              <i
                aria-hidden="true"
                key={index}
                style={{
                  opacity:
                    count === 0
                      ? 0.08
                      : 0.24 + (count / spatialDetectionPeak) * 0.76,
                }}
              />
            ))
          )}
          {spatialDetections.length > 0 && (
            <small className="timeline-track-count">
              {spatialDetections.length} samples
            </small>
          )}
        </div>
      </div>

      <div className="timeline-row interactive-timeline-row">
        <span className="timeline-label">
          <Eye size={14} />
          <span className="timeline-label-long">Observations</span>
          <span className="timeline-label-short">Observ.</span>
        </span>
        <div className="timeline-track">
          {track.observations.length === 0 ? (
            <span className="empty-track">
              {loading ? "Loading observations" : "No structured observations"}
            </span>
          ) : (
            track.observations.map((observation) => {
              const span = boundedTimelineSpan(
                observation.start_seconds,
                observation.end_seconds,
                durationSeconds,
                1.2,
              );
              return (
                <button
                  type="button"
                  className="timeline-span observation-span"
                  key={observation.observation_id}
                  onPointerDown={(event) => {
                    if (event.button === 0) {
                      onSelectObservation(
                        observation.observation_id,
                        observation.start_seconds,
                      );
                    }
                  }}
                  onClick={() =>
                    onSelectObservation(
                      observation.observation_id,
                      observation.start_seconds,
                    )
                  }
                  style={{
                    left: `${span.left}%`,
                    width: `${span.width}%`,
                  }}
                  aria-label={`Seek to ${formatBehavior(observation.behavior)} observation at ${formatDuration(
                    observation.start_seconds,
                  )}`}
                  title={formatBehavior(observation.behavior)}
                >
                  <span>{formatBehavior(observation.behavior)}</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="timeline-row interactive-timeline-row">
        <span className="timeline-label">
          <ShieldCheck size={14} />
          <span className="timeline-label-long">Rule checks</span>
          <span className="timeline-label-short">Checks</span>
        </span>
        <div className="timeline-track">
          {ruleChecks.length === 0 ? (
            <span className="empty-track">
              {loading ? "Loading rule checks" : "No recorded rule checks"}
            </span>
          ) : (
            ruleChecks.map((check) => {
              const fired =
                check.event_id != null &&
                check.severity.toUpperCase() !== "NONE" &&
                check.rule_fired !== "NO_RULE_FIRED";
              const span = boundedTimelineSpan(
                check.start_seconds,
                check.end_seconds,
                durationSeconds,
                1.1,
              );
              const selectCheck = () => {
                if (fired && check.event_id) {
                  onSelectEvent(check.event_id, check.start_seconds);
                } else {
                  onSelectObservation(check.observation_id, check.start_seconds);
                }
              };
              const title = fired
                ? `${check.severity} · ${formatRule(check.rule_fired)}`
                : `${formatBehavior(check.behavior)} reviewed · no deterministic rule fired`;
              return (
                <button
                  type="button"
                  className="timeline-span rule-check-span"
                  data-fired={fired}
                  data-selected={
                    fired && selectedEventId === check.event_id
                  }
                  key={`rule-check-${check.observation_id}`}
                  onPointerDown={(event) => {
                    if (event.button === 0) selectCheck();
                  }}
                  onClick={selectCheck}
                  style={{
                    left: `${span.left}%`,
                    width: `${span.width}%`,
                  }}
                  aria-label={`Seek to ${title.toLowerCase()} at ${formatDuration(
                    check.start_seconds,
                  )}`}
                  title={title}
                >
                  <span>{fired ? formatRule(check.rule_fired) : "Checked"}</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="timeline-row interactive-timeline-row">
        <span className="timeline-label">
          <AlertTriangle size={14} />
          <span className="timeline-label-long">Fired events</span>
          <span className="timeline-label-short">Events</span>
        </span>
        <div className="timeline-track">
          {track.events.length === 0 ? (
            <span className="empty-track">
              {loading ? "Loading fired events" : "No deterministic rule events"}
            </span>
          ) : (
            track.events.map((event) => {
              const span = boundedTimelineSpan(
                event.start_seconds,
                event.end_seconds,
                durationSeconds,
                2,
              );
              return (
                <button
                  type="button"
                  className={`timeline-span event-span severity-${event.severity.toLowerCase()}`}
                  data-selected={selectedEventId === event.event_id}
                  key={event.event_id}
                  onPointerDown={(pointerEvent) => {
                    if (pointerEvent.button === 0) {
                      onSelectEvent(event.event_id, event.start_seconds);
                    }
                  }}
                  onClick={() =>
                    onSelectEvent(event.event_id, event.start_seconds)
                  }
                  style={{
                    left: `${span.left}%`,
                    width: `${span.width}%`,
                  }}
                  aria-label={`Seek to ${event.severity} ${formatBehavior(
                    event.behavior,
                  )} event at ${formatDuration(event.start_seconds)}`}
                  title={`${event.severity} · ${formatBehavior(event.behavior)} · ${event.rule_fired}`}
                >
                  <span>{formatBehavior(event.behavior)}</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <label className="timeline-range">
        <span className="sr-only">Recorded shift position</span>
        <input
          type="range"
          min={0}
          max={1000}
          value={Math.round(progress * 10)}
          onChange={handleRange}
          aria-valuetext={formatDuration((progress / 100) * durationSeconds)}
        />
      </label>
      <span className="timeline-playhead" aria-hidden="true" />
    </section>
  );
}

export function MonitorWorkspace() {
  const reduceMotion = useReducedMotion();
  const [cameraIndex, setCameraIndex] = useState(0);
  const [durationSeconds, setDurationSeconds] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState<(typeof PLAYBACK_SPEEDS)[number]>(1);
  const [progress, setProgress] = useState(0);
  const [track, setTrack] = useState<VideoTrack | null>(null);
  const [videos, setVideos] = useState<VideoSource[]>([]);
  const [videoBounds, setVideoBounds] = useState({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
  });
  const [selectedEvidence, setSelectedEvidence] = useState<{
    kind: "event" | "observation";
    id: string;
  } | null>(null);
  const inspectorRef = useRef<HTMLElement>(null);
  const pendingSeekRef = useRef<{
    sourcePath: string;
    seconds: number;
  } | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoStageRef = useRef<HTMLDivElement>(null);
  const selectedCamera = videos[cameraIndex];
  const selectedSourcePath = selectedCamera?.source_path;
  const selectedAnimalId = selectedCamera?.animal_ids?.[0] ?? null;
  const selectedAnimalName = selectedCamera?.animal_names?.[0] ?? null;
  const selectedEnclosureId = selectedCamera?.enclosure_id;
  const selectedCameraId = selectedCamera?.camera_id;
  const selectedCompletedSegments = selectedCamera?.completed_segments;
  const selectedAnalysisStatus = selectedCamera?.analysis_status;
  const selectedProbeDuration = selectedCamera?.probe_duration_seconds;
  const currentSeconds = (progress / 100) * durationSeconds;
  const trackLoading = Boolean(
    selectedCamera &&
      track &&
      track.source_path === selectedCamera.source_path &&
      track.chunks.length === 0 &&
      selectedCamera.chunk_count > 0,
  );
  const usesTwelveLabs = Boolean(
    track?.observations.some((observation) => observation.provider === "twelvelabs"),
  );
  const usesFrameSampledAnalysis = Boolean(
    track?.observations.some(
      (observation) => observation.evidence_kind === "frame_sampled_provider",
    ),
  );
  const providerDisplayName =
    trackLoading
      ? "Loading track"
      : usesTwelveLabs && usesFrameSampledAnalysis
      ? "Pegasus + OpenAI"
      : usesTwelveLabs
        ? "Pegasus 1.5"
        : usesFrameSampledAnalysis
          ? "OpenAI vision"
          : "Unavailable";
  const playheadEvent = useMemo(() => {
    if (!track) return null;
    return track.events.find(
      (event) =>
        currentSeconds >= event.start_seconds &&
        currentSeconds <= event.end_seconds,
    );
  }, [currentSeconds, track]);
  const playheadObservation = useMemo(() => {
    if (!track) return null;
    return observationAtTime(track.observations, currentSeconds);
  }, [currentSeconds, track]);
  const visibleDetections = useMemo(() => {
    if (!track) return [];
    const observationText = activeObservationText(
      track.observations,
      currentSeconds,
    );
    return labelVisibleDetections(
      curateVisibleDetections(
        detectionsAtTime(track.detections, currentSeconds),
        track.source_path,
        observationText,
      ),
      track.source_path,
      observationText,
    );
  }, [currentSeconds, track]);
  const selectedEvent = useMemo(() => {
    if (!track) return null;
    if (selectedEvidence?.kind === "event") {
      return (
        track.events.find((event) => event.event_id === selectedEvidence.id) ??
        playheadEvent
      );
    }
    return playheadEvent;
  }, [playheadEvent, selectedEvidence, track]);
  const selectedObservation = useMemo(() => {
    if (!track) return null;
    if (selectedEvidence?.kind === "observation") {
      return (
        track.observations.find(
          (observation) => observation.observation_id === selectedEvidence.id,
        ) ?? playheadObservation
      );
    }
    return playheadObservation;
  }, [playheadObservation, selectedEvidence, track]);
  const selectedObservationIsFrameSampled =
    selectedObservation?.evidence_kind === "frame_sampled_provider";
  useEffect(() => {
    let cancelled = false;
    let hasLoaded = false;
    let refreshTimer: number | null = null;

    const scheduleRefresh = () => {
      if (cancelled) return;
      refreshTimer = window.setTimeout(() => void loadVideos(), 30_000);
    };

    const loadVideos = async () => {
      if (cancelled) return;
      if (document.hidden) {
        scheduleRefresh();
        return;
      }

      try {
        const { videos: sources } = await api.videos();
        if (cancelled) return;
        hasLoaded = true;
        setVideos(sources);
        setTrack((current) => {
          if (
            current &&
            sources.some((source) => source.source_path === current.source_path)
          ) {
            return current;
          }
          return sources[0] ? emptyVideoTrack(sources[0]) : null;
        });
        setLoadError(
          sources.length === 0
            ? "No analyzed video sources are available."
            : null,
        );
      } catch (caught: unknown) {
        if (!cancelled && !hasLoaded) {
          setLoadError(
            caught instanceof Error ? caught.message : "Unable to load videos.",
          );
        }
      } finally {
        scheduleRefresh();
      }
    };

    void loadVideos();
    return () => {
      cancelled = true;
      if (refreshTimer !== null) window.clearTimeout(refreshTimer);
    };
  }, []);

  useEffect(() => {
    function openMoment(event: Event) {
      const detail = (event as CustomEvent).detail as
        | { sourcePath?: string; seconds?: number }
        | undefined;
      if (
        !detail?.sourcePath ||
        typeof detail.seconds !== "number" ||
        !Number.isFinite(detail.seconds)
      ) {
        return;
      }
      const targetIndex = videos.findIndex(
        (video) => video.source_path === detail.sourcePath,
      );
      if (targetIndex < 0) return;
      sessionStorage.removeItem("zoovision:pending-moment");
      if (targetIndex === cameraIndex) {
        const video = videoRef.current;
        const duration =
          video && Number.isFinite(video.duration) && video.duration > 0
            ? video.duration
            : durationSeconds;
        const next = clamp(detail.seconds, 0, duration);
        if (video) video.currentTime = next;
        setProgress((next / duration) * 100);
        return;
      }
      pendingSeekRef.current = {
        sourcePath: detail.sourcePath,
        seconds: detail.seconds,
      };
      setTrack(emptyVideoTrack(videos[targetIndex]));
      setCameraIndex(targetIndex);
    }

    window.addEventListener("zoovision:seek-moment", openMoment);
    const stored = sessionStorage.getItem("zoovision:pending-moment");
    if (stored) {
      try {
        openMoment(
          new CustomEvent("zoovision:seek-moment", {
            detail: JSON.parse(stored),
          }),
        );
      } catch {
        sessionStorage.removeItem("zoovision:pending-moment");
      }
    }
    return () => window.removeEventListener("zoovision:seek-moment", openMoment);
  }, [cameraIndex, durationSeconds, videos]);

  useEffect(() => {
    if (!selectedSourcePath || !selectedEnclosureId || !selectedCameraId) return;
    let cancelled = false;
    const controller = new AbortController();
    const assistantContext = {
      animalId: selectedAnimalId,
      animalName: selectedAnimalName,
      enclosureId: selectedEnclosureId,
      cameraId: selectedCameraId,
      sourcePath: selectedSourcePath,
    };
    sessionStorage.setItem(
      "zoovision:assistant-context",
      JSON.stringify(assistantContext),
    );
    window.dispatchEvent(
      new CustomEvent("zoovision:assistant-context", {
        detail: assistantContext,
      }),
    );
    api
      .videoTrack(selectedSourcePath, controller.signal)
      .then((payload) => {
        if (cancelled) return;
        setTrack(payload);
        setSelectedEvidence(null);
        setDurationSeconds(authoritativeSourceDuration(selectedProbeDuration, payload));
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        if (caught instanceof Error && caught.name === "AbortError") return;
        setLoadError(
          caught instanceof Error
            ? caught.message
            : "Unable to load the video evidence track.",
        );
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [
    selectedAnalysisStatus,
    selectedAnimalId,
    selectedAnimalName,
    selectedCameraId,
    selectedCompletedSegments,
    selectedEnclosureId,
    selectedProbeDuration,
    selectedSourcePath,
  ]);

  useEffect(() => {
    const stage = videoStageRef.current;
    const video = videoRef.current;
    if (!stage || !video) return;
    const update = () => setVideoBounds(containedVideoBounds(stage, video));
    const observer = new ResizeObserver(update);
    observer.observe(stage);
    document.addEventListener("fullscreenchange", update);
    update();
    return () => {
      observer.disconnect();
      document.removeEventListener("fullscreenchange", update);
    };
  }, [selectedCamera]);

  function seekToSeconds(seconds: number) {
    const video = videoRef.current;
    const duration =
      video && Number.isFinite(video.duration) && video.duration > 0
        ? video.duration
        : durationSeconds;
    const next = clamp(seconds, 0, duration);
    if (video) video.currentTime = next;
    setProgress((next / duration) * 100);
  }

  function seekBy(seconds: number) {
    seekToSeconds(currentSeconds + seconds);
  }

  async function togglePlayback() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      try {
        await video.play();
      } catch {
        setMediaError("Playback could not start. Try selecting the camera again.");
      }
    } else {
      video.pause();
    }
  }

  function updatePlaybackRate(
    value: (typeof PLAYBACK_SPEEDS)[number],
  ) {
    setPlaybackRate(value);
    if (videoRef.current) videoRef.current.playbackRate = value;
  }

  async function openFullscreen() {
    try {
      await videoStageRef.current?.requestFullscreen();
    } catch {
      setMediaError("Fullscreen is not available in this browser window.");
    }
  }

  function jumpToEvidence(direction: -1 | 1) {
    if (!track) return;
    const moments = [
      ...track.events.map((event) => event.start_seconds),
      ...track.observations.map((observation) => observation.start_seconds),
    ]
      .filter((value, index, items) => items.indexOf(value) === index)
      .sort((a, b) => a - b);
    if (moments.length === 0) return;
    const target =
      direction === 1
        ? moments.find((value) => value > currentSeconds + 0.5) ?? moments[0]
        : [...moments].reverse().find((value) => value < currentSeconds - 0.5) ??
          moments[moments.length - 1];
    seekToSeconds(target);
  }

  function selectCamera(index: number) {
    const nextCamera = videos[index];
    if (!nextCamera) return;
    videoRef.current?.pause();
    setLoadError(null);
    setMediaError(null);
    setPlaying(false);
    setProgress(0);
    const placeholder = emptyVideoTrack(nextCamera);
    setTrack(placeholder);
    setDurationSeconds(
      authoritativeSourceDuration(nextCamera.probe_duration_seconds, placeholder),
    );
    setSelectedEvidence(null);
    setCameraIndex(index);
  }

  function selectEvidence(
    kind: "event" | "observation",
    id: string,
    seconds: number,
  ) {
    setSelectedEvidence({ kind, id });
    seekToSeconds(seconds);
    window.requestAnimationFrame(() => {
      inspectorRef.current?.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
        block: "nearest",
      });
      inspectorRef.current?.focus({ preventScroll: true });
    });
  }

  function changeCamera(direction: -1 | 1) {
    if (videos.length === 0) return;
    selectCamera((cameraIndex + direction + videos.length) % videos.length);
  }

  if (loadError) {
    return (
      <div className="monitor-state" role="alert">
        <AlertTriangle size={22} />
        <strong>Evidence workspace unavailable</strong>
        <p>{loadError}</p>
      </div>
    );
  }

  if (!selectedCamera || !track) {
    return (
      <div className="monitor-state" role="status">
        <span className="monitor-spinner" />
        <strong>Loading recorded evidence</strong>
        <p>Connecting the video, localization track, and rule provenance.</p>
      </div>
    );
  }

  const poster = POSTER_BY_SOURCE_PATH[selectedCamera.source_path];
  const isFixtureEvidence =
    selectedObservation?.provider === "fixture" ||
    selectedObservation?.evidence_kind === "synthetic_scenario";
  const currentActivity =
    selectedObservation?.activity_label ??
    (selectedObservation?.behavior && selectedObservation.behavior !== "other"
      ? formatBehavior(selectedObservation.behavior)
      : "No activity annotation");
  const currentEventActive =
    selectedEvent != null &&
    currentSeconds >= selectedEvent.start_seconds &&
    currentSeconds <= selectedEvent.end_seconds;
  const selectedSourceFullyAnalyzed = sourceIsFullyAnalyzed(selectedCamera);
  const selectedAnalysisProgress = analysisProgressDetail(selectedCamera);
  const showAnalysisProgress =
    selectedCamera.analysis_status === "analyzing" ||
    selectedCamera.analysis_status === "incomplete";

  return (
    <div className="monitor-page">
      <header className="monitor-statusbar">
        <div className="monitor-title-group">
          <span className="monitor-kicker">
            <Moon size={14} />
            Overnight review
          </span>
          <div>
            <h1>{selectedCamera.camera_id}</h1>
            <p>
              {selectedCamera.enclosure_id}
              <span>·</span>
              {selectedCamera.animal_names?.join(", ") || "Animal not assigned"}
              <span>·</span>
              {selectedCamera.animal_species?.join(", ") || "Species not assigned"}
            </p>
          </div>
        </div>
        <dl className="monitor-metrics">
          <div>
            <dt>Recorded</dt>
            <dd>{formatDate(selectedCamera.first_start_ts)}</dd>
          </div>
          <div>
            <dt>Provider</dt>
            <dd>{providerDisplayName}</dd>
          </div>
          <div>
            <dt>Analysis</dt>
            <dd>{analysisLabel(selectedCamera)}</dd>
          </div>
          <div className="review-mode">
            <dt>Delivery</dt>
            <dd>
              <ShieldCheck size={13} />
              Shadow mode
            </dd>
          </div>
        </dl>
      </header>

      {showAnalysisProgress && (
        <section
          className="analysis-progress"
          data-status={selectedCamera.analysis_status}
          aria-live="polite"
        >
          <span className="monitor-spinner" aria-hidden="true" />
          <div>
            <strong>{analysisLabel(selectedCamera)}</strong>
            {selectedAnalysisProgress && <p>{selectedAnalysisProgress}</p>}
          </div>
        </section>
      )}

      <section className="event-log" aria-label="Welfare event log">
        <header>
          <div>
            <span>Review first</span>
            <strong>Welfare event log</strong>
          </div>
          <small>
            {trackLoading
              ? "Loading rule checks"
              : selectedCamera.analysis_status === "analyzing"
              ? analysisLabel(selectedCamera)
              : track.events.length
              ? `${track.events.length} rule event${track.events.length === 1 ? "" : "s"}`
              : "No welfare rules fired"}
          </small>
        </header>
        {trackLoading ? (
          <p className="event-log-empty">
            <span className="monitor-spinner" aria-hidden="true" />
            Loading observations and deterministic rule checks.
          </p>
        ) : track.events.length ? (
          <div className="event-log-list">
            {track.events.map((event) => (
              <button
                type="button"
                key={event.event_id}
                data-selected={
                  selectedEvidence?.kind === "event" &&
                  selectedEvidence.id === event.event_id
                }
                data-severity={event.severity.toLowerCase()}
                onClick={() =>
                  selectEvidence("event", event.event_id, event.start_seconds)
                }
              >
                <time>{formatDuration(event.start_seconds)}</time>
                <span>
                  <strong>{formatBehavior(event.behavior)}</strong>
                  <small>
                    {event.animal_name} · {formatRule(event.rule_fired)}
                  </small>
                </span>
                <em>{formatBehavior(event.severity)}</em>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>
        ) : (
          <p className="event-log-empty">
            {selectedSourceFullyAnalyzed ? (
              <Check size={15} />
            ) : (
              <Activity size={15} />
            )}
            {emptyEventMessage(selectedCamera)}
          </p>
        )}
      </section>

      <div className="monitor-layout">
        <div className="monitor-primary">
          <section className="video-panel" aria-label="Recorded camera video">
            <header className="video-panel-header">
              <div>
                <span className="recorded-dot" />
                <strong>Recorded camera</strong>
                <span>
                  {formatWallClock(selectedCamera.first_start_ts, currentSeconds)}
                </span>
              </div>
              <div className="video-source-label">
                <Video size={14} />
                <span>{selectedCamera.chunk_count} analyzed chunks</span>
              </div>
            </header>

            <div
              className="video-stage"
              ref={videoStageRef}
              data-playing={playing}
            >
              <video
                ref={videoRef}
                src={selectedCamera.media_url}
                poster={poster}
                preload="auto"
                autoPlay
                loop
                muted
                playsInline
                onLoadedMetadata={(event) => {
                  const video = event.currentTarget;
                  const duration =
                    Number.isFinite(video.duration) && video.duration > 0
                      ? video.duration
                      : authoritativeSourceDuration(
                          selectedCamera.probe_duration_seconds,
                          track,
                        );
                  const pending = pendingSeekRef.current;
                  const initial = clamp(
                    pending?.sourcePath === selectedCamera.source_path
                      ? pending.seconds
                      : initialEvidenceSeconds(track),
                    0,
                    duration,
                  );
                  if (pending?.sourcePath === selectedCamera.source_path) {
                    pendingSeekRef.current = null;
                  }
                  video.playbackRate = playbackRate;
                  video.currentTime = initial;
                  setDurationSeconds(duration);
                  setProgress((initial / duration) * 100);
                  setMediaError(null);
                  window.requestAnimationFrame(() =>
                    setVideoBounds(
                      containedVideoBounds(videoStageRef.current!, video),
                    ),
                  );
                  void video.play().catch(() => setPlaying(false));
                }}
                onTimeUpdate={(event) => {
                  const video = event.currentTarget;
                  if (Number.isFinite(video.duration) && video.duration > 0) {
                    setProgress((video.currentTime / video.duration) * 100);
                  }
                }}
                onPlay={() => {
                  setPlaying(true);
                  setSelectedEvidence(null);
                }}
                onPause={() => setPlaying(false)}
                onEnded={() => setPlaying(false)}
                onError={() =>
                  setMediaError(
                    "The recording could not be decoded by this browser.",
                  )
                }
                aria-label={`${selectedCamera.camera_id} recorded footage`}
              />

              <div
                className="detection-layer"
                style={{
                  left: videoBounds.left,
                  top: videoBounds.top,
                  width: videoBounds.width,
                  height: videoBounds.height,
                }}
                aria-label="Spatial animal evidence overlays"
                role="group"
              >
                {visibleDetections.map((detection, detectionIndex) => (
                  <span
                    aria-label={detection.provenanceTitle}
                    className="motion-box"
                    data-canonical-label={detection.displayLabel}
                    data-source={detection.source}
                    data-label-align={
                      detection.box.x + detection.box.width / 2 >= 0.5
                        ? "right"
                        : "left"
                    }
                    data-label-position={
                      detection.box.y <
                      0.12 + (detectionIndex % 3) * 0.08
                        ? "below"
                        : detection.box.y + detection.box.height >
                            0.78 - (detectionIndex % 3) * 0.08
                          ? "above"
                          : detectionIndex % 2 === 1
                            ? "below"
                            : "above"
                    }
                    data-label-lane={detectionIndex % 3}
                    key={detection.detection_id}
                    role="img"
                    style={{
                      left: `${detection.box.x * 100}%`,
                      top: `${detection.box.y * 100}%`,
                      width: `${detection.box.width * 100}%`,
                      height: `${detection.box.height * 100}%`,
                    }}
                    title={detection.provenanceTitle}
                  >
                    <span>
                      <span className="motion-box-label">
                        {detection.displayLabel}
                      </span>
                      <b>{Math.round(detection.score * 100)}%</b>
                    </span>
                  </span>
                ))}
              </div>

              <div className="stage-badges" aria-hidden="true">
                <span>
                  <Camera size={12} />
                  {selectedCamera.camera_id}
                </span>
                <span className="evidence-mode-badge">
                  <Video size={12} />
                  {usesTwelveLabs && usesFrameSampledAnalysis
                    ? "Video + frame analysis"
                    : usesTwelveLabs
                      ? "TwelveLabs analyzed"
                      : usesFrameSampledAnalysis
                        ? "Frame-sampled analysis"
                        : "Provider analysis unavailable"}
                </span>
              </div>

              {!playing && (
                <button
                  type="button"
                  className="stage-play"
                  onClick={togglePlayback}
                  aria-label="Play recording"
                >
                  <Play size={24} fill="currentColor" />
                </button>
              )}

              <div className="stage-context">
                <span className={currentEventActive ? "event-active" : ""}>
                  {currentEventActive ? (
                    <AlertTriangle size={13} />
                  ) : (
                    <Activity size={13} />
                  )}
                  <span className="stage-context-label">
                    {currentEventActive
                      ? `${selectedEvent?.severity} · ${formatBehavior(selectedEvent?.behavior)}`
                      : `Observed activity · ${currentActivity}`}
                  </span>
                </span>
                <span>
                  {isFixtureEvidence
                    ? "Evidence annotation · open the source moment to review"
                    : selectedObservationIsFrameSampled
                      ? "Frame-sampled observation · keeper verification required"
                      : usesTwelveLabs
                      ? "Pegasus 1.5 observation · keeper verification required"
                      : "No structured observation at this moment"}
                </span>
              </div>
            </div>

            <div className="video-transport">
              <div className="transport-controls">
                <button
                  type="button"
                  onClick={() => seekToSeconds(0)}
                  aria-label="Go to recording start"
                  title="Recording start"
                >
                  <SkipBack size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => seekBy(-10)}
                  aria-label="Go back 10 seconds"
                  title="Back 10 seconds"
                >
                  <ChevronLeft size={17} />
                  <span>10</span>
                </button>
                <button
                  type="button"
                  className="primary-play"
                  data-testid="video-play-toggle"
                  onClick={togglePlayback}
                  aria-label={playing ? "Pause recording" : "Play recording"}
                >
                  {playing ? (
                    <Pause size={17} fill="currentColor" />
                  ) : (
                    <Play size={17} fill="currentColor" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => seekBy(10)}
                  aria-label="Go forward 10 seconds"
                  title="Forward 10 seconds"
                >
                  <span>10</span>
                  <ChevronRight size={17} />
                </button>
                <button
                  type="button"
                  onClick={() => seekToSeconds(durationSeconds)}
                  aria-label="Go to recording end"
                  title="Recording end"
                >
                  <SkipForward size={16} />
                </button>
              </div>

              <time className="transport-time">
                {formatDuration(currentSeconds)}
                <span>/</span>
                {formatDuration(durationSeconds)}
              </time>

              <div
                className="speed-control"
                role="group"
                aria-label="Playback speed"
              >
                {PLAYBACK_SPEEDS.map((speed) => (
                  <button
                    type="button"
                    key={speed}
                    data-active={speed === playbackRate}
                    onClick={() => updatePlaybackRate(speed)}
                    aria-pressed={speed === playbackRate}
                  >
                    {speed}x
                  </button>
                ))}
              </div>

              <button
                type="button"
                className="next-evidence"
                onClick={() => jumpToEvidence(1)}
              >
                <Sparkles size={14} />
                Next evidence
              </button>
              <button
                type="button"
                className="fullscreen-button"
                onClick={openFullscreen}
                aria-label="Open fullscreen"
                title="Fullscreen"
              >
                <Maximize2 size={16} />
              </button>
            </div>

            {mediaError && (
              <p className="media-error" role="alert">
                <AlertTriangle size={14} />
                {mediaError}
              </p>
            )}
          </section>

          <EvidenceTimeline
            durationSeconds={durationSeconds}
            loading={trackLoading}
            onSelectEvent={(id, seconds) =>
              selectEvidence("event", id, seconds)
            }
            onSelectObservation={(id, seconds) =>
              selectEvidence("observation", id, seconds)
            }
            onSeek={seekToSeconds}
            progress={progress}
            selectedEventId={selectedEvent?.event_id}
            track={track}
          />
        </div>

        <aside className="evidence-sidebar" aria-label="Evidence inspector">
          <section
            className="evidence-inspector"
            data-focused={selectedEvidence != null}
            ref={inspectorRef}
            tabIndex={-1}
          >
            <header>
              <div>
                <span>
                  {selectedEvidence ? "Selected evidence" : "Evidence inspector"}
                </span>
                <strong>
                  {formatWallClock(selectedCamera.first_start_ts, currentSeconds)}
                </strong>
              </div>
              <span className="fixture-badge">
                {isFixtureEvidence ? "Evidence scenario" : "Provider evidence"}
              </span>
            </header>

            <div className="activity-summary">
              <span className="activity-summary-icon">
                <Footprints size={18} />
              </span>
              <div>
                <span>Observed activity</span>
                <strong>{currentActivity}</strong>
                <p>
                  {isFixtureEvidence
                    ? "Evidence annotation connected to localization and deterministic rule review."
                    : "Structured observation nearest to the playhead."}
                </p>
              </div>
            </div>

            <div
              className={`event-summary severity-${
                selectedEvent?.severity.toLowerCase() ?? "none"
              }`}
            >
              <span className="event-summary-icon">
                {selectedEvent ? (
                  <AlertTriangle size={18} />
                ) : (
                  <Check size={18} />
                )}
              </span>
              <div>
                <span>
                  {selectedEvent
                    ? `${selectedEvent.severity} welfare event`
                    : "No rule event"}
                </span>
                <strong>{formatBehavior(selectedEvent?.behavior)}</strong>
                <p>
                  {selectedEvent
                    ? `${formatRule(selectedEvent.rule_fired)} matched the recorded evidence.`
                    : "No deterministic rule fired for this recording."}
                </p>
              </div>
            </div>

            <div className="response-summary" data-triggered={selectedEvent?.action != null}>
              <span className="response-summary-icon">
                {selectedEvent?.action ? <Route size={18} /> : <ShieldCheck size={18} />}
              </span>
              <div>
                <span>Keeper response</span>
                <strong>
                  {selectedEvent?.action
                    ? formatBehavior(selectedEvent.action)
                    : "No response triggered"}
                </strong>
                <p>
                  {selectedEvent?.action
                    ? `${formatRule(selectedEvent.rule_fired)} selected this constrained response.`
                    : "Continue routine review; no deterministic welfare rule fired."}
                </p>
              </div>
            </div>

            <dl className="evidence-facts">
              <div>
                <dt>Animal</dt>
                <dd>{selectedEvent?.animal_name ?? selectedCamera.animal_names[0] ?? "Unassigned"}</dd>
              </div>
              <div>
                <dt>Rule fired</dt>
                <dd>{formatRule(selectedEvent?.rule_fired)}</dd>
              </div>
              <div>
                <dt>Response</dt>
                <dd>{selectedEvent?.action ? formatBehavior(selectedEvent.action) : "None"}</dd>
              </div>
              <div>
                <dt>Evidence window</dt>
                <dd>
                  {selectedEvent
                    ? `${formatDuration(selectedEvent.start_seconds)}–${formatDuration(
                        selectedEvent.end_seconds,
                      )}`
                    : "Not applicable"}
                </dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{confidenceSummary(selectedEvent?.confidence)}</dd>
              </div>
              <div>
                <dt>Review state</dt>
                <dd>{selectedEvent?.ack_state ?? selectedEvent?.review_state ?? "Pending"}</dd>
              </div>
            </dl>

            <div className="observation-note">
              <span>
                <Eye size={14} />
                Observation detail
              </span>
              <strong>{currentActivity}</strong>
              <p>
                {selectedObservation
                  ? readableEvidenceDetail(selectedObservation.evidence)
                  : "No observation was recorded near this point."}
              </p>
              {selectedObservation && (
                <small>
                  {readableObservationSource(
                    selectedObservation.provider,
                    selectedObservation.evidence_kind,
                  )}
                </small>
              )}
            </div>

            <p className="review-boundary">
              <ShieldCheck size={14} />
              Evidence only. A keeper verifies the clip before any action.
            </p>
          </section>

          <section className="motion-inspector">
            <header>
              <div>
                <span>Video analysis</span>
                <strong>Provider evidence</strong>
              </div>
            </header>

            <div className="motion-summary">
              <span>
                <Video size={14} />
                {track.observations.length} structured observations
              </span>
              <span>
                {selectedCamera.chunk_count} analyzed chunks
              </span>
            </div>

            <div className="observation-note">
              <span>
                <Eye size={14} />
                Current provider finding
              </span>
              <strong>{currentActivity}</strong>
              <p>
                {selectedObservation
                  ? readableEvidenceDetail(selectedObservation.evidence)
                  : "No structured observation was returned near this point."}
              </p>
              <small>
                {selectedObservationIsFrameSampled
                  ? "Timestamped still-frame review, without continuous audio"
                  : usesTwelveLabs
                  ? "Temporal video understanding, not spatial object tracking"
                  : "Provider coverage is unavailable"}
              </small>
            </div>
          </section>
        </aside>
      </div>

      <section className="camera-section" aria-label="Camera selection">
        <header>
          <div>
            <span>Recorded sources</span>
            <strong>Camera views</strong>
          </div>
          <div>
            <button
              type="button"
              onClick={() => changeCamera(-1)}
              aria-label="Previous camera"
            >
              <ChevronLeft size={17} />
            </button>
            <span>
              {cameraIndex + 1} / {videos.length}
            </span>
            <button
              type="button"
              onClick={() => changeCamera(1)}
              aria-label="Next camera"
            >
              <ChevronRight size={17} />
            </button>
          </div>
        </header>

        <div
          className="camera-grid"
          role="radiogroup"
          aria-label="Recorded camera sources"
        >
          {videos.map((cameraSource, index) => {
            const active = index === cameraIndex;
            const sourcePoster =
              POSTER_BY_SOURCE_PATH[cameraSource.source_path];
            return (
              <motion.button
                type="button"
                className="camera-card"
                role="radio"
                aria-checked={active}
                data-active={active}
                key={cameraSource.source_path}
                onClick={() => selectCamera(index)}
                whileTap={reduceMotion ? undefined : { scale: 0.99 }}
              >
                <span className="camera-card-image">
                  {/* Static extracted frames avoid loading every full video in the camera list. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={sourcePoster}
                    alt={`${cameraSource.camera_id} recorded camera preview`}
                  />
                  <span className="camera-card-state">
                    <span
                      className={
                        sourceIsFullyAnalyzed(cameraSource)
                          ? "recorded-dot analysis-complete-dot"
                          : "recorded-dot"
                      }
                    />
                    {analysisLabel(cameraSource)}
                  </span>
                  {active && (
                    <span className="camera-card-selected">
                      <Check size={13} />
                      Selected
                    </span>
                  )}
                </span>
                <span className="camera-card-copy">
                  <span>
                    <strong>{cameraSource.camera_id}</strong>
                    <small>
                      {cameraSource.enclosure_id} ·{" "}
                      {cameraSource.animal_species?.join(", ") || "Unassigned species"}
                    </small>
                  </span>
                  <span className="camera-card-metrics">
                    <span>
                      <Footprints size={13} />
                      {cameraSource.animal_names?.join(", ") || "Unassigned"}
                    </span>
                    <span>
                      <Eye size={13} />
                      {cameraSource.observation_count} moments
                    </span>
                    <span>
                      <Clock3 size={13} />
                      {sourceDurationLabel(cameraSource)}
                    </span>
                  </span>
                </span>
              </motion.button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
