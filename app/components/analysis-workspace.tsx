"use client";

import {
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ExternalLink,
  FileText,
  List,
  MoreVertical,
  PawPrint,
  Pencil,
  Play,
  ShieldCheck,
  Sparkles,
  Target,
  UserRound,
  Video,
} from "lucide-react";
import { useMemo, useState } from "react";

type ReviewEvent = {
  id: string;
  time: string;
  title: string;
  meta: string;
  type: "camera" | "rule" | "human";
  eventId: string;
  source: string;
};

const reviewEvents: ReviewEvent[] = [
  {
    id: "baseline",
    time: "20:30",
    title: "Night shift baseline established",
    meta: "Camera evidence",
    type: "camera",
    eventId: "EVT-1831",
    source: "CAM 07",
  },
  {
    id: "pacing",
    time: "02:00",
    title: "Pacing started",
    meta: "Camera evidence",
    type: "camera",
    eventId: "EVT-1842",
    source: "CAM 07 · Savannah Overlook",
  },
  {
    id: "rule",
    time: "02:14",
    title: "Rule triggered",
    meta: "Deterministic rule",
    type: "rule",
    eventId: "RULE-10.1",
    source: "Rule set v1.3",
  },
  {
    id: "clip",
    time: "02:15",
    title: "Clip created",
    meta: "Camera evidence",
    type: "camera",
    eventId: "CLIP-1842",
    source: "CAM 07",
  },
  {
    id: "reviewed",
    time: "02:18",
    title: "Reviewed",
    meta: "Human review",
    type: "human",
    eventId: "NOTE-512",
    source: "Maria Chen",
  },
];

const metrics = [
  {
    label: "Coverage",
    value: "100%",
    detail: "Expected 23:00–05:00",
    icon: Target,
  },
  {
    label: "Animals",
    value: "2",
    detail: "Monitored",
    icon: PawPrint,
  },
  {
    label: "Review items",
    value: "1",
    detail: "Requires review",
    icon: List,
  },
  {
    label: "Data gaps",
    value: "0",
    detail: "Detected",
    icon: CircleAlert,
  },
] as const;

const comparisonRows = [
  { label: "Pacing", tonight: 72, baseline: 18, tonightValue: "14.0 min", baselineValue: "2.0 min" },
  { label: "Resting", tonight: 92, baseline: 106, tonightValue: "30.0 min", baselineValue: "42.0 min" },
  { label: "Water contact", tonight: 9, baseline: 14, tonightValue: "1.0", baselineValue: "2.0" },
] as const;

function TimelineIcon({ type }: { type: ReviewEvent["type"] }) {
  if (type === "human") return <UserRound size={13} />;
  if (type === "rule") return <ShieldCheck size={13} />;
  return <Video size={13} />;
}

export function AnalysisWorkspace() {
  const [selectedId, setSelectedId] = useState("pacing");
  const [briefingReady, setBriefingReady] = useState(false);
  const selected = useMemo(
    () =>
      reviewEvents.find((event) => event.id === selectedId) ?? reviewEvents[1],
    [selectedId],
  );

  return (
    <div className="review-analysis-page">
      <div className="review-toolbar">
        <button type="button" className="review-filter">
          <span>ENC-07 · Painted dogs</span>
          <ChevronDown size={14} />
        </button>
        <button type="button" className="review-filter">
          <span>All monitored animals</span>
          <ChevronDown size={14} />
        </button>
        <button type="button" className="review-filter review-date-filter">
          <CalendarDays size={14} />
          <span>May 12 · 23:00–05:00</span>
        </button>
        <button
          type="button"
          className="primary-button review-briefing-button"
          onClick={() => setBriefingReady(true)}
        >
          {briefingReady ? <Check size={14} /> : <FileText size={14} />}
          {briefingReady ? "Briefing prepared" : "Prepare morning briefing"}
        </button>
      </div>

      <header className="review-page-heading">
        <h1>Overnight evidence review</h1>
      </header>

      <section className="review-metrics" aria-label="Overnight summary">
        {metrics.map(({ label, value, detail, icon: Icon }) => (
          <article key={label}>
            <span className="review-metric-icon">
              <Icon size={18} />
            </span>
            <div>
              <small>{label}</small>
              <strong>{value}</strong>
              <span>{detail}</span>
            </div>
          </article>
        ))}
      </section>

      <section className="review-dashboard-grid">
        <article className="review-panel review-activity-panel">
          <header className="review-panel-header">
            <h2>Activity timeline</h2>
          </header>
          <div className="review-event-list">
            {reviewEvents.map((event) => (
              <button
                type="button"
                className={selectedId === event.id ? "selected" : undefined}
                onClick={() => setSelectedId(event.id)}
                aria-pressed={selectedId === event.id}
                key={event.id}
              >
                <time>{event.time}</time>
                <i className={`review-event-node ${event.type}`} />
                <span className="review-event-copy">
                  <strong>
                    <TimelineIcon type={event.type} />
                    {event.title}
                  </strong>
                  <small>{event.meta}</small>
                </span>
              </button>
            ))}
          </div>
          <button type="button" className="review-full-timeline">
            View full timeline
            <ExternalLink size={12} />
          </button>
        </article>

        <div className="review-center-column">
          <article className="review-panel review-chart-panel">
            <header className="review-panel-header">
              <h2>Behavior vs daytime baseline</h2>
              <div className="review-chart-legend">
                <span>
                  <i className="tonight" />
                  Tonight
                </span>
                <span>
                  <i className="baseline" />
                  Daytime baseline
                </span>
              </div>
            </header>
            <div
              className="review-comparison-chart"
              role="img"
              aria-label="Pacing was fourteen minutes tonight compared with a two-minute daytime baseline. Resting was thirty minutes compared with forty-two minutes. Water contact was one compared with two."
            >
              <div className="review-chart-axis">
                <span>0</span>
                <span>15</span>
                <span>30</span>
                <span>45</span>
                <span>60</span>
              </div>
              {comparisonRows.map((row) => (
                <div className="review-chart-row" key={row.label}>
                  <span>{row.label}</span>
                  <div>
                    <i
                      className="review-bar tonight"
                      style={{ width: `${row.tonight}%` }}
                    >
                      <b>{row.tonightValue}</b>
                    </i>
                    <i
                      className="review-bar baseline"
                      style={{ width: `${row.baseline}%` }}
                    >
                      <b>{row.baselineValue}</b>
                    </i>
                  </div>
                </div>
              ))}
              <p>Pacing was 3.1σ above Rex&apos;s daytime-only baseline.</p>
            </div>
          </article>

          <article className="review-panel review-animal-panel">
            <header className="review-panel-header">
              <h2>Animal summary</h2>
            </header>
            <div className="review-animal-table" role="table">
              <div className="review-animal-row head" role="row">
                <span role="columnheader">Animal</span>
                <span role="columnheader">Observed behavior</span>
                <span role="columnheader">Baseline</span>
                <span role="columnheader">Outcome</span>
                <span role="columnheader">Coverage</span>
              </div>
              <div className="review-animal-row" role="row">
                <span role="cell">R</span>
                <span role="cell">Pacing 14.0 min</span>
                <span role="cell">2.0 min</span>
                <span role="cell">Acknowledged</span>
                <span role="cell">100%</span>
              </div>
              <div className="review-animal-row" role="row">
                <span role="cell">Z</span>
                <span role="cell">Resting 31.0 min</span>
                <span role="cell">38.0 min</span>
                <span role="cell">No events</span>
                <span role="cell">100%</span>
              </div>
            </div>
            <footer className="review-table-footer">
              <button type="button">
                Export summary
                <ExternalLink size={12} />
              </button>
              <span>1–2 of 2</span>
              <button type="button" aria-label="Previous animals">
                <ChevronLeft size={13} />
              </button>
              <button type="button" aria-label="Next animals">
                <ChevronRight size={13} />
              </button>
            </footer>
          </article>
        </div>

        <aside className="review-right-column">
          <article className="review-panel review-selected-panel">
            <header className="review-panel-header">
              <h2>Selected evidence</h2>
              <button type="button" aria-label="More evidence actions">
                <MoreVertical size={14} />
              </button>
            </header>

            <div className="review-camera-preview" aria-label="CAM 07 evidence preview">
              <span>CAM 07 · 02:06:42</span>
              <i className="review-track-box one" />
              <i className="review-track-box two" />
              <i className="review-track-box three" />
              <div className="review-preview-landscape" />
            </div>

            <dl className="review-evidence-list">
              <div>
                <dt>Event ID</dt>
                <dd>{selected.eventId}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{selected.time}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{selected.source}</dd>
              </div>
              <div>
                <dt>Animal</dt>
                <dd>Rex</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>0.91</dd>
              </div>
              <div>
                <dt>Review</dt>
                <dd>02:18 · Maria Chen</dd>
              </div>
            </dl>

            <section className="review-rule-block">
              <ShieldCheck size={15} />
              <div>
                <span>Deterministic rule provenance</span>
                <strong>pacing &gt; 10 min</strong>
                <small>v1.3 · fixed rule logic</small>
              </div>
              <ExternalLink size={12} />
            </section>

            <div className="review-selected-actions">
              <button type="button" className="primary-button">
                <Play size={13} />
                Review clip
                <ExternalLink size={11} />
              </button>
              <button type="button" className="secondary-button">
                <Pencil size={13} />
                Record outcome
              </button>
            </div>
          </article>

          <article className="review-panel review-status-panel">
            <header>
              <CheckCircle2 size={15} />
              <strong>Review status · Acknowledged</strong>
            </header>
            <dl>
              <div>
                <dt>Reviewer</dt>
                <dd>Maria Chen</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>May 12, 2025 · 02:18:05</dd>
              </div>
              <div>
                <dt>Outcome</dt>
                <dd>Acknowledged</dd>
              </div>
              <div>
                <dt>Notes</dt>
                <dd>Animal monitored; no action required.</dd>
              </div>
            </dl>
          </article>
        </aside>
      </section>

      {briefingReady && (
        <div className="settings-save-toast" role="status">
          <Sparkles size={14} />
          Morning briefing preview prepared.
        </div>
      )}
    </div>
  );
}
