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
import { useEffect, useMemo, useState } from "react";
import {
  api,
  type DashboardEvent,
  type DashboardPayload,
} from "../lib/api";

type ReviewEvent = {
  id: string;
  time: string;
  title: string;
  meta: string;
  type: "camera" | "rule" | "human";
  eventId: string;
  source: string;
  event: DashboardEvent;
};

function TimelineIcon({ type }: { type: ReviewEvent["type"] }) {
  if (type === "human") return <UserRound size={13} />;
  if (type === "rule") return <ShieldCheck size={13} />;
  return <Video size={13} />;
}

export function AnalysisWorkspace() {
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [briefingReady, setBriefingReady] = useState(false);
  const [outcomeRecorded, setOutcomeRecorded] = useState(false);
  const reviewEvents = useMemo<ReviewEvent[]>(
    () =>
      (dashboard?.events ?? []).map((event) => ({
        id: event.event_id,
        time: new Date(event.start_ts).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        title: `${event.behavior.replaceAll("_", " ")} · ${event.severity}`,
        meta: "Deterministic rule event",
        type: event.ack_state === "acknowledged" ? "human" : "rule",
        eventId: event.event_id,
        source: `${event.enclosure_id} · ${event.rule_fired}`,
        event,
      })),
    [dashboard],
  );
  const selected = useMemo(
    () => reviewEvents.find((event) => event.id === selectedId) ?? reviewEvents[0],
    [reviewEvents, selectedId],
  );
  const metrics = [
    {
      label: "Coverage",
      value: dashboard?.data_gaps.length ? "Reduced" : "Complete",
      detail: "Recorded backend coverage",
      icon: Target,
    },
    {
      label: "Animals",
      value: String(dashboard?.animals.length ?? 0),
      detail: "Monitored",
      icon: PawPrint,
    },
    {
      label: "Review items",
      value: String(dashboard?.events.length ?? 0),
      detail: "Deterministic events",
      icon: List,
    },
    {
      label: "Data gaps",
      value: String(dashboard?.data_gaps.length ?? 0),
      detail: "Recorded",
      icon: CircleAlert,
    },
  ] as const;
  const comparisonRows = (dashboard?.events ?? []).slice(0, 3).map((event) => {
    const duration =
      Math.max(0, Date.parse(event.end_ts) - Date.parse(event.start_ts)) / 60_000;
    return {
      label: event.behavior.replaceAll("_", " "),
      tonight: Math.min(100, Math.max(4, duration * 3)),
      tonightValue: `${duration.toFixed(1)} min`,
    };
  });

  useEffect(() => {
    api
      .dashboard()
      .then(setDashboard)
      .catch((caught: unknown) =>
        setLoadError(caught instanceof Error ? caught.message : "Unable to load analysis"),
      );
  }, []);

  if (loadError) {
    return (
      <div className="graph-loading" role="alert">
        <p>{loadError}</p>
      </div>
    );
  }
  if (!dashboard) {
    return (
      <div className="graph-loading" role="status">
        <span />
        <p>Loading evidence analysis from the backend…</p>
      </div>
    );
  }
  if (!selected) {
    return (
      <div className="graph-loading" role="status">
        <p>No deterministic events are available for review yet.</p>
      </div>
    );
  }

  return (
    <div className="review-analysis-page">
      <div className="review-toolbar">
        <button type="button" className="review-filter">
          <span>All connected enclosures</span>
          <ChevronDown size={14} />
        </button>
        <button type="button" className="review-filter">
          <span>All monitored animals</span>
          <ChevronDown size={14} />
        </button>
        <button type="button" className="review-filter review-date-filter">
          <CalendarDays size={14} />
          <span>Current recorded shift</span>
        </button>
        <button
          type="button"
          className="primary-button review-briefing-button"
          onClick={() => {
            api.morningReport().then(() => setBriefingReady(true));
          }}
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
                  Baseline unavailable in this endpoint
                </span>
              </div>
            </header>
            <div
              className="review-comparison-chart"
              role="img"
              aria-label="Durations of deterministic events recorded by the backend"
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
                  </div>
                </div>
              ))}
              <p>
                Severity and rule provenance come from deterministic backend
                records. This view does not infer missing baseline values.
              </p>
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
              {dashboard.animals.map((animal) => {
                const event = dashboard.events.find(
                  (item) => item.animal_id === animal.animal_id,
                );
                return (
                  <div className="review-animal-row" role="row" key={animal.animal_id}>
                    <span role="cell">{animal.name.slice(0, 1)}</span>
                    <span role="cell">
                      {event ? event.behavior.replaceAll("_", " ") : "No notable events"}
                    </span>
                    <span role="cell">
                      {animal.baseline_state} · {animal.baseline_days} days
                    </span>
                    <span role="cell">{event?.ack_state ?? "No event"}</span>
                    <span role="cell">
                      {dashboard.data_gaps.some(
                        (gap) => gap.enclosure_id === animal.enclosure_id,
                      )
                        ? "Reduced"
                        : "Complete"}
                    </span>
                  </div>
                );
              })}
            </div>
            <footer className="review-table-footer">
              <button type="button">
                Export summary
                <ExternalLink size={12} />
              </button>
              <span>{dashboard.animals.length} animals</span>
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

            <div className="review-camera-preview" aria-label="Source evidence preview">
              <span>
                {selected.event.enclosure_id} · {selected.time}
              </span>
              {selected.event.media_url ? (
                <video
                  src={selected.event.media_url}
                  muted
                  playsInline
                  preload="metadata"
                  controls
                />
              ) : (
                <div className="review-preview-landscape" />
              )}
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
                <dd>{selected.event.animal_name}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{selected.event.confidence.toFixed(2)}</dd>
              </div>
              <div>
                <dt>Review</dt>
                <dd>
                  {selected.event.ack_state ?? "pending"}
                  {selected.event.acknowledged_by
                    ? ` · ${selected.event.acknowledged_by}`
                    : ""}
                </dd>
              </div>
            </dl>

            <section className="review-rule-block">
              <ShieldCheck size={15} />
              <div>
                <span>Deterministic rule provenance</span>
                <strong>{selected.event.rule_fired}</strong>
                <small>{selected.event.rule_version} · fixed rule logic</small>
              </div>
              <ExternalLink size={12} />
            </section>

            <div className="review-selected-actions">
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  if (selected.event.media_url) {
                    window.location.assign(selected.event.media_url);
                  }
                }}
              >
                <Play size={13} />
                Review clip
                <ExternalLink size={11} />
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => {
                  api
                    .recordOutcome(selected.event.event_id, "continued_observation")
                    .then(() => setOutcomeRecorded(true));
                }}
              >
                <Pencil size={13} />
                {outcomeRecorded ? "Outcome recorded" : "Record outcome"}
              </button>
            </div>
          </article>

          <article className="review-panel review-status-panel">
            <header>
              <CheckCircle2 size={15} />
              <strong>
                Review status · {selected.event.ack_state ?? selected.event.review_state}
              </strong>
            </header>
            <dl>
              <div>
                <dt>Reviewer</dt>
                <dd>{selected.event.acknowledged_by ?? "Not acknowledged"}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>
                  {selected.event.acknowledged_at
                    ? new Date(selected.event.acknowledged_at).toLocaleString()
                    : "Not recorded"}
                </dd>
              </div>
              <div>
                <dt>Outcome</dt>
                <dd>{outcomeRecorded ? "continued observation" : "Not recorded here"}</dd>
              </div>
              <div>
                <dt>Notes</dt>
                <dd>Human outcome records remain backend owned.</dd>
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
