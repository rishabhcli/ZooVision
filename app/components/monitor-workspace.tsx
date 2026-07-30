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
  ScanLine,
  ShieldCheck,
  SkipBack,
  SkipForward,
  Sparkles,
  Route,
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
const MOTION_BINS = 72;
const POSTER_BY_CAMERA: Record<string, string> = {
  "CAM-03Y": "/camera-posters/cam-03y-gorilla.jpg?v=ad815f51",
  "CAM-05N": "/camera-posters/cam-05n-elephant.jpg?v=dcdd8d17",
  "CAM-07A": "/camera-posters/cam-07a-lion.jpg?v=46763447",
  "CAM-BY1": "/media/uploads/backyard-squirrel-staircase-poster.jpg?v=7d576fa3",
  "CAM-BY2":
    "/media/uploads/backyard-squirrels-and-birds-poster.jpg?v=71ed3e94",
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

function trackRole(index: number) {
  if (index === 0) return "Primary subject";
  if (index === 1) return "Companion subject";
  return `Context track ${String(index - 1).padStart(2, "0")}`;
}

function formatDuration(seconds: number) {
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

function formatDate(value: string) {
  return new Date(value).toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
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
    ...track.detections.map((item) => item.video_seconds),
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

function preferredDetections(track: VideoTrack) {
  const yolo = track.detections.filter(
    (item) => item.source === "yolov8_object",
  );
  return yolo.length > 0
    ? yolo
    : track.detections.filter((item) => item.source === "motion_region");
}

function initialEvidenceSeconds(track: VideoTrack) {
  const detections = preferredDetections(track);
  const visibleDetection = detections.reduce<VideoDetection | null>(
    (largest, detection) => {
    if (!largest) return detection;
    const area = detection.box.width * detection.box.height;
    const largestArea = largest.box.width * largest.box.height;
    return area > largestArea ? detection : largest;
    },
    null,
  );
  if (visibleDetection) return visibleDetection.video_seconds;

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
  return detections[0]?.video_seconds ?? 0;
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

function EvidenceTimeline({
  durationSeconds,
  onSeek,
  progress,
  selectedEventId,
  track,
}: {
  durationSeconds: number;
  onSeek: (seconds: number) => void;
  progress: number;
  selectedEventId?: string;
  track: VideoTrack;
}) {
  const detections = useMemo(() => preferredDetections(track), [track]);
  const usesYolo = detections.some(
    (detection) => detection.source === "yolov8_object",
  );
  const bins = useMemo(() => {
    const next = Array.from({ length: MOTION_BINS }, () => 0);
    for (const detection of detections) {
      const index = clamp(
        Math.floor((detection.video_seconds / durationSeconds) * MOTION_BINS),
        0,
        MOTION_BINS - 1,
      );
      next[index] += 1;
    }
    return next;
  }, [detections, durationSeconds]);
  const peak = Math.max(1, ...bins);
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
          <span className="legend-swatch motion" />
          {usesYolo ? "YOLO objects" : "Motion"}
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

      <div className="timeline-row">
        <span className="timeline-label">
          <ScanLine size={14} />
          {usesYolo ? "Objects" : "Motion"}
        </span>
        <div className="timeline-track motion-heatmap" aria-hidden="true">
          {bins.map((count, index) => (
            <i
              key={index}
              style={{ opacity: count === 0 ? 0.08 : 0.24 + (count / peak) * 0.76 }}
            />
          ))}
        </div>
      </div>

      <div className="timeline-row">
        <span className="timeline-label">
          <Eye size={14} />
          Observations
        </span>
        <div className="timeline-track">
          {track.observations.map((observation) => {
            const width = Math.max(
              1.2,
              ((observation.end_seconds - observation.start_seconds) /
                durationSeconds) *
                100,
            );
            return (
              <button
                type="button"
                className="timeline-span observation-span"
                key={observation.observation_id}
                onPointerDown={(event) => {
                  if (event.button === 0) onSeek(observation.start_seconds);
                }}
                onClick={() => onSeek(observation.start_seconds)}
                style={{
                  left: `${(observation.start_seconds / durationSeconds) * 100}%`,
                  width: `${width}%`,
                }}
                aria-label={`Seek to ${formatBehavior(observation.behavior)} observation at ${formatDuration(
                  observation.start_seconds,
                )}`}
                title={formatBehavior(observation.behavior)}
              >
                <span>{formatBehavior(observation.behavior)}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="timeline-row">
        <span className="timeline-label">
          <AlertTriangle size={14} />
          Rule events
        </span>
        <div className="timeline-track">
          {track.events.length === 0 ? (
            <span className="empty-track">No non-NONE events</span>
          ) : (
            track.events.map((event) => {
              const width = Math.max(
                2,
                ((event.end_seconds - event.start_seconds) / durationSeconds) *
                  100,
              );
              return (
                <button
                  type="button"
                  className={`timeline-span event-span severity-${event.severity.toLowerCase()}`}
                  data-selected={selectedEventId === event.event_id}
                  key={event.event_id}
                  onPointerDown={(pointerEvent) => {
                    if (pointerEvent.button === 0) onSeek(event.start_seconds);
                  }}
                  onClick={() => onSeek(event.start_seconds)}
                  style={{
                    left: `${(event.start_seconds / durationSeconds) * 100}%`,
                    width: `${width}%`,
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
  const [showAllTracks, setShowAllTracks] = useState(false);
  const [track, setTrack] = useState<VideoTrack | null>(null);
  const [trackVisibility, setTrackVisibility] = useState<Record<string, boolean>>({});
  const [videos, setVideos] = useState<VideoSource[]>([]);
  const pendingSeekRef = useRef<{
    sourcePath: string;
    seconds: number;
  } | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoStageRef = useRef<HTMLDivElement>(null);
  const selectedCamera = videos[cameraIndex];
  const currentSeconds = (progress / 100) * durationSeconds;
  const localizedDetections = useMemo(
    () => (track ? preferredDetections(track) : []),
    [track],
  );
  const usesYolo = localizedDetections.some(
    (detection) => detection.source === "yolov8_object",
  );
  const usesTwelveLabs = Boolean(
    track?.observations.some((observation) => observation.provider === "twelvelabs"),
  );

  const trackIds = useMemo(() => {
    const stats = new Map<
      string,
      { samples: number; score: number; largestArea: number }
    >();
    for (const detection of localizedDetections) {
      const current = stats.get(detection.track_id) ?? {
        samples: 0,
        score: 0,
        largestArea: 0,
      };
      current.samples += 1;
      current.score += detection.score;
      current.largestArea = Math.max(
        current.largestArea,
        detection.box.width * detection.box.height,
      );
      stats.set(detection.track_id, current);
    }
    return [...stats.entries()]
      .sort(([, left], [, right]) => {
        const persistence = right.samples - left.samples;
        if (persistence !== 0) return persistence;
        const prominence = right.largestArea - left.largestArea;
        if (prominence !== 0) return prominence;
        return right.score - left.score;
      })
      .map(([trackId]) => trackId);
  }, [localizedDetections]);
  const trackLabels = useMemo(
    () =>
      new Map(
        trackIds.map((trackId, index) => [
          trackId,
          usesYolo ? trackRole(index) : `Motion ${String(index + 1).padStart(2, "0")}`,
        ]),
      ),
    [trackIds, usesYolo],
  );
  const activeDetections = useMemo(() => {
    const visible = localizedDetections.filter(
      (detection) => trackVisibility[detection.track_id] !== false,
    );
    const nearestTimestamp = visible.reduce<number | null>((nearest, detection) => {
      if (Math.abs(detection.video_seconds - currentSeconds) > 1.25) return nearest;
      if (nearest == null) return detection.video_seconds;
      return Math.abs(detection.video_seconds - currentSeconds) <
        Math.abs(nearest - currentSeconds)
        ? detection.video_seconds
        : nearest;
    }, null);
    if (nearestTimestamp == null) return [];
    return visible
      .filter(
        (detection) =>
          Math.abs(detection.video_seconds - nearestTimestamp) < 0.001,
      )
      .sort((left, right) => right.score - left.score)
      .slice(0, 4);
  }, [currentSeconds, localizedDetections, trackVisibility]);
  const selectedEvent = useMemo(() => {
    if (!track) return null;
    return (
      track.events.find(
        (event) =>
          currentSeconds >= event.start_seconds &&
          currentSeconds <= event.end_seconds,
      ) ?? nearestByStart(track.events, currentSeconds)
    );
  }, [currentSeconds, track]);
  const selectedObservation = useMemo(() => {
    if (!track) return null;
    return observationAtTime(track.observations, currentSeconds);
  }, [currentSeconds, track]);
  const orderedTrackIds = useMemo(() => {
    const active = new Set(activeDetections.map((item) => item.track_id));
    return [
      ...trackIds.filter((trackId) => active.has(trackId)),
      ...trackIds.filter((trackId) => !active.has(trackId)),
    ];
  }, [activeDetections, trackIds]);
  const displayedTrackIds = showAllTracks
    ? orderedTrackIds
    : orderedTrackIds.slice(0, 6);
  const allTracksVisible =
    trackIds.length > 0 &&
    trackIds.every((trackId) => trackVisibility[trackId] !== false);

  useEffect(() => {
    api
      .videos()
      .then(({ videos: sources }) => {
        setVideos(sources);
        if (sources.length === 0) {
          setLoadError("No analyzed video sources are available.");
        }
      })
      .catch((caught: unknown) =>
        setLoadError(
          caught instanceof Error ? caught.message : "Unable to load videos.",
        ),
      );
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
    if (!selectedCamera) return;
    api
      .videoTrack(selectedCamera.source_path)
      .then((payload) => {
        setTrack(payload);
        setDurationSeconds(maximumTrackSeconds(payload));
        setTrackVisibility(
          Object.fromEntries(
            [...new Set(preferredDetections(payload).map((item) => item.track_id))].map(
              (trackId) => [trackId, true],
            ),
          ),
        );
      })
      .catch((caught: unknown) =>
        setLoadError(
          caught instanceof Error
            ? caught.message
            : "Unable to load the video evidence track.",
        ),
      );
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
      ...preferredDetections(track).map(
        (detection) => detection.video_seconds,
      ),
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
    setCameraIndex(index);
    setShowAllTracks(false);
  }

  function changeCamera(direction: -1 | 1) {
    if (videos.length === 0) return;
    selectCamera((cameraIndex + direction + videos.length) % videos.length);
  }

  function toggleAllTracks() {
    const nextVisible = !allTracksVisible;
    setTrackVisibility(
      Object.fromEntries(trackIds.map((trackId) => [trackId, nextVisible])),
    );
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

  const poster =
    POSTER_BY_CAMERA[selectedCamera.camera_id] ??
    POSTER_BY_CAMERA["CAM-07A"];
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
            <dt>{usesYolo ? "Spatial tracks" : "Motion regions"}</dt>
            <dd>{trackIds.length}</dd>
          </div>
          <div>
            <dt>Tracked moments</dt>
            <dd>{selectedCamera.observation_count}</dd>
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
                      : maximumTrackSeconds(track);
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

              <div className="stage-badges" aria-hidden="true">
                <span>
                  <Camera size={12} />
                  {selectedCamera.camera_id}
                </span>
                <span className="evidence-mode-badge">
                  <ScanLine size={12} />
                  {usesTwelveLabs
                    ? "TwelveLabs analyzed"
                    : usesYolo
                      ? "YOLOv8n"
                      : "Motion fallback"}
                </span>
              </div>

              {activeDetections.map((detection) => (
                <i
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
                    {trackLabels.get(detection.track_id)}
                    <b>{Math.round(detection.score * 100)}%</b>
                  </span>
                </i>
              ))}

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
                    ? "Demo annotation · spatial tracks shown separately"
                    : usesYolo
                      ? `${activeDetections.length} localized at playhead · verify identity`
                      : "Motion only · no identity or diagnosis inferred"}
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
            onSeek={seekToSeconds}
            progress={progress}
            selectedEventId={selectedEvent?.event_id}
            track={track}
          />
        </div>

        <aside className="evidence-sidebar" aria-label="Evidence inspector">
          <section className="evidence-inspector">
            <header>
              <div>
                <span>Evidence inspector</span>
                <strong>
                  {formatWallClock(selectedCamera.first_start_ts, currentSeconds)}
                </strong>
              </div>
              <span className="fixture-badge">
                {isFixtureEvidence ? "Fixture scenario" : "Provider evidence"}
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
                    ? "Demo annotation, kept separate from localization and severity."
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
                  {currentEventActive
                    ? "The playhead is inside this event window."
                    : selectedEvent
                      ? "Nearest rule event to the playhead."
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
                    ? `Deterministic rule ${selectedEvent.rule_fired} selected this constrained response.`
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
                <dd>{selectedEvent?.rule_fired ?? "None"}</dd>
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
                <dd>
                  {selectedEvent?.confidence == null
                    ? "Not provided"
                    : `${Math.round(selectedEvent.confidence * 100)}%`}
                </dd>
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
                {selectedObservation?.evidence ??
                  "No observation was recorded near this point."}
              </p>
              {selectedObservation && (
                <small>
                  {selectedObservation.provider} ·{" "}
                  {formatBehavior(selectedObservation.evidence_kind)}
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
                <span>Overlay controls</span>
                <strong>
                  {usesYolo ? "Spatial subject tracks" : "Measured motion"}
                </strong>
              </div>
              <button
                type="button"
                className="toggle-all"
                onClick={toggleAllTracks}
              >
                {allTracksVisible ? "Hide all" : "Show all"}
              </button>
            </header>

            <div className="motion-summary">
              <span>
                <ScanLine size={14} />
                {activeDetections.length} active
              </span>
              <span>
                {trackIds.length} {usesYolo ? "object" : "motion"} tracks
              </span>
            </div>

            <div className="track-controls">
              {displayedTrackIds.map((trackId) => {
                const activeDetection = activeDetections.find(
                  (item) => item.track_id === trackId,
                );
                const active = activeDetection != null;
                return (
                  <label key={trackId} data-active={active}>
                    <input
                      type="checkbox"
                      checked={trackVisibility[trackId] !== false}
                      onChange={() =>
                        setTrackVisibility((current) => ({
                          ...current,
                          [trackId]: current[trackId] === false,
                        }))
                      }
                    />
                    <i />
                    <span>
                      <strong>{trackLabels.get(trackId)}</strong>
                      <small>
                        {active
                          ? usesYolo
                            ? `Localized object · ${Math.round(
                                (activeDetection?.score ?? 0) * 100,
                              )}%`
                            : "Visible at playhead"
                          : usesYolo
                            ? "Tracked spatial region"
                            : trackId.slice(-8)}
                      </small>
                    </span>
                  </label>
                );
              })}
            </div>

            {orderedTrackIds.length > 6 && (
              <button
                type="button"
                className="show-tracks"
                onClick={() => setShowAllTracks((current) => !current)}
              >
                {showAllTracks
                  ? "Show fewer tracks"
                  : `Show ${orderedTrackIds.length - 6} more tracks`}
              </button>
            )}
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
              POSTER_BY_CAMERA[cameraSource.camera_id] ?? POSTER_BY_CAMERA["CAM-07A"];
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
                    <span className="recorded-dot" />
                    Recorded
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
                      {formatDuration(
                        (new Date(cameraSource.last_end_ts).getTime() -
                          new Date(cameraSource.first_start_ts).getTime()) /
                          1000,
                      )}
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
