import { Camera, Crosshair, Pause, Play, ScanLine } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SEVERITY_COLOR } from "../severity";
import type { DetectionItem, VideoSource, VideoTrack } from "../types";

/** Boxes are sampled, so each stays on screen until the next sample lands. */
const BOX_HOLD_SECONDS = 0.75;

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function clockLabel(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  return `${String(minutes).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** Motion regions visible at a given moment in the media file. */
function activeDetections(detections: DetectionItem[], atSeconds: number) {
  return detections.filter(
    (item) =>
      atSeconds >= item.video_seconds &&
      atSeconds < item.video_seconds + BOX_HOLD_SECONDS
  );
}

export function VideoPanel({
  sources,
  selected,
  track,
  onSelect,
  onOpenEvent
}: {
  sources: VideoSource[];
  selected: string | null;
  track: VideoTrack | null;
  onSelect: (sourcePath: string) => void;
  onOpenEvent: (eventId: string) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);

  const source = sources.find((item) => item.source_path === selected) ?? null;
  const detections = useMemo(() => track?.detections ?? [], [track]);
  const events = useMemo(() => track?.events ?? [], [track]);

  const visible = useMemo(
    () => (showBoxes ? activeDetections(detections, currentTime) : []),
    [detections, currentTime, showBoxes]
  );

  const activeEvents = useMemo(
    () =>
      events.filter(
        (event) =>
          currentTime >= event.start_seconds && currentTime <= event.end_seconds
      ),
    [events, currentTime]
  );

  // Reset the transport whenever the operator switches feeds.
  useEffect(() => {
    setCurrentTime(0);
    setPlaying(false);
  }, [selected]);

  const seek = useCallback((seconds: number) => {
    const media = videoRef.current;
    if (!media) return;
    media.currentTime = Math.max(0, seconds);
    setCurrentTime(Math.max(0, seconds));
  }, []);

  const togglePlay = useCallback(() => {
    const media = videoRef.current;
    if (!media) return;
    if (media.paused) {
      void media.play();
    } else {
      media.pause();
    }
  }, []);

  const timelineSpan = duration || 1;

  return (
    <div className="video-panel">
      <div className="video-rail" role="tablist" aria-label="Camera feeds">
        {sources.map((item) => (
          <button
            key={item.source_path}
            role="tab"
            aria-selected={item.source_path === selected}
            className={
              item.source_path === selected ? "feed-chip active" : "feed-chip"
            }
            onClick={() => onSelect(item.source_path)}
          >
            <Camera size={15} />
            <span>
              <strong>{item.camera_id}</strong>
              <small>
                {item.enclosure_id} · {item.animal_names.join(", ") || "unassigned"}
              </small>
            </span>
            <em>{item.event_count}</em>
          </button>
        ))}
      </div>

      {!source ? (
        <div className="video-empty">
          <Camera size={26} />
          <p>No analyzed footage yet. Upload a video to begin.</p>
        </div>
      ) : (
        <div className="video-stage-wrap">
          <div className="video-stage">
            <video
              ref={videoRef}
              key={source.media_url}
              src={source.media_url}
              playsInline
              muted
              preload="metadata"
              onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
              onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onClick={togglePlay}
            />

            <div className="box-layer" aria-hidden="true">
              {visible.map((item) => (
                <span
                  key={item.detection_id}
                  className="motion-box"
                  style={{
                    left: `${item.box.x * 100}%`,
                    top: `${item.box.y * 100}%`,
                    width: `${item.box.width * 100}%`,
                    height: `${item.box.height * 100}%`
                  }}
                >
                  <em>motion {(item.score * 100).toFixed(0)}%</em>
                </span>
              ))}
            </div>

            {activeEvents.length > 0 && (
              <div className="event-flag">
                {activeEvents.map((event) => (
                  <button
                    key={event.event_id}
                    style={{ borderColor: SEVERITY_COLOR[event.severity] }}
                    onClick={() => onOpenEvent(event.event_id)}
                  >
                    <span
                      className="flag-dot"
                      style={{ background: SEVERITY_COLOR[event.severity] }}
                    />
                    <strong>{event.severity}</strong>
                    <span>
                      {event.animal_name} · {titleCase(event.behavior)}
                    </span>
                    <small>{event.rule_fired}</small>
                  </button>
                ))}
              </div>
            )}

            <span className="stage-badge">
              <ScanLine size={13} /> Motion regions · not species recognition
            </span>
          </div>

          <div className="transport">
            <button
              className="icon-button"
              onClick={togglePlay}
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <span className="clock">
              {clockLabel(currentTime)} / {clockLabel(duration)}
            </span>
            <button
              className={showBoxes ? "toggle-chip on" : "toggle-chip"}
              onClick={() => setShowBoxes((value) => !value)}
            >
              <Crosshair size={14} />
              Boxes {showBoxes ? "on" : "off"}
            </button>
            <span className="transport-count">
              {visible.length} region(s) in frame · {detections.length} measured
            </span>
          </div>

          <div className="timeline">
            <div className="timeline-head">
              <span className="eyebrow">Event timeline</span>
              <span>{events.length} deterministic event(s) on this feed</span>
            </div>
            <div
              className="timeline-track"
              role="slider"
              tabIndex={0}
              aria-label="Seek video"
              aria-valuemin={0}
              aria-valuemax={Math.round(timelineSpan)}
              aria-valuenow={Math.round(currentTime)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight") seek(currentTime + 5);
                if (e.key === "ArrowLeft") seek(currentTime - 5);
              }}
              onClick={(e) => {
                const bounds = e.currentTarget.getBoundingClientRect();
                seek(((e.clientX - bounds.left) / bounds.width) * timelineSpan);
              }}
            >
              <div className="timeline-motion">
                {detections.map((item) => (
                  <span
                    key={item.detection_id}
                    style={{
                      left: `${(item.video_seconds / timelineSpan) * 100}%`,
                      opacity: 0.25 + item.score * 0.6
                    }}
                  />
                ))}
              </div>
              {events.map((event) => (
                <button
                  key={event.event_id}
                  className="timeline-event"
                  title={`${event.animal_name} · ${titleCase(event.behavior)} · ${event.severity}`}
                  style={{
                    left: `${(event.start_seconds / timelineSpan) * 100}%`,
                    width: `${Math.max(
                      0.8,
                      ((event.end_seconds - event.start_seconds) / timelineSpan) * 100
                    )}%`,
                    background: SEVERITY_COLOR[event.severity]
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    seek(event.start_seconds);
                  }}
                />
              ))}
              <span
                className="timeline-playhead"
                style={{ left: `${(currentTime / timelineSpan) * 100}%` }}
              />
            </div>
            <div className="timeline-legend">
              {events.length === 0 ? (
                <span className="legend-note">
                  No rule fired on this feed. Motion ticks show where movement was
                  measured.
                </span>
              ) : (
                events.map((event) => (
                  <button
                    key={event.event_id}
                    className="legend-item"
                    onClick={() => onOpenEvent(event.event_id)}
                  >
                    <span
                      className="flag-dot"
                      style={{ background: SEVERITY_COLOR[event.severity] }}
                    />
                    <strong>{clockLabel(event.start_seconds)}</strong>
                    <span>
                      {event.animal_name} · {titleCase(event.behavior)}
                    </span>
                    <small>{event.rule_fired}</small>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VideoPanel;
