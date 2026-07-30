"use client";

import {
  Camera,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Dog,
  ExternalLink,
  Eye,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Video,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const cameraOptions = [
  "ENC-07 · Camera 1",
  "ENC-07 · Camera 2",
  "ENC-03 · Camera 1",
  "ENC-05 · Camera 1",
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

export function MonitorWorkspace() {
  const router = useRouter();
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(45);
  const [camera, setCamera] = useState(cameraOptions[1]);
  const [selectedTrack, setSelectedTrack] = useState<"rex" | "zuri">("rex");
  const [outcomeSaved, setOutcomeSaved] = useState(false);

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
            behavior: "Pacing",
            status: "Review",
            confidence: "0.86 identity confidence",
          }
        : {
            name: "Zuri",
            behavior: "Resting",
            status: "Within baseline",
            confidence: "0.94 identity confidence",
          },
    [selectedTrack],
  );

  return (
    <div className="page-stack monitor-page">
      <div className="control-row">
        <label className="select-control">
          <span>Camera</span>
          <select
            value={camera}
            onChange={(event) => setCamera(event.target.value)}
          >
            {cameraOptions.map((option) => (
              <option value={option} key={option}>
                {option}
              </option>
            ))}
          </select>
          <ChevronDown size={14} />
        </label>
        <label className="select-control">
          <span>Segment</span>
          <select defaultValue="02:00–02:15">
            <option>01:45–02:00</option>
            <option>02:00–02:15</option>
            <option>02:15–02:30</option>
          </select>
          <ChevronDown size={14} />
        </label>
        <div className="coverage-readout">
          <span className="status-dot" />
          <span>Coverage complete</span>
          <strong>15:00</strong>
        </div>
        <button className="quiet-button" type="button">
          <SlidersHorizontal size={15} />
          Overlay settings
        </button>
      </div>

      <section className="monitor-grid">
        <div className="video-workspace">
          <div className="video-toolbar">
            <div>
              <span className="section-kicker">Recorded camera segment</span>
              <h1>ENC-07 · North habitat</h1>
            </div>
            <div className="video-toolbar-meta">
              <span>
                <Camera size={14} />
                Camera 2
              </span>
              <span>
                <Clock3 size={14} />
                July 30 · 02:00
              </span>
            </div>
          </div>

          <div className="camera-stage" aria-label="Recorded enclosure footage">
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
              <span className="track-label">Rex · moving</span>
              <Dog className="animal-shape rex-shape" strokeWidth={1.15} />
            </button>
            <button
              type="button"
              className={`track-box zuri ${
                selectedTrack === "zuri" ? "selected" : ""
              }`}
              onClick={() => setSelectedTrack("zuri")}
              aria-label="Select Zuri track"
            >
              <span className="track-label">Zuri · resting</span>
              <Dog className="animal-shape zuri-shape" strokeWidth={1.15} />
            </button>
            <span className="camera-id">ENC-07 CAM 2</span>
            <span className="camera-state">
              <Check size={13} />
              Analysis complete
            </span>
            <span className="camera-timecode">{formatTime(progress)}</span>
          </div>

          <div className="playback-controls">
            <button
              type="button"
              className="playback-button"
              onClick={() => setPlaying((current) => !current)}
              aria-label={playing ? "Pause segment" : "Play segment"}
            >
              {playing ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Restart segment"
              onClick={() => setProgress(0)}
            >
              <RotateCcw size={15} />
            </button>
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
            <span className="playback-time">{formatTime(progress)} / 02:15:00</span>
            <button
              type="button"
              className="icon-button"
              aria-label="Fullscreen"
            >
              <Maximize2 size={16} />
            </button>
          </div>

          <div className="observation-timeline">
            <div className="timeline-head">
              <span>Observed activity</span>
              <small>Source-aligned timestamps</small>
            </div>
            <div className="timeline-lanes">
              <span className="lane-name">Pacing · Rex</span>
              <div className="timeline-track">
                <span
                  className="timeline-block pacing"
                  style={{ left: "3%", width: "88%" }}
                >
                  02:00–02:14
                </span>
              </div>
              <span className="lane-name">Water bowl</span>
              <div className="timeline-track">
                <span
                  className="timeline-block neutral"
                  style={{ left: "20%", width: "23%" }}
                >
                  in frame
                </span>
              </div>
              <span className="lane-name">Resting · Zuri</span>
              <div className="timeline-track">
                <span
                  className="timeline-block resting"
                  style={{ left: "58%", width: "35%" }}
                >
                  observed
                </span>
              </div>
              <span
                className="timeline-playhead"
                style={{ left: `calc(116px + (100% - 116px) * ${progress / 100})` }}
              />
            </div>
            <div className="filmstrip" aria-hidden="true">
              {Array.from({ length: 10 }).map((_, index) => (
                <span key={index}>
                  <Dog size={18} />
                </span>
              ))}
            </div>
          </div>
        </div>

        <aside className="evidence-drawer">
          <div className="drawer-heading">
            <div>
              <span className="section-kicker">Selected track</span>
              <h2>{selectedAnimal.name}</h2>
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
              <dd>ENC-07 Camera 2</dd>
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
                  Verify the animal identity and source clip before a welfare
                  check.
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
    </div>
  );
}
