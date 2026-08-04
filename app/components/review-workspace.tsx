"use client";

import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock3,
  Download,
  ExternalLink,
  FileCheck2,
  Filter,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type DashboardPayload,
  type EventDetail,
  type ReviewEvent,
  type ReviewPayload,
} from "../lib/api";

type ReviewFilters = {
  query: string;
  severity: string;
  reviewState: string;
  animalId: string;
};

const DEFAULT_FILTERS: ReviewFilters = {
  query: "",
  severity: "all",
  reviewState: "all",
  animalId: "all",
};

const RESOLUTIONS = [
  ["welfare_check_completed", "Welfare check completed"],
  ["water_available", "Water available"],
  ["continued_observation", "Continue observation"],
  ["false_positive", "False positive"],
  ["camera_issue", "Camera issue"],
] as const;

function titleCase(value: string | null | undefined) {
  return (value ?? "Unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function severityLabel(event: ReviewEvent) {
  return event.severity === "CRITICAL" ? "Critical" : titleCase(event.severity);
}

export function ReviewWorkspace() {
  const [filters, setFilters] = useState<ReviewFilters>(DEFAULT_FILTERS);
  const [payload, setPayload] = useState<ReviewPayload | null>(null);
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [selected, setSelected] = useState<EventDetail | null>(null);
  const [resolution, setResolution] = useState("welfare_check_completed");
  const [note, setNote] = useState("");
  const [keeper, setKeeper] = useState("ZooVision operator");
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReview = useCallback(async () => {
    setLoading(true);
    try {
      const next = await api.reviewEvents(filters);
      setPayload(next);
      setSelectedId((current) =>
        next.events.some((event) => event.event_id === current)
          ? current
          : next.events[0]?.event_id ?? "",
      );
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Review queue unavailable");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void api.dashboard().then(setDashboard).catch(() => undefined);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadReview(), 180);
    return () => window.clearTimeout(timer);
  }, [loadReview]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }
    let active = true;
    api
      .event(selectedId)
      .then((detail) => {
        if (active) setSelected(detail);
      })
      .catch((caught) => {
        if (active) {
          setSelected(null);
          setError(caught instanceof Error ? caught.message : "Event detail unavailable");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const animals = useMemo(
    () =>
      (dashboard?.animals ?? []).map((animal) => ({
        id: animal.animal_id,
        label: animal.name + " · " + animal.species,
      })),
    [dashboard],
  );

  const activeSelected = selected?.event_id === selectedId ? selected : null;
  const selectedSource = activeSelected?.sources?.[0];

  function setFilter<Key extends keyof ReviewFilters>(key: Key, value: ReviewFilters[Key]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTERS);
  }

  async function mutate(action: () => Promise<unknown>) {
    setPending(true);
    setError(null);
    try {
      await action();
      await loadReview();
      if (selectedId) setSelected(await api.event(selectedId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Review update failed");
    } finally {
      setPending(false);
    }
  }

  function openInMonitor() {
    if (!selectedSource) return;
    sessionStorage.setItem(
      "zoovision:pending-moment",
      JSON.stringify({
        sourcePath: selectedSource.source_path,
        seconds: selectedSource.source_offset_seconds,
      }),
    );
  }

  return (
    <div className="review-page">
      <header className="review-hero">
        <div>
          <span className="review-kicker">Operator review</span>
          <h1>Close the loop on every routed event</h1>
          <p>
            Search the evidence record, acknowledge the alert, and preserve the human
            outcome that follows. Severity and rule provenance remain deterministic.
          </p>
        </div>
        <div className="review-hero-actions">
          <button type="button" className="review-quiet-button" onClick={() => void loadReview()}>
            <RefreshCw className={loading ? "spin" : undefined} size={15} />
            Refresh queue
          </button>
          <a className="review-primary-button" href={api.reviewExportUrl(filters)} download>
            <Download size={15} />
            Export CSV
          </a>
        </div>
      </header>

      <section className="review-counts" aria-label="Review queue summary">
        {(["all", "unreviewed", "confirmed", "dismissed"] as const).map((state) => (
          <button
            type="button"
            key={state}
            className={filters.reviewState === state ? "active" : undefined}
            onClick={() => setFilter("reviewState", state)}
          >
            <span>{titleCase(state)}</span>
            <strong>{payload?.counts[state] ?? 0}</strong>
          </button>
        ))}
      </section>

      <section className="review-toolbar" aria-label="Review filters">
        <label className="review-search">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search the review queue</span>
          <input
            type="search"
            value={filters.query}
            onChange={(event) => setFilter("query", event.target.value)}
            placeholder="Search animal, rule, evidence..."
          />
        </label>
        <label>
          <span>Severity</span>
          <select value={filters.severity} onChange={(event) => setFilter("severity", event.target.value)}>
            <option value="all">All severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MODERATE">Moderate</option>
            <option value="LOW">Low</option>
          </select>
        </label>
        <label>
          <span>Animal</span>
          <select value={filters.animalId} onChange={(event) => setFilter("animalId", event.target.value)}>
            <option value="all">All animals</option>
            {animals.map((animal) => (
              <option value={animal.id} key={animal.id}>{animal.label}</option>
            ))}
          </select>
        </label>
        <button type="button" className="review-filter-reset" onClick={clearFilters}>
          <Filter size={14} />
          Clear
        </button>
      </section>

      {error && (
        <div className="review-error" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button type="button" onClick={() => void loadReview()}>Retry</button>
        </div>
      )}

      <div className="review-grid">
        <section className="review-list-panel" aria-label="Welfare events">
          <header className="review-list-header">
            <div>
              <span>Evidence queue</span>
              <strong>{payload?.events.length ?? 0} events in view</strong>
            </div>
            <small>
              {filters.query
                ? "Matching “" + filters.query + "”"
                : "Highest severity first"}
            </small>
          </header>
          {loading && !payload ? (
            <div className="review-state">
              <LoaderCircle className="spin" size={22} />
              <span>Loading routed events</span>
            </div>
          ) : payload?.events.length ? (
            <div className="review-event-list">
              {payload.events.map((event) => (
                <button
                  type="button"
                  key={event.event_id}
                  className="review-event-row"
                  data-selected={event.event_id === selectedId}
                  onClick={() => setSelectedId(event.event_id)}
                >
                  <span className="review-event-severity" data-severity={event.severity}>
                    {event.severity.slice(0, 1)}
                  </span>
                  <span className="review-event-main">
                    <strong>{event.animal_name + " · " + titleCase(event.behavior)}</strong>
                    <small>
                      {event.species + " · " + event.enclosure_id + " · " + formatDate(event.start_ts)}
                    </small>
                    <em>{titleCase(event.rule_fired)}</em>
                  </span>
                  <span className="review-event-state">
                    <b data-state={event.review_state}>{titleCase(event.review_state)}</b>
                    <small>{event.ack_state ? titleCase(event.ack_state) : "No alert"}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="review-state">
              <CheckCircle2 size={22} />
              <strong>No events match these filters</strong>
              <span>Try a broader search or return to all review states.</span>
            </div>
          )}
        </section>

        <aside className="review-detail-panel" aria-label="Selected event detail">
          {activeSelected ? (
            <>
              <header className="review-detail-header">
                <div>
                  <span>Evidence inspector</span>
                  <h2>{activeSelected.animal_name + " · " + titleCase(activeSelected.behavior)}</h2>
                  <small>
                    {activeSelected.species + " · " + activeSelected.enclosure_id + " · " + formatDate(activeSelected.start_ts)}
                  </small>
                </div>
                <span className="review-detail-severity" data-severity={activeSelected.severity}>
                  {severityLabel(activeSelected)}
                </span>
              </header>

              <div className="review-facts">
                <div><span>Rule fired</span><strong>{activeSelected.rule_fired}</strong></div>
                <div><span>Keeper action</span><strong>{titleCase(activeSelected.action)}</strong></div>
                <div><span>Review state</span><strong>{titleCase(activeSelected.review_state)}</strong></div>
                <div><span>Evidence source</span><strong>{selectedSource?.camera_id ?? "Source clip attached"}</strong></div>
              </div>

              <section className="review-detail-section">
                <span className="review-section-label">Why it was routed</span>
                <ul>
                  {activeSelected.explanation_facts.map((fact) => <li key={fact}>{fact}</li>)}
                </ul>
              </section>

              {selectedSource && (
                <a href="/monitor" className="review-source-button" onClick={openInMonitor}>
                  <Play size={15} />
                  Open source moment in Monitor
                  <ExternalLink size={14} />
                </a>
              )}

              <section className="review-action-section">
                <span className="review-section-label">Operator action</span>
                {activeSelected.alert_id && activeSelected.ack_state === "pending" ? (
                  <button
                    type="button"
                    className="review-ack-button"
                    disabled={pending}
                    onClick={() => void mutate(() => api.acknowledgeAlert(activeSelected.alert_id!, keeper))}
                  >
                    {pending ? <LoaderCircle className="spin" size={15} /> : <ShieldCheck size={15} />}
                    Acknowledge alert
                  </button>
                ) : (
                  <div className="review-ack-state">
                    <Check size={15} />
                    {activeSelected.ack_state ? "Alert " + titleCase(activeSelected.ack_state) : "No alert is pending"}
                  </div>
                )}
                <div className="review-outcome-form">
                  <label>
                    <span>Resolution</span>
                    <select value={resolution} onChange={(event) => setResolution(event.target.value)}>
                      {RESOLUTIONS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                    </select>
                  </label>
                  <label>
                    <span>Entered by</span>
                    <input value={keeper} onChange={(event) => setKeeper(event.target.value)} maxLength={80} />
                  </label>
                  <label>
                    <span>Review note</span>
                    <textarea
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="What did the keeper confirm?"
                      maxLength={500}
                      rows={3}
                    />
                  </label>
                  <button
                    type="button"
                    className="review-outcome-button"
                    disabled={pending || !keeper.trim()}
                    onClick={() => void mutate(() => api.recordOutcome(activeSelected.event_id, resolution, keeper, note))}
                  >
                    {pending ? <LoaderCircle className="spin" size={15} /> : <FileCheck2 size={15} />}
                    Save outcome
                  </button>
                </div>
              </section>

              {activeSelected.outcomes.length > 0 && (
                <section className="review-history">
                  <span className="review-section-label">Recorded history</span>
                  {activeSelected.outcomes.map((outcome) => (
                    <div key={outcome.outcome_id}>
                      <Clock3 size={14} />
                      <span>
                        <strong>{titleCase(outcome.resolution)}</strong>
                        <small>{(outcome.note || "No note") + " · " + outcome.entered_by}</small>
                      </span>
                      <time>{formatDate(outcome.created_at)}</time>
                    </div>
                  ))}
                </section>
              )}
            </>
          ) : (
            <div className="review-state detail">
              <XCircle size={24} />
              <strong>Select a routed event</strong>
              <span>Its source evidence, rule facts, and operator history will appear here.</span>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
