import {
  Activity,
  BarChart3,
  Camera,
  Check,
  ChevronRight,
  CircleGauge,
  CloudUpload,
  FileClock,
  HeartPulse,
  Moon,
  Network,
  Radio,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import AnalysisPanel from "./components/AnalysisPanel";
import ChatRail from "./components/ChatRail";
import EventDrawer from "./components/EventDrawer";
import GraphPanel from "./components/GraphPanel";
import IngestPanel from "./components/IngestPanel";
import VideoPanel from "./components/VideoPanel";
import { SEVERITY_COLOR, SEVERITY_RANK } from "./severity";
import type {
  Dashboard,
  EventDetail,
  GraphPayload,
  IngestJobState,
  MorningReport,
  Readiness,
  Severity,
  VideoSource,
  VideoTrack
} from "./types";

type View = "workspace" | "report" | "system";
type Workspace = "graph" | "video" | "analysis" | "ingest";

const NAV_ITEMS = [
  { id: "workspace" as const, label: "Live workspace", icon: Activity },
  { id: "report" as const, label: "Morning brief", icon: FileClock },
  { id: "system" as const, label: "System", icon: CircleGauge }
];

const WORKSPACE_TABS = [
  { id: "graph" as const, label: "Knowledge graph", icon: Network },
  { id: "video" as const, label: "Camera feed", icon: Camera },
  { id: "analysis" as const, label: "Analysis", icon: BarChart3 },
  { id: "ingest" as const, label: "Ingest", icon: CloudUpload }
];

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  twelvelabs: "TwelveLabs",
  aws_storage: "AWS S3",
  neo4j: "Neo4j",
  slack: "Slack"
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function SeverityBadge({ value }: { value: Severity }) {
  return (
    <span className="severity" style={{ background: SEVERITY_COLOR[value] }}>
      {value}
    </span>
  );
}

function StatusDot({ online = true }: { online?: boolean }) {
  return <span className={`status-dot ${online ? "online" : "offline"}`} />;
}

function App() {
  const [view, setView] = useState<View>("workspace");
  const [workspace, setWorkspace] = useState<Workspace>("graph");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [report, setReport] = useState<MorningReport | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [graph, setGraph] = useState<GraphPayload | null>(null);
  const [videos, setVideos] = useState<VideoSource[]>([]);
  const [track, setTrack] = useState<VideoTrack | null>(null);
  const [jobs, setJobs] = useState<IngestJobState[]>([]);
  const [scope, setScope] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  const [selected, setSelected] = useState<EventDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedEventId = selected?.event_id;

  const load = useCallback(async () => {
    try {
      setError("");
      const [nextDashboard, nextReport, nextReadiness, nextVideos, nextJobs] =
        await Promise.all([
          api.dashboard(),
          api.report(),
          api.readiness(),
          api.videos(),
          api.ingestJobs()
        ]);
      setDashboard(nextDashboard);
      setReport(nextReport);
      setReadiness(nextReadiness);
      setVideos(nextVideos.videos);
      setJobs(nextJobs.jobs);
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

  // The graph reloads whenever the operator switches enclosure web.
  useEffect(() => {
    api
      .graph(scope)
      .then(setGraph)
      .catch((caught: unknown) =>
        setError(caught instanceof Error ? caught.message : "Unable to load the graph")
      );
  }, [scope, dashboard]);

  // Keep a feed selected: prefer one inside the current enclosure scope.
  useEffect(() => {
    if (videos.length === 0) {
      setSelectedVideo(null);
      return;
    }
    const inScope = scope
      ? videos.filter((item) => item.enclosure_id === scope)
      : videos;
    const pool = inScope.length > 0 ? inScope : videos;
    if (!selectedVideo || !pool.some((item) => item.source_path === selectedVideo)) {
      setSelectedVideo(pool[0].source_path);
    }
  }, [videos, scope, selectedVideo]);

  useEffect(() => {
    if (!selectedVideo) {
      setTrack(null);
      return;
    }
    api
      .videoTrack(selectedVideo)
      .then(setTrack)
      .catch(() => setTrack(null));
  }, [selectedVideo, dashboard]);

  const refreshJobs = useCallback(() => {
    api
      .ingestJobs()
      .then((payload) => setJobs(payload.jobs))
      .catch(() => undefined);
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

  const scopedVideos = useMemo(
    () => (scope ? videos.filter((item) => item.enclosure_id === scope) : videos),
    [videos, scope]
  );

  const pending = dashboard
    ? dashboard.events.filter((event) => event.ack_state === "pending").length
    : 0;
  const highest = dashboard
    ? dashboard.events.reduce<Severity>(
        (current, event) =>
          SEVERITY_RANK[event.severity] > SEVERITY_RANK[current]
            ? event.severity
            : current,
        "NONE"
      )
    : "NONE";

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

        {view === "workspace" && (
          <>
            <div className="side-menu">
              <span className="side-menu-title">Enclosure web</span>
              <button
                className={scope === null ? "side-option active" : "side-option"}
                onClick={() => setScope(null)}
              >
                All enclosures
                <em>{videos.length}</em>
              </button>
              {(graph?.enclosures ?? []).map((enclosure) => (
                <button
                  key={enclosure}
                  className={scope === enclosure ? "side-option active" : "side-option"}
                  onClick={() => setScope(enclosure)}
                >
                  {enclosure}
                  <em>
                    {videos.filter((v) => v.enclosure_id === enclosure).length}
                  </em>
                </button>
              ))}
            </div>

            <div className="side-menu">
              <span className="side-menu-title">Camera feed</span>
              {scopedVideos.length === 0 && (
                <span className="side-empty">No analyzed feeds</span>
              )}
              {scopedVideos.map((item) => (
                <button
                  key={item.source_path}
                  className={
                    selectedVideo === item.source_path
                      ? "side-option active"
                      : "side-option"
                  }
                  onClick={() => {
                    setSelectedVideo(item.source_path);
                    setWorkspace("video");
                  }}
                  title={item.source_path}
                >
                  {item.camera_id}
                  <em>{item.event_count}</em>
                </button>
              ))}
            </div>
          </>
        )}

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
            <span className="breadcrumb">
              Operations / {NAV_ITEMS.find((i) => i.id === view)?.label}
              {view === "workspace" &&
                ` / ${WORKSPACE_TABS.find((t) => t.id === workspace)?.label}`}
            </span>
            <h1>
              {view === "workspace"
                ? WORKSPACE_TABS.find((t) => t.id === workspace)?.label
                : NAV_ITEMS.find((i) => i.id === view)?.label}
            </h1>
          </div>
          <div className="topbar-actions">
            <span className="mode-pill">
              <StatusDot />
              {readiness?.fixture_mode ? "Fixture feed" : "Live feed"}
            </span>
            <span className="mode-pill subtle">
              {pending} awaiting review
            </span>
            <span className="mode-pill subtle">
              Highest <SeverityBadge value={highest} />
            </span>
            <button className="icon-button" aria-label="Refresh" onClick={() => void load()}>
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
            {view === "workspace" && (
              <div className="workspace">
                <div className="workspace-tabs" role="tablist">
                  {WORKSPACE_TABS.map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <button
                        key={tab.id}
                        role="tab"
                        aria-selected={workspace === tab.id}
                        className={
                          workspace === tab.id ? "workspace-tab active" : "workspace-tab"
                        }
                        onClick={() => setWorkspace(tab.id)}
                      >
                        <Icon size={16} />
                        {tab.label}
                      </button>
                    );
                  })}
                </div>

                <div className="workspace-body">
                  {workspace === "graph" && (
                    <GraphPanel
                      graph={graph}
                      scope={scope}
                      onScope={setScope}
                      onOpenEvent={(id) => void openEvent(id)}
                    />
                  )}
                  {workspace === "video" && (
                    <VideoPanel
                      sources={scopedVideos}
                      selected={selectedVideo}
                      track={track}
                      onSelect={setSelectedVideo}
                      onOpenEvent={(id) => void openEvent(id)}
                    />
                  )}
                  {workspace === "analysis" && (
                    <AnalysisPanel
                      dashboard={dashboard}
                      track={track}
                      onOpenEvent={(id) => void openEvent(id)}
                    />
                  )}
                  {workspace === "ingest" && (
                    <IngestPanel jobs={jobs} onRefresh={refreshJobs} />
                  )}
                </div>
              </div>
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

      <ChatRail
        scopeLabel={scope ?? "All enclosures"}
        enclosureId={scope}
      />

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
          <span>
            <strong>{report.summary.animals_monitored}</strong> animals
          </span>
          <span>
            <strong>{report.summary.events}</strong> events
          </span>
          <span>
            <strong>{report.summary.data_gaps}</strong> gaps
          </span>
        </div>
      </div>
      <section className="report-list">
        {report.animals.map((animal) => (
          <article className="report-animal" key={animal.animal_id}>
            <div className="report-animal-head">
              <span className="animal-monogram">{animal.name.slice(0, 1)}</span>
              <div>
                <h3>{animal.name}</h3>
                <span>
                  {animal.species} · {animal.enclosure_id}
                </span>
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
            <span>
              {formatTime(gap.start_ts)}–{formatTime(gap.end_ts)}
            </span>
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
          <span className="system-icon">
            <ShieldCheck size={28} />
          </span>
          <div>
            <span className="eyebrow">Runtime posture</span>
            <h2>
              {readiness.fixture_mode ? "Fixture mode" : "Live mode"} ·{" "}
              {readiness.delivery_mode} delivery
            </h2>
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
          {Object.entries(readiness.providers).map(([name, provider]) => (
            <div className="provider-row" key={name}>
              <StatusDot online={provider.enabled} />
              <span>{PROVIDER_LABELS[name] || titleCase(name)}</span>
              <strong>{titleCase(provider.status)}</strong>
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

export default App;
