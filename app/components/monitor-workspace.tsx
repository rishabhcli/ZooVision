"use client";

import "./monitor-target.css";

import {
  Bookmark,
  CalendarDays,
  Camera,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Maximize,
  MoreVertical,
  Pause,
  Play,
  Share2,
  SkipBack,
  SkipForward,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import {
  CSSProperties,
  KeyboardEvent,
  PointerEvent,
  useEffect,
  useRef,
  useState,
} from "react";

const cameraOptions = [
  {
    id: "cam-07",
    code: "CAM 07",
    view: "Savanna Overlook",
    position: "42% 17%",
  },
  {
    id: "cam-02",
    code: "CAM 02",
    view: "North Perimeter",
    position: "25% 86%",
  },
  {
    id: "cam-03",
    code: "CAM 03",
    view: "Elephant Yard",
    position: "38% 86%",
  },
  {
    id: "cam-04",
    code: "CAM 04",
    view: "Service Road",
    position: "53% 86%",
  },
  {
    id: "cam-05",
    code: "CAM 05",
    view: "Giraffe Habitat",
    position: "67% 86%",
  },
  {
    id: "cam-06",
    code: "CAM 06",
    view: "Staff Gate",
    position: "81% 86%",
  },
  {
    id: "cam-08",
    code: "CAM 08",
    view: "Bridge Approach",
    position: "92% 86%",
  },
];

const scrubberTicks = Array.from({ length: 53 }, (_, index) => index);
const waveform = [
  5, 7, 10, 4, 8, 12, 6, 9, 5, 13, 8, 4, 7, 11, 6, 5, 9, 14, 7, 4, 8,
  12, 6, 10, 4, 7, 11, 5, 9, 13, 6, 4, 8, 12, 5, 7, 10, 4, 9, 13, 6, 8,
  5, 11, 7, 4, 10, 12, 6, 8, 5, 9, 13, 7, 4, 10, 6, 12, 5, 8, 11, 4,
  9, 6, 13, 7, 5, 10, 4, 8, 12, 6, 9, 5, 11, 7, 4, 10, 6, 13, 8, 5,
];

function formatShiftTime(progress: number) {
  const totalSeconds = Math.round(6 * 60 * 60 * (progress / 100));
  const hours = (23 + Math.floor(totalSeconds / 3600)) % 24;
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(
    2,
    "0",
  )}:${String(seconds).padStart(2, "0")}`;
}

function ChapterScrubber({
  progress,
  onChange,
}: {
  progress: number;
  onChange: (value: number) => void;
}) {
  const reduceMotion = useReducedMotion();
  const activeTick = Math.round(
    (progress / 100) * Math.max(scrubberTicks.length - 1, 1),
  );
  const [hoveredTick, setHoveredTick] = useState<number | null>(null);
  const focusTick = hoveredTick ?? activeTick;

  function tickFromPointer(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(
      1,
      Math.max(0, (event.clientX - bounds.left) / bounds.width),
    );
    return Math.round(ratio * (scrubberTicks.length - 1));
  }

  function commitTick(index: number) {
    onChange((index / (scrubberTicks.length - 1)) * 100);
  }

  function handleKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    let next = activeTick;
    if (event.key === "ArrowLeft") next = Math.max(0, activeTick - 1);
    else if (event.key === "ArrowRight")
      next = Math.min(scrubberTicks.length - 1, activeTick + 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = scrubberTicks.length - 1;
    else return;
    event.preventDefault();
    commitTick(next);
  }

  return (
    <div
      className="chapter-scrubber"
      role="slider"
      tabIndex={0}
      aria-label="Recorded shift position"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress)}
      onKeyDown={handleKeyboard}
      onPointerMove={(event) => setHoveredTick(tickFromPointer(event))}
      onPointerLeave={() => setHoveredTick(null)}
      onPointerDown={(event) => commitTick(tickFromPointer(event))}
    >
      {scrubberTicks.map((tick) => {
        const distance = Math.abs(tick - focusTick);
        const height =
          distance === 0 ? 16 : distance === 1 ? 12 : distance === 2 ? 9 : 6;
        const highlighted =
          tick === 4 ||
          tick === 12 ||
          (tick >= 22 && tick <= 28) ||
          tick === 36 ||
          tick === 45;

        return (
          <motion.i
            key={tick}
            className={highlighted ? "highlighted" : undefined}
            animate={{ height }}
            transition={
              reduceMotion
                ? { duration: 0 }
                : { type: "spring", stiffness: 420, damping: 30 }
            }
          />
        );
      })}
    </div>
  );
}

function Timeline({
  progress,
  onChange,
}: {
  progress: number;
  onChange: (value: number) => void;
}) {
  return (
    <div
      className="production-timeline"
      style={{ "--timeline-progress": progress / 100 } as CSSProperties}
    >
      <div className="production-ruler">
        <span />
        {["23:00", "00:00", "01:00", "02:00", "03:00", "04:00", "05:00"].map(
          (time) => (
            <time key={time}>{time}</time>
          ),
        )}
      </div>

      <div className="production-row detections-row">
        <span className="production-label">
          <i className="blue-dot" />
          Detections
        </span>
        <div className="production-track">
          <ChapterScrubber progress={progress} onChange={onChange} />
        </div>
      </div>

      <div className="production-row">
        <span className="production-label">Tracks</span>
        <div className="production-track">
          <i className="timeline-segment blue" style={{ left: "4%", width: "14%" }} />
          <i className="timeline-segment blue" style={{ left: "21%", width: "8%" }} />
          <i className="timeline-segment blue" style={{ left: "33%", width: "18%" }} />
          <i className="timeline-segment blue" style={{ left: "57%", width: "13%" }} />
          <i className="timeline-segment blue" style={{ left: "71%", width: "10%" }} />
        </div>
      </div>

      <div className="production-row">
        <span className="production-label">Zones</span>
        <div className="production-track">
          <i className="timeline-segment gray" style={{ left: "17%", width: "14%" }} />
          <i className="timeline-segment gray" style={{ left: "58%", width: "11%" }} />
          <i className="timeline-segment gray" style={{ left: "78%", width: "10%" }} />
        </div>
      </div>

      <div className="production-row">
        <span className="production-label">Audio</span>
        <div className="production-track audio-wave" aria-label="Audio waveform">
          {waveform.map((height, index) => (
            <i key={index} style={{ height }} />
          ))}
        </div>
      </div>

      <div className="production-row">
        <span className="production-label">Events</span>
        <div className="production-track">
          {[22, 42, 57, 86].map((left) => (
            <i
              className="timeline-event"
              style={{ left: `${left}%` }}
              key={left}
            />
          ))}
        </div>
      </div>

      <div className="production-row">
        <span className="production-label">Bookmarks</span>
        <div className="production-track">
          {[12, 44, 65, 89].map((left) => (
            <Bookmark
              className="timeline-bookmark"
              style={{ left: `${left}%` }}
              size={14}
              key={left}
            />
          ))}
        </div>
      </div>

      <span className="production-playhead" aria-hidden="true">
        <b>{formatShiftTime(progress)}</b>
      </span>
    </div>
  );
}

export function MonitorWorkspace() {
  const reduceMotion = useReducedMotion();
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(37.7);
  const [cameraIndex, setCameraIndex] = useState(0);
  const [trackVisibility, setTrackVisibility] = useState([true, true]);
  const galleryRef = useRef<HTMLDivElement>(null);
  const selectedCamera = cameraOptions[cameraIndex];

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 100) {
          setPlaying(false);
          return 0;
        }
        return Math.min(100, current + 0.05);
      });
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    const viewport = galleryRef.current;
    const card = viewport?.querySelector<HTMLElement>(
      `[data-camera-index="${cameraIndex}"]`,
    );
    if (!viewport || !card) return;
    viewport.scrollTo({
      left: Math.max(0, card.offsetLeft - 4),
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [cameraIndex, reduceMotion]);

  function changeCamera(direction: number) {
    setCameraIndex(
      (current) =>
        (current + direction + cameraOptions.length) % cameraOptions.length,
    );
  }

  function nudgeProgress(amount: number) {
    setProgress((current) => Math.min(100, Math.max(0, current + amount)));
  }

  return (
    <div className="monitor-page">
      <section className="monitor-grid">
        <div className="video-workspace">
          <div className="video-toolbar">
            <strong>
              {selectedCamera.view} <span>·</span> {selectedCamera.code}
            </strong>
            <div>
              <span>May 12, 2025</span>
              <span>23:00:00 – 05:00:00</span>
              <button type="button" aria-label="Select date">
                <CalendarDays size={15} />
              </button>
              <button type="button" aria-label="More camera actions">
                <MoreVertical size={16} />
              </button>
            </div>
          </div>

          <div
            className="camera-stage screenshot-camera"
            aria-label={`Recorded night footage from ${selectedCamera.view}`}
            data-camera={selectedCamera.id}
          />

          <div className="video-transport">
            <button
              type="button"
              onClick={() => setProgress(0)}
              aria-label="Go to shift start"
            >
              <SkipBack size={16} />
            </button>
            <button
              type="button"
              onClick={() => nudgeProgress(-2)}
              aria-label="Previous chapter"
            >
              <ChevronLeft size={17} />
            </button>
            <button
              type="button"
              className="transport-play"
              onClick={() => setPlaying((current) => !current)}
              aria-label={playing ? "Pause recording" : "Play recording"}
            >
              {playing ? <Pause size={18} /> : <Play size={18} />}
            </button>
            <button
              type="button"
              onClick={() => nudgeProgress(2)}
              aria-label="Next chapter"
            >
              <ChevronRight size={17} />
            </button>
            <button
              type="button"
              onClick={() => setProgress(100)}
              aria-label="Go to shift end"
            >
              <SkipForward size={16} />
            </button>
            <span className="transport-divider" />
            <button type="button" className="transport-speed">
              1x <ChevronDown size={13} />
            </button>
            <span className="live-badge">LIVE</span>
            <span className="transport-time">
              {formatShiftTime(progress)} <i>/</i> 05:00:00
            </span>
            <span className="transport-spacer" />
            <button type="button" aria-label="Capture still frame">
              <Camera size={16} />
            </button>
            <button type="button" aria-label="Bookmark current time">
              <Bookmark size={16} />
            </button>
            <button type="button" aria-label="Open fullscreen">
              <Maximize size={16} />
            </button>
          </div>

          <Timeline progress={progress} onChange={setProgress} />
        </div>

        <aside className="evidence-column">
          <section className="evidence-panel">
            <div className="panel-title">
              <strong>Evidence details</strong>
              <button type="button" aria-label="Close evidence details">×</button>
            </div>
            <div className="evidence-record-heading">
              <span>
                <i className="blue-dot" />
                <strong>Evidence</strong>
                <time>{formatShiftTime(progress)}</time>
              </span>
              <div>
                <Bookmark size={15} />
                <MoreVertical size={15} />
              </div>
            </div>
            <dl className="evidence-definition-list">
              <div>
                <dt>Camera</dt>
                <dd>{selectedCamera.view} ({selectedCamera.code})</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>May 12, 2025&nbsp; {formatShiftTime(progress)}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd>00:00:18</dd>
              </div>
              <div>
                <dt>Tracks</dt>
                <dd>2</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>Medium</dd>
              </div>
              <div>
                <dt>Zone</dt>
                <dd>Watering Hole</dd>
              </div>
              <div>
                <dt>Rule</dt>
                <dd>pacing &gt; 10 min</dd>
              </div>
            </dl>

            <div className="track-list">
              <strong>Tracks (2)</strong>
              {["Track 1", "Track 2"].map((track, index) => (
                <label key={track}>
                  <input
                    type="checkbox"
                    checked={trackVisibility[index]}
                    onChange={() =>
                      setTrackVisibility((current) =>
                        current.map((value, itemIndex) =>
                          itemIndex === index ? !value : value,
                        ),
                      )
                    }
                  />
                  <i className={index === 0 ? "white-track" : "blue-track"} />
                  <span>
                    {track}
                    <small>Medium confidence</small>
                  </span>
                </label>
              ))}
            </div>

            <div className="evidence-actions">
              <button type="button">
                Export clip
                <ChevronDown size={14} />
              </button>
              <button type="button">
                <Share2 size={14} />
                Share
              </button>
            </div>
            <p className="evidence-safety">
              <Check size={12} />
              Evidence only · human verification required
            </p>
          </section>

          <section className="preview-panel">
            <div className="panel-title">
              <strong>Scrubber preview</strong>
              <button type="button" aria-label="Close scrubber preview">×</button>
            </div>
            <div className="preview-stage-row">
              <button
                type="button"
                aria-label="Previous evidence frame"
                onClick={() => nudgeProgress(-1)}
              >
                <ChevronLeft size={23} />
              </button>
              <div className="scrubber-preview-image" aria-hidden="true" />
              <button
                type="button"
                aria-label="Next evidence frame"
                onClick={() => nudgeProgress(1)}
              >
                <ChevronRight size={23} />
              </button>
            </div>
            <time>{formatShiftTime(progress)}</time>
          </section>
        </aside>
      </section>

      <section className="camera-gallery" aria-label="Camera selection">
        <button
          type="button"
          className="gallery-edge gallery-edge-previous"
          onClick={() => changeCamera(-1)}
          aria-label="Previous camera"
        >
          <ChevronLeft size={24} />
        </button>
        <div
          className="camera-carousel-viewport"
          ref={galleryRef}
          role="radiogroup"
          aria-label="Recorded camera sources"
        >
          <div className="camera-carousel-track">
            {cameraOptions.map((option, index) => {
              const active = index === cameraIndex;
              return (
                <motion.button
                  type="button"
                  role="radio"
                  aria-checked={active}
                  className="camera-gallery-card"
                  data-camera-index={index}
                  data-active={active}
                  onClick={() => setCameraIndex(index)}
                  whileTap={reduceMotion ? undefined : { scale: 0.985 }}
                  key={option.id}
                >
                  <span className="camera-card-heading">
                    <span>
                      <strong>{option.code}</strong>
                      <small>{option.view}</small>
                    </span>
                    <em>
                      <i className="blue-dot" />
                      REC
                    </em>
                  </span>
                  <span
                    className="camera-card-image"
                    style={
                      {
                        "--camera-position": option.position,
                      } as CSSProperties
                    }
                  />
                  <span className="camera-card-menu">
                    <MoreVertical size={16} />
                  </span>
                </motion.button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          className="gallery-edge gallery-edge-next"
          onClick={() => changeCamera(1)}
          aria-label="Next camera"
        >
          <ChevronRight size={24} />
        </button>
      </section>

      <button
        type="button"
        className="monitor-graph-shortcut"
        onClick={() => window.location.assign("/graph")}
      >
        Open connected graph <ExternalLink size={13} />
      </button>
    </div>
  );
}
