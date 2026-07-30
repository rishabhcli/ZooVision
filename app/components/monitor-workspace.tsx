"use client";

import {
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  ExternalLink,
  Eye,
  Grid3X3,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  ScanLine,
  SkipBack,
  SkipForward,
  Video,
  ZoomIn,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import {
  CSSProperties,
  KeyboardEvent,
  PointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const cameraOptions = [
  {
    id: "enc-07-cam-1",
    label: "Camera 1",
    enclosure: "ENC-07",
    view: "West habitat",
    variant: "west",
  },
  {
    id: "enc-07-cam-2",
    label: "Camera 2",
    enclosure: "ENC-07",
    view: "North habitat",
    variant: "north",
  },
  {
    id: "enc-07-cam-3",
    label: "Camera 3",
    enclosure: "ENC-07",
    view: "Shelter entrance",
    variant: "ledge",
  },
  {
    id: "enc-07-cam-4",
    label: "Camera 4",
    enclosure: "ENC-07",
    view: "Water station",
    variant: "pool",
  },
];

const scrubberTicks = Array.from({ length: 19 }, (_, index) => index);

const chapterCopy = [
  {
    title: "Coverage begins",
    description: "Recorded segment starts with complete camera coverage.",
  },
  {
    title: "Track 14 identified",
    description: "Identity linked to Rex with 0.86 confidence.",
  },
  {
    title: "Pacing sustained",
    description: "Continuous movement remains visible through the segment.",
  },
  {
    title: "Rule threshold crossed",
    description: "Deterministic pacing > 10 min rule is preserved.",
  },
];

function formatTime(progress: number) {
  const totalSeconds = Math.round(15 * 60 * (progress / 100));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `02:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(
    2,
    "0",
  )}`;
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
  const focusedChapter =
    chapterCopy[
      Math.min(
        chapterCopy.length - 1,
        Math.floor((focusTick / scrubberTicks.length) * chapterCopy.length),
      )
    ];

  function tickFromPointer(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(
      1,
      Math.max(0, (event.clientY - bounds.top) / bounds.height),
    );
    return Math.round(ratio * (scrubberTicks.length - 1));
  }

  function commitTick(index: number) {
    onChange((index / (scrubberTicks.length - 1)) * 100);
  }

  function handleKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    let next = activeTick;
    if (event.key === "ArrowUp") next = Math.max(0, activeTick - 1);
    else if (event.key === "ArrowDown")
      next = Math.min(scrubberTicks.length - 1, activeTick + 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = scrubberTicks.length - 1;
    else return;

    event.preventDefault();
    commitTick(next);
  }

  return (
    <div className="chapter-scrubber-panel">
      <div
        className="chapter-scrubber"
        role="slider"
        tabIndex={0}
        aria-label="Recorded segment position"
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
          const width =
            distance === 0 ? 42 : distance === 1 ? 32 : distance === 2 ? 22 : 12;
          const isElapsed = tick <= activeTick;

          return (
            <motion.i
              key={tick}
              className={isElapsed ? "elapsed" : undefined}
              animate={{ width }}
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { type: "spring", stiffness: 420, damping: 30 }
              }
            />
          );
        })}
        <span
          className="scrubber-position"
          style={{ top: `${progress}%` }}
          aria-hidden="true"
        />
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={focusedChapter.title}
          className="chapter-preview-card"
          initial={reduceMotion ? false : { opacity: 0, x: 6 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, x: -4 }}
        >
          <small>
            {formatTime((focusTick / (scrubberTicks.length - 1)) * 100)}
          </small>
          <strong>{focusedChapter.title}</strong>
          <p>{focusedChapter.description}</p>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

export function MonitorWorkspace() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(45);
  const [cameraIndex, setCameraIndex] = useState(1);
  const [selectedTrack, setSelectedTrack] = useState<"rex" | "zuri">("rex");
  const [outcomeSaved, setOutcomeSaved] = useState(false);
  const galleryRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 100) {
          setPlaying(false);
          return 0;
        }
        return current + 0.35;
      });
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing]);

  const selectedAnimal = useMemo(
    () =>
      selectedTrack === "rex"
        ? {
            name: "Rex",
            track: "Track 14",
            behavior: "Pacing",
            status: "Review",
            confidence: "0.86 identity confidence",
          }
        : {
            name: "Zuri",
            track: "Track 21",
            behavior: "Resting",
            status: "Within baseline",
            confidence: "0.94 identity confidence",
          },
    [selectedTrack],
  );
  const selectedCamera = cameraOptions[cameraIndex];

  function changeCamera(direction: number) {
    setCameraIndex(
      (current) =>
        (current + direction + cameraOptions.length) % cameraOptions.length,
    );
  }

  useEffect(() => {
    const viewport = galleryRef.current;
    const card = viewport?.querySelector<HTMLElement>(
      `[data-camera-index="${cameraIndex}"]`,
    );
    if (!viewport || !card) return;
    viewport.scrollTo({
      left: Math.max(0, card.offsetLeft - 2),
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [cameraIndex, reduceMotion]);

  return (
    <div className="page-stack monitor-page">
      <div className="monitor-context-bar">
        <div className="active-source-readout">
          <span className="active-source-icon">
            <Camera size={15} />
          </span>
          <span>
            <small>Recorded source</small>
            <strong>
              {selectedCamera.enclosure} · {selectedCamera.label}
            </strong>
          </span>
        </div>
        <div className="segment-stepper" aria-label="Recorded segment">
          <button type="button" aria-label="Previous segment">
            <ChevronLeft size={15} />
          </button>
          <span>
            <small>July 30</small>
            <strong>02:00–02:15</strong>
          </span>
          <button type="button" aria-label="Next segment">
            <ChevronRight size={15} />
          </button>
        </div>
        <div className="coverage-readout">
          <span className="status-dot" />
          <span>Coverage complete</span>
          <strong>15:00</strong>
        </div>
      </div>

      <section className="monitor-grid">
        <div className="video-workspace">
          <div className="video-toolbar">
            <div>
              <span className="section-kicker">Recorded camera segment</span>
              <h1>{selectedCamera.view}</h1>
            </div>
            <div className="video-toolbar-meta">
              <span>
                <Camera size={14} />
                {selectedCamera.enclosure} · {selectedCamera.label}
              </span>
              <span>
                <Clock3 size={14} />
                02:00 start
              </span>
            </div>
          </div>

          <div
            className="camera-stage"
            data-camera={selectedCamera.variant}
            aria-label={`Recorded footage from ${selectedCamera.label}`}
          >
            <div className="camera-noise" aria-hidden="true" />
            <div className="camera-landscape" aria-hidden="true">
              <span className="tree-trunk one" />
              <span className="tree-trunk two" />
              <span className="ground-rock rock-one" />
              <span className="ground-rock rock-two" />
            </div>
            <button
              type="button"
              className={`track-box rex ${
                selectedTrack === "rex" ? "selected" : ""
              }`}
              onClick={() => setSelectedTrack("rex")}
              aria-label="Select Rex track"
            >
              <span className="track-label">Track 14 · moving</span>
              <span className="track-target-code">T14</span>
              <span className="track-vector" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </button>
            <button
              type="button"
              className={`track-box zuri ${
                selectedTrack === "zuri" ? "selected" : ""
              }`}
              onClick={() => setSelectedTrack("zuri")}
              aria-label="Select Zuri track"
            >
              <span className="track-label">Track 21 · resting</span>
              <span className="track-target-code">T21</span>
              <span className="track-vector" aria-hidden="true">
                <i />
                <i />
              </span>
            </button>
            <motion.span
              key={selectedCamera.id}
              className="camera-id"
              initial={reduceMotion ? false : { opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {selectedCamera.enclosure} / {selectedCamera.label.toUpperCase()}
            </motion.span>
            <span className="camera-state">
              <Check size={13} />
              Analysis complete
            </span>
            <span className="camera-timecode">{formatTime(progress)}</span>
          </div>

          <div
            className="timeline-editor"
            style={
              {
                "--timeline-progress": progress / 100,
              } as CSSProperties
            }
          >
            <div className="timeline-head">
              <div>
                <span>Observed activity</span>
                <small>Source-aligned · 15 minute segment</small>
              </div>
              <div className="timeline-transport">
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Jump to segment start"
                  onClick={() => setProgress(0)}
                >
                  <SkipBack size={14} />
                </button>
                <button
                  type="button"
                  className="playback-button"
                  onClick={() => setPlaying((current) => !current)}
                  aria-label={playing ? "Pause segment" : "Play segment"}
                >
                  {playing ? <Pause size={16} /> : <Play size={16} />}
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Jump to segment end"
                  onClick={() => setProgress(100)}
                >
                  <SkipForward size={14} />
                </button>
                <span className="playback-time">
                  {formatTime(progress)} / 02:15:00
                </span>
                <input
                  className="video-scrubber"
                  type="range"
                  min="0"
                  max="100"
                  step="0.1"
                  value={progress}
                  onChange={(event) => setProgress(Number(event.target.value))}
                  aria-label="Segment timeline"
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Toggle timeline grid"
                >
                  <Grid3X3 size={14} />
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Zoom timeline"
                >
                  <ZoomIn size={14} />
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Restart segment"
                  onClick={() => setProgress(0)}
                >
                  <RotateCcw size={14} />
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Fullscreen"
                >
                  <Maximize2 size={15} />
                </button>
              </div>
            </div>
            <div className="timeline-editor-layout">
              <div className="timeline-track-workspace">
                <div className="timeline-ruler">
                  <span />
                  {["02:00", "02:03", "02:06", "02:09", "02:12", "02:15"].map(
                    (time) => (
                      <time key={time}>{time}</time>
                    ),
                  )}
                </div>
                <div className="timeline-editor-body">
                  <div className="timeline-editor-row">
                    <span className="timeline-row-label">
                      <strong>Behavior</strong>
                      <small>Track 14</small>
                    </span>
                    <div className="timeline-editor-track">
                      <button
                        type="button"
                        className="timeline-clip pacing"
                        style={{ left: "2%", width: "89%" }}
                        onClick={() => setSelectedTrack("rex")}
                      >
                        <span>Pacing</span>
                        <small>14 min · confidence 0.91</small>
                      </button>
                    </div>
                  </div>
                  <div className="timeline-editor-row">
                    <span className="timeline-row-label">
                      <strong>Context</strong>
                      <small>Object region</small>
                    </span>
                    <div className="timeline-editor-track">
                      <span
                        className="timeline-clip context"
                        style={{ left: "19%", width: "27%" }}
                      >
                        <span>Water station</span>
                        <small>in frame</small>
                      </span>
                    </div>
                  </div>
                  <div className="timeline-editor-row">
                    <span className="timeline-row-label">
                      <strong>Behavior</strong>
                      <small>Track 21</small>
                    </span>
                    <div className="timeline-editor-track">
                      <button
                        type="button"
                        className="timeline-clip resting"
                        style={{ left: "57%", width: "37%" }}
                        onClick={() => setSelectedTrack("zuri")}
                      >
                        <span>Resting</span>
                        <small>confidence 0.94</small>
                      </button>
                    </div>
                  </div>
                  <div className="timeline-editor-row frame-row">
                    <span className="timeline-row-label">
                      <strong>Frames</strong>
                      <small>3 minute intervals</small>
                    </span>
                    <div className="frame-strip" aria-hidden="true">
                      {Array.from({ length: 6 }).map((_, index) => (
                        <i key={index}>
                          <ScanLine size={13} />
                          <span />
                        </i>
                      ))}
                    </div>
                  </div>
                  <span
                    className="timeline-editor-playhead"
                    aria-hidden="true"
                  />
                </div>
              </div>
              <ChapterScrubber progress={progress} onChange={setProgress} />
            </div>
          </div>
        </div>

        <aside className="evidence-drawer">
          <div className="drawer-heading">
            <div>
              <span className="section-kicker">Selected track</span>
              <h2>{selectedAnimal.name}</h2>
              <small>{selectedAnimal.track}</small>
            </div>
            <span
              className={`plain-status ${
                selectedTrack === "rex" ? "review" : "normal"
              }`}
            >
              {selectedAnimal.status}
            </span>
          </div>
          <dl className="evidence-definition-list">
            <div>
              <dt>Observed behavior</dt>
              <dd>{selectedAnimal.behavior}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>
                {selectedCamera.enclosure} {selectedCamera.label}
              </dd>
            </div>
            <div>
              <dt>Identity</dt>
              <dd>{selectedAnimal.confidence}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>02:00–02:14</dd>
            </div>
          </dl>

          {selectedTrack === "rex" && (
            <>
              <div className="drawer-rule">
                <div className="rule-icon">
                  <CircleAlert size={17} />
                </div>
                <div>
                  <span>Deterministic rule</span>
                  <strong>pacing &gt; 10 min</strong>
                  <small>Severity: MODERATE</small>
                </div>
              </div>
              <div className="drawer-note">
                <Eye size={16} />
                <p>
                  Verify the identity and source clip before recording a
                  welfare check.
                </p>
              </div>
            </>
          )}

          <div className="drawer-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() => router.push("/graph")}
            >
              Open connected graph
              <ExternalLink size={15} />
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setOutcomeSaved(true)}
            >
              {outcomeSaved ? <Check size={15} /> : <Video size={15} />}
              {outcomeSaved ? "Outcome noted locally" : "Record outcome"}
            </button>
          </div>
        </aside>
      </section>

      <section className="camera-gallery" aria-labelledby="camera-gallery-title">
        <div className="camera-gallery-heading">
          <div>
            <span className="section-kicker">Recorded sources</span>
            <h2 id="camera-gallery-title">Choose camera view</h2>
          </div>
          <div className="gallery-nav" aria-label="Camera navigation">
            <span>
              {String(cameraIndex + 1).padStart(2, "0")} /{" "}
              {String(cameraOptions.length).padStart(2, "0")}
            </span>
            <button
              type="button"
              onClick={() => changeCamera(-1)}
              aria-label="Previous camera"
            >
              <ChevronLeft size={17} />
            </button>
            <button
              type="button"
              onClick={() => changeCamera(1)}
              aria-label="Next camera"
            >
              <ChevronRight size={17} />
            </button>
          </div>
        </div>

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
                  layout
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  className="camera-gallery-card"
                  data-camera={option.variant}
                  data-camera-index={index}
                  data-active={active}
                  onClick={() => setCameraIndex(index)}
                  whileTap={reduceMotion ? undefined : { scale: 0.985 }}
                >
                  <span className="camera-gallery-card-grid" aria-hidden="true" />
                  <span className="camera-gallery-card-index">
                    CAM {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="camera-gallery-card-copy">
                    <small>{option.enclosure}</small>
                    <strong>{option.view}</strong>
                    <span>{option.label} · recorded segment</span>
                    <em>
                      {active ? "Viewing now" : "Open camera"}{" "}
                      <ChevronRight size={14} />
                    </em>
                  </span>
                </motion.button>
              );
            })}
          </div>
        </div>
        <div className="gallery-pagination" aria-hidden="true">
          {cameraOptions.map((option, index) => (
            <i className={index === cameraIndex ? "active" : ""} key={option.id} />
          ))}
        </div>
      </section>
    </div>
  );
}
