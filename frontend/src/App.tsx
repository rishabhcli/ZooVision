import {
  Activity,
  Bell,
  Camera,
  Check,
  ChevronRight,
  CircleGauge,
  ClipboardCheck,
  FileClock,
  HeartPulse,
  Moon,
  Radio,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type {
  Animal,
  Dashboard,
  EventDetail,
  MorningReport,
  Readiness,
  Severity
} from "./types";

type View = "monitor" | "report" | "system";

const NAV_ITEMS = [
  { id: "monitor" as const, label: "Shift monitor", icon: Activity },
  { id: "report" as const, label: "Morning brief", icon: FileClock },
  { id: "system" as const, label: "System", icon: CircleGauge }
];

const SEVERITY_ORDER: Record<Severity, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MODERATE: 2,
  LOW: 1,
  NONE: 0
};

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
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function SeverityBadge({ value }: { value: Severity }) {
  return <span className={`severity severity-${value.toLowerCase()}`}>{value}</span>;
}

function StatusDot({ online = true }: { online?: boolean }) {
  return <span className={`status-dot ${online ? "online" : "offline"}`} />;
}

function App() {
  const [view, setView] = useState<View>("monitor");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [report, setReport] = useState<MorningReport | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [selected, setSelected] = useState<EventDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedEventId = selected?.event_id;

  const load = useCallback(async () => {
    try {
      setError("");
      const [nextDashboard, nextReport, nextReadiness] = await Promise.all([
        api.dashboard(),
        api.report(),
        api.readiness()
      ]);
      setDashboard(nextDashboard);
      setReport(nextReport);
      setReadiness(nextReadiness);
      if (selectedEventId) {
        setSelected(await api.event(selectedEventId));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load ZooVision");
    }
  }, [selectedEventId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openEvent(eventId: string) {
    try {
      setSelected(await api.event(eventId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to open event");
    }
  }

  async function mutate(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <HeartPulse size={21} strokeWidth={2.2} />
          </span>
          <div>
            <strong>ZooVision</strong>
            <span>Keeper console</span>
          </div>
        </div>
        <nav aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={view === item.id ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => setView(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="shift-meta">
          <span className="eyebrow">Current watch</span>
          <strong>Overnight welfare</strong>
          <span>
            <Moon size={14} /> 19:00–06:00
          </span>
        </div>
        <div className="operator">
          <span className="avatar">AK</span>
          <div>
            <strong>Avery Kim</strong>
            <span>Night keeper</span>
          </div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="breadcrumb">Operations / {NAV_ITEMS.find((i) => i.id === view)?.label}</span>
            <h1>{NAV_ITEMS.find((i) => i.id === view)?.label}</h1>
          </div>
          <div className="topbar-actions">
            <span className="mode-pill">
              <StatusDot />
              Fixture feed
            </span>
            <span className="date-label">
              {new Intl.DateTimeFormat("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric"
              }).format(new Date())}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh"
              title="Refresh"
              onClick={() => void load()}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <TriangleAlert size={16} />
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {!dashboard || !report || !readiness ? (
          <div className="loading">
            <Radio size={22} />
            <span>Connecting to shift record…</span>
          </div>
        ) : (
          <>
            {view === "monitor" && (
              <MonitorView
                dashboard={dashboard}
                onOpen={(id) => void openEvent(id)}
                onBaseline={(animal) =>
                  void mutate(() => api.baseline(animal.animal_id, "active"))
                }
                busy={busy}
              />
            )}
            {view === "report" && (
              <ReportView report={report} onOpen={(id) => void openEvent(id)} />
            )}
            {view === "system" && (
              <SystemView
                readiness={readiness}
                onReset={() => void mutate(api.reset)}
                busy={busy}
              />
            )}
          </>
        )}
      </main>

      {selected && (
        <EventDrawer
          event={selected}
          busy={busy}
          onClose={() => setSelected(null)}
          onAcknowledge={() =>
            void mutate(() => api.acknowledge(selected.alert_id, "Avery Kim"))
          }
          onOutcome={(resolution, note) =>
            void mutate(() =>
              api.outcome(selected.event_id, resolution, note, "Avery Kim")
            )
          }
        />
      )}
    </div>
  );
}

function MonitorView({
  dashboard,
  onOpen,
  onBaseline,
  busy
}: {
  dashboard: Dashboard;
  onOpen: (id: string) => void;
  onBaseline: (animal: Animal) => void;
  busy: boolean;
}) {
  const highest = useMemo(
    () =>
      dashboard.events.reduce<Severity>(
        (current, event) =>
          SEVERITY_ORDER[event.severity] > SEVERITY_ORDER[current]
            ? event.severity
            : current,
        "NONE"
      ),
    [dashboard.events]
  );
  const pending = dashboard.events.filter((event) => event.ack_state === "pending").length;

  return (
    <div className="page-content">
      <div className="fixture-notice">
        <ShieldCheck size={18} />
        <div>
          <strong>Shadow evaluation</strong>
          <span>Synthetic observations · no staff pages sent</span>
        </div>
      </div>

      <section className="metric-row" aria-label="Shift summary">
        <Metric label="Animals monitored" value={String(dashboard.animals.length)} detail="3 cameras" />
        <Metric label="Highest signal" value={highest} detail="deterministic triage" tone={highest} />
        <Metric label="Awaiting review" value={String(pending)} detail="keeper console" />
        <Metric label="Coverage gaps" value={String(dashboard.data_gaps.length)} detail="18 minutes total" />
      </section>

      <div className="monitor-grid">
        <section className="work-section event-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Decision queue</span>
              <h2>Overnight events</h2>
            </div>
            <span className="count-label">{dashboard.events.length} signals</span>
          </div>
          <div className="event-table" role="table">
            <div className="table-row table-head" role="row">
              <span>Severity</span>
              <span>Animal</span>
              <span>Evidence</span>
              <span>Time</span>
              <span>Status</span>
              <span />
            </div>
            {dashboard.events.map((event) => (
              <button
                className="table-row event-row"
                role="row"
                key={event.event_id}
                onClick={() => onOpen(event.event_id)}
              >
                <span><SeverityBadge value={event.severity} /></span>
                <span className="animal-cell">
                  <strong>{event.animal_name}</strong>
                  <small>{event.enclosure_id}</small>
                </span>
                <span className="behavior-cell">
                  <strong>{titleCase(event.behavior)}</strong>
                  <small>{event.rule_fired}</small>
                </span>
                <span>
                  <strong>{formatTime(event.start_ts)}</strong>
                  <small>{formatDuration(event.start_ts, event.end_ts)}</small>
                </span>
                <span className={`ack-state ${event.ack_state}`}>
                  {event.ack_state === "pending" ? "Needs review" : "Acknowledged"}
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        </section>

        <section className="camera-stack">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Camera rail</span>
              <h2>Evidence feeds</h2>
            </div>
          </div>
          {dashboard.events.map((event) => (
            <button
              className="camera-feed"
              key={event.event_id}
              onClick={() => onOpen(event.event_id)}
            >
              {event.media_url ? (
                <video
                  src={event.media_url}
                  muted
                  autoPlay
                  loop
                  playsInline
                  preload="metadata"
                />
              ) : (
                <div className="camera-missing"><Camera size={22} /></div>
              )}
              <span className="feed-live"><StatusDot /> FIXTURE</span>
              <span className="feed-caption">
                <strong>{event.enclosure_id}</strong>
                <small>{event.animal_name} · {titleCase(event.behavior)}</small>
              </span>
            </button>
          ))}
        </section>
      </div>

      <section className="work-section animal-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Baseline registry</span>
            <h2>Monitored animals</h2>
          </div>
        </div>
        <div className="animal-grid">
          {dashboard.animals.map((animal) => (
            <article className="animal-item" key={animal.animal_id}>
              <span className="animal-monogram">{animal.name.slice(0, 1)}</span>
              <div className="animal-identity">
                <strong>{animal.name}</strong>
                <span>{animal.species}</span>
              </div>
              <div>
                <span className="field-label">Enclosure</span>
                <strong>{animal.enclosure_id}</strong>
              </div>
              <div>
                <span className="field-label">Day shifts</span>
                <strong>{animal.baseline_days}</strong>
              </div>
              <span className={`baseline-state ${animal.baseline_state}`}>
                {titleCase(animal.baseline_state)}
              </span>
              {animal.baseline_state === "shadow" ? (
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => onBaseline(animal)}
                >
                  <Check size={15} /> Activate
                </button>
              ) : (
                <span className="event-total">{animal.event_count} events</span>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
  tone
}: {
  label: string;
  value: string;
  detail: string;
  tone?: Severity;
}) {
  return (
    <div className={`metric ${tone ? `metric-${tone.toLowerCase()}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ReportView({
  report,
  onOpen
}: {
  report: MorningReport;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="page-content report-page">
      <div className="report-header">
        <div>
          <span className="eyebrow">Shift handoff</span>
          <h2>Morning welfare brief</h2>
          <p>{new Intl.DateTimeFormat("en-US", { dateStyle: "full" }).format(new Date())}</p>
        </div>
        <div className="report-stats">
          <span><strong>{report.summary.animals_monitored}</strong> animals</span>
          <span><strong>{report.summary.events}</strong> events</span>
          <span><strong>{report.summary.data_gaps}</strong> gap</span>
        </div>
      </div>
      <section className="report-list">
        {report.animals.map((animal) => (
          <article className="report-animal" key={animal.animal_id}>
            <div className="report-animal-head">
              <span className="animal-monogram">{animal.name.slice(0, 1)}</span>
              <div>
                <h3>{animal.name}</h3>
                <span>{animal.species} · {animal.enclosure_id}</span>
              </div>
              <span className={`baseline-state ${animal.baseline_state}`}>
                {titleCase(animal.baseline_state)}
              </span>
            </div>
            {animal.events.length ? (
              <div className="report-events">
                {animal.events.map((event) => (
                  <button key={event.event_id} onClick={() => onOpen(event.event_id)}>
                    <SeverityBadge value={event.severity} />
                    <span>
                      <strong>{titleCase(event.behavior)}</strong>
                      <small>{event.explanation_facts[0]}</small>
                    </span>
                    <ChevronRight size={17} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="quiet-night">
                <Check size={17} />
                <span>No notable deterministic events recorded</span>
              </div>
            )}
          </article>
        ))}
      </section>
      <section className="gap-band">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Coverage</span>
            <h2>Data gaps</h2>
          </div>
        </div>
        {report.data_gaps.map((gap) => (
          <div className="gap-row" key={gap.gap_id}>
            <TriangleAlert size={18} />
            <strong>{gap.enclosure_id}</strong>
            <span>{formatTime(gap.start_ts)}–{formatTime(gap.end_ts)}</span>
            <span>{titleCase(gap.reason)}</span>
            <small>{gap.detail}</small>
          </div>
        ))}
      </section>
    </div>
  );
}

function SystemView({
  readiness,
  onReset,
  busy
}: {
  readiness: Readiness;
  onReset: () => void;
  busy: boolean;
}) {
  return (
    <div className="page-content system-page">
      <section className="system-band">
        <div className="system-status">
          <span className="system-icon"><ShieldCheck size={28} /></span>
          <div>
            <span className="eyebrow">Runtime posture</span>
            <h2>Fixture mode · shadow delivery</h2>
            <p>Deterministic rules active. External alert delivery inactive.</p>
          </div>
        </div>
        <button className="secondary-button" disabled={busy} onClick={onReset}>
          <RefreshCw size={16} /> Reset fixture
        </button>
      </section>
      <section className="system-grid">
        <div className="system-panel">
          <span className="eyebrow">Connections</span>
          <h3>Provider readiness</h3>
          {Object.entries(readiness.providers).map(([name, configured]) => (
            <div className="provider-row" key={name}>
              <StatusDot online={configured} />
              <span>{titleCase(name)}</span>
              <strong>{configured ? "Configured" : "Not configured"}</strong>
            </div>
          ))}
        </div>
        <div className="system-panel">
          <span className="eyebrow">Retention policy</span>
          <h3>Operational storage</h3>
          {Object.entries(readiness.retention_days).map(([name, days]) => (
            <div className="retention-row" key={name}>
              <span>{titleCase(name)}</span>
              <strong>{days} days</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function EventDrawer({
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

  return (
    <div className="drawer-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="event-drawer" aria-label="Event evidence">
        <header>
          <div>
            <SeverityBadge value={event.severity} />
            <span className="drawer-id">{event.event_id.slice(-8)}</span>
          </div>
          <button className="icon-button" aria-label="Close" title="Close" onClick={onClose}>
            <X size={19} />
          </button>
        </header>
        <div className="drawer-title">
          <span className="eyebrow">{event.enclosure_id} · {formatTime(event.start_ts)}</span>
          <h2>{event.animal_name} · {titleCase(event.behavior)}</h2>
          <p>{formatDuration(event.start_ts, event.end_ts)} continuous observation</p>
        </div>

        <div className="evidence-video">
          {source?.media_url ? (
            <video src={source.media_url} controls muted autoPlay playsInline />
          ) : (
            <div className="camera-missing"><Camera size={24} /></div>
          )}
          <span className="fixture-watermark">FIXTURE MEDIA</span>
        </div>

        <section className="drawer-section">
          <div className="drawer-section-title">
            <ClipboardCheck size={17} />
            <h3>Deterministic decision</h3>
          </div>
          <div className="rule-line">
            <span>{event.rule_fired}</span>
            <small>{event.rule_version}</small>
          </div>
          <ul className="fact-list">
            {event.explanation_facts.map((fact) => <li key={fact}>{fact}</li>)}
          </ul>
          <div className="confidence-line">
            <span>Evidence confidence</span>
            <strong>{Math.round(event.confidence * 100)}%</strong>
          </div>
        </section>

        <section className="drawer-section">
          <div className="drawer-section-title">
            <Camera size={17} />
            <h3>Source provenance</h3>
          </div>
          {event.sources.map((item) => (
            <div className="source-row" key={item.observation_id}>
              <div>
                <strong>{item.camera_id} · {formatTime(item.start_ts)}–{formatTime(item.end_ts)}</strong>
                <span>{item.evidence}</span>
              </div>
              <small>{titleCase(item.evidence_kind)} · {item.provider_model}</small>
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
          <select value={resolution} onChange={(event) => setResolution(event.target.value)}>
            <option value="welfare_check_completed">Welfare check completed</option>
            <option value="water_available">Water available</option>
            <option value="continued_observation">Continue observation</option>
            <option value="false_positive">False positive</option>
            <option value="camera_issue">Camera issue</option>
          </select>
          <textarea
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
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
            <small>{outcome.entered_by} · {formatTime(outcome.created_at)}</small>
          </div>
        ))}
      </aside>
    </div>
  );
}

export default App;
