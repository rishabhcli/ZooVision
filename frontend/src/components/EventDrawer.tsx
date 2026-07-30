import { Bell, Camera, Check, ClipboardCheck, ScanLine, X } from "lucide-react";
import { useState } from "react";

import { SEVERITY_COLOR } from "../severity";
import type { EventDetail } from "../types";

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatDuration(start: string, end: string) {
  const minutes = Math.round(
    (new Date(end).getTime() - new Date(start).getTime()) / 60000
  );
  return `${minutes}m`;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export function EventDrawer({
  event,
  busy,
  onClose,
  onAcknowledge,
  onOutcome
}: {
  event: EventDetail;
  busy: boolean;
  onClose: () => void;
  onAcknowledge: () => void;
  onOutcome: (resolution: string, note: string) => void;
}) {
  const [resolution, setResolution] = useState("welfare_check_completed");
  const [note, setNote] = useState("");
  const source = event.sources[0];
  const detections = event.detections ?? [];

  return (
    <div
      className="drawer-scrim"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <aside className="event-drawer" aria-label="Event evidence">
        <header>
          <div>
            <span
              className="severity"
              style={{ background: SEVERITY_COLOR[event.severity] }}
            >
              {event.severity}
            </span>
            <span className="drawer-id">{event.event_id.slice(-8)}</span>
          </div>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            <X size={19} />
          </button>
        </header>

        <div className="drawer-title">
          <span className="eyebrow">
            {event.enclosure_id} · {formatTime(event.start_ts)}
          </span>
          <h2>
            {event.animal_name} · {titleCase(event.behavior)}
          </h2>
          <p>{formatDuration(event.start_ts, event.end_ts)} continuous observation</p>
        </div>

        <div className="evidence-video">
          {source?.media_url ? (
            <video
              src={source.media_url}
              controls
              muted
              autoPlay
              playsInline
              onLoadedMetadata={(media) => {
                media.currentTarget.currentTime = source.source_offset_seconds;
              }}
            />
          ) : (
            <div className="camera-missing">
              <Camera size={24} />
            </div>
          )}
        </div>

        <section className="drawer-section">
          <div className="drawer-section-title">
            <ClipboardCheck size={17} />
            <h3>Deterministic decision</h3>
          </div>
          <div className="rule-line">
            <span className="mono">{event.rule_fired}</span>
            <small>{event.rule_version}</small>
          </div>
          <ul className="fact-list">
            {event.explanation_facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
          <div className="confidence-line">
            <span>Evidence confidence</span>
            <strong>{Math.round(event.confidence * 100)}%</strong>
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-section-title">
            <ScanLine size={17} />
            <h3>Spatial track</h3>
          </div>
          <p className="drawer-note">
            {detections.length} motion region(s) measured across{" "}
            {new Set(detections.map((d) => d.track_id)).size} track(s). Motion
            locates movement in the frame; it does not identify the species or the
            behavior.
          </p>
        </section>

        <section className="drawer-section">
          <div className="drawer-section-title">
            <Camera size={17} />
            <h3>Source provenance</h3>
          </div>
          {event.sources.map((item) => (
            <div className="source-row" key={item.observation_id}>
              <div>
                <strong>
                  {item.camera_id} · {formatTime(item.start_ts)}–
                  {formatTime(item.end_ts)}
                </strong>
                <span>{item.evidence}</span>
              </div>
              <small>
                {titleCase(item.evidence_kind)} · {item.provider_model}
              </small>
            </div>
          ))}
        </section>

        {event.ack_state === "pending" ? (
          <button className="primary-button" disabled={busy} onClick={onAcknowledge}>
            <Bell size={17} /> Acknowledge for review
          </button>
        ) : (
          <div className="acknowledged-band">
            <Check size={17} />
            <span>Acknowledged by {event.acknowledged_by}</span>
          </div>
        )}

        <section className="drawer-section outcome-form">
          <div className="drawer-section-title">
            <ClipboardCheck size={17} />
            <h3>Keeper outcome</h3>
          </div>
          <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
            <option value="welfare_check_completed">Welfare check completed</option>
            <option value="water_available">Water available</option>
            <option value="continued_observation">Continue observation</option>
            <option value="false_positive">False positive</option>
            <option value="camera_issue">Camera issue</option>
          </select>
          <textarea
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Factual shift note"
          />
          <button
            className="secondary-button"
            disabled={busy}
            onClick={() => onOutcome(resolution, note)}
          >
            <Check size={16} /> Record outcome
          </button>
        </section>

        {event.outcomes.map((outcome) => (
          <div className="outcome-record" key={outcome.outcome_id}>
            <strong>{titleCase(outcome.resolution)}</strong>
            <span>{outcome.note || "No note entered"}</span>
            <small>
              {outcome.entered_by} · {formatTime(outcome.created_at)}
            </small>
          </div>
        ))}
      </aside>
    </div>
  );
}

export default EventDrawer;
