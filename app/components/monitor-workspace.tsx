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
  type VideoSource,
  type VideoTrack,
} from "../lib/api";

const PLAYBACK_SPEEDS = [0.5, 1, 2] as const;
const COVERAGE_BINS = 72;
const DETECTION_HOLD_SECONDS = 1.5;
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
  function latestFrame(source: string) {
    const candidates = detections.filter(
      (item) =>
        item.source === source &&
        item.video_seconds <= currentSeconds + 0.05 &&
        currentSeconds - item.video_seconds <= DETECTION_HOLD_SECONDS,
    );
    if (candidates.length === 0) return [];
    const latestSeconds = Math.max(
      ...candidates.map((item) => item.video_seconds),
    );
    return candidates.filter(
      (item) => Math.abs(item.video_seconds - latestSeconds) < 0.001,
    );
  }

  const yolo = latestFrame("yolov8_object");
  return yolo.length > 0 ? yolo : latestFrame("motion_region");
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

function EvidenceTimeline({
  durationSeconds,
  onSelectEvent,
  onSelectObservation,
  onSeek,
  progress,
  selectedEventId,
  track,
}: {
  durationSeconds: number;
  onSelectEvent: (id: string, seconds: number) => void;
  onSelectObservation: (id: string, seconds: number) => void;
  onSeek: (seconds: number) => void;
  progress: number;
  selectedEventId?: string;
  track: VideoTrack;
}) {
  const objectCandidates = useMemo(
    () =>
      track.detections.filter(
        (detection) => detection.source === "yolov8_object",
      ),
    [track.detections],
  );
  const movementRegions = useMemo(
    () =>
      track.detections.filter(
        (detection) => detection.source === "motion_region",
      ),
    [track.detections],
  );
  const objectCandidateBins = useMemo(
    () => detectionTimelineBins(objectCandidates, durationSeconds),
    [durationSeconds, objectCandidates],
  );
  const movementRegionBins = useMemo(
    () => detectionTimelineBins(movementRegions, durationSeconds),
    [durationSeconds, movementRegions],
  );
  const objectCandidatePeak = Math.max(1, ...objectCandidateBins);
  const movementRegionPeak = Math.max(1, ...movementRegionBins);
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
      style={{ "--timeline-progress": progress / 100 } as CSSProperties}
    >
      <header className="timeline-heading">
        <div>
          <span>Recorded evidence</span>
          <strong>Shift timeline</strong>
        </div>
        <p>
          <span className="legend-swatch candidate" />
          Candidate
          <span className="legend-swatch movement" />
          Movement
          <span className="legend-swatch observation" />
          Observation
          <span className="legend-swatch event" />
          Rule event
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
        aria-label={`${objectCandidates.length} object candidate samples`}
      >
        <span className="timeline-label">
          <ScanLine size={14} />
          <span className="timeline-label-long">Object candidates</span>
          <span className="timeline-label-short">Objects</span>
        </span>
        <div className="timeline-track detection-heatmap candidate-heatmap">
          {objectCandidates.length === 0 ? (
            <span className="empty-track">No object candidates</span>
          ) : (
            objectCandidateBins.map((count, index) => (
              <i
                aria-hidden="true"
                key={index}
                style={{
                  opacity:
                    count === 0
                      ? 0.08
                      : 0.24 + (count / objectCandidatePeak) * 0.76,
                }}
              />
            ))
          )}
          {objectCandidates.length > 0 && (
            <small className="timeline-track-count">
              {objectCandidates.length} samples
            </small>
          )}
        </div>
      </div>

      <div
        className="timeline-row"
        aria-label={`${movementRegions.length} measured movement region samples`}
      >
        <span className="timeline-label">
          <Activity size={14} />
          <span className="timeline-label-long">Movement regions</span>
          <span className="timeline-label-short">Motion</span>
        </span>
        <div className="timeline-track detection-heatmap movement-heatmap">
          {movementRegions.length === 0 ? (
            <span className="empty-track">No movement regions</span>
          ) : (
            movementRegionBins.map((count, index) => (
              <i
                aria-hidden="true"
                key={index}
                style={{
                  opacity:
                    count === 0
                      ? 0.08
                      : 0.24 + (count / movementRegionPeak) * 0.76,
                }}
              />
            ))
          )}
          {movementRegions.length > 0 && (
            <small className="timeline-track-count">
              {movementRegions.length} samples
            </small>
          )}
        </div>
      </div>

      <div className="timeline-row">
        <span className="timeline-label">
          <Eye size={14} />
          <span className="timeline-label-long">Observations</span>
          <span className="timeline-label-short">Observ.</span>
        </span>
        <div className="timeline-track">
          {track.observations.length === 0 ? (
            <span className="empty-track">No structured observations</span>
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

      <div className="timeline-row">
        <span className="timeline-label">
          <AlertTriangle size={14} />
          <span className="timeline-label-long">Rule events</span>
          <span className="timeline-label-short">Rules</span>
        </span>
        <div className="timeline-track">
          {track.events.length === 0 ? (
            <span className="empty-track">No deterministic rule events</span>
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
  const usesTwelveLabs = Boolean(
    track?.observations.some((observation) => observation.provider === "twelvelabs"),
  );
  const usesFrameSampledAnalysis = Boolean(
    track?.observations.some(
      (observation) => observation.evidence_kind === "frame_sampled_provider",
    ),
  );
  const providerDisplayName =
    usesTwelveLabs && usesFrameSampledAnalysis
      ? "Pegasus + OpenAI"
      : usesTwelveLabs
        ? "Pegasus 1.5"
        : usesFrameSampledAnalysis
          ? "OpenAI vision"
          : "Unavailable";
  const playheadEvent = useMemo(() => {
    if (!track) return null;
    return (
      track.events.find(
        (event) =>
          currentSeconds >= event.start_seconds &&
          currentSeconds <= event.end_seconds,
      ) ?? nearestByStart(track.events, currentSeconds)
    );
  }, [currentSeconds, track]);
  const playheadObservation = useMemo(() => {
    if (!track) return null;
    return observationAtTime(track.observations, currentSeconds);
  }, [currentSeconds, track]);
  const visibleDetections = useMemo(
    () => (track ? detectionsAtTime(track.detections, currentSeconds) : []),
    [currentSeconds, track],
  );
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
    const loadVideos = () => {
      api
        .videos()
        .then(({ videos: sources }) => {
          if (cancelled) return;
          hasLoaded = true;
          setVideos(sources);
          setLoadError(
            sources.length === 0
              ? "No analyzed video sources are available."
              : null,
          );
        })
        .catch((caught: unknown) => {
          if (cancelled || hasLoaded) return;
          setLoadError(
            caught instanceof Error ? caught.message : "Unable to load videos.",
          );
        });
    };
    loadVideos();
    const timer = window.setInterval(loadVideos, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
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
      .videoTrack(selectedSourcePath)
      .then((payload) => {
        if (cancelled) return;
        setTrack(payload);
        setSelectedEvidence(
          (current) =>
            current ??
            (payload.events[0]
              ? { kind: "event", id: payload.events[0].event_id }
              : payload.observations[0]
                ? {
                    kind: "observation",
                    id: payload.observations[0].observation_id,
                  }
                : null),
        );
        setDurationSeconds(authoritativeSourceDuration(selectedProbeDuration, payload));
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setLoadError(
          caught instanceof Error
            ? caught.message
            : "Unable to load the video evidence track.",
        );
      });
    return () => {
      cancelled = true;
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
    videoRef.current?.pause();
    setLoadError(null);
    setMediaError(null);
    setPlaying(false);
    setProgress(0);
    setTrack(null);
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
            {selectedCamera.analysis_status === "analyzing"
              ? analysisLabel(selectedCamera)
              : track.events.length
              ? `${track.events.length} rule event${track.events.length === 1 ? "" : "s"}`
              : "No welfare rules fired"}
          </small>
        </header>
        {track.events.length ? (
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
                onPlay={() => setPlaying(true)}
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
                aria-hidden="true"
              >
                {visibleDetections.map((detection) => (
                  <span
                    className="motion-box"
                    data-source={detection.source}
                    key={detection.detection_id}
                    style={{
                      left: `${detection.box.x * 100}%`,
                      top: `${detection.box.y * 100}%`,
                      width: `${detection.box.width * 100}%`,
                      height: `${detection.box.height * 100}%`,
                    }}
                  >
                    <span>
                      {detection.source === "yolov8_object"
                        ? formatBehavior(
                            `${detection.label ?? "animal"} candidate`,
                          )
                        : "Movement region"}
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
                  {currentEventActive
                    ? `${selectedEvent?.severity} · ${formatBehavior(selectedEvent?.behavior)}`
                    : `Observed activity · ${currentActivity}`}
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
