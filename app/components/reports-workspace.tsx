"use client";

import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Download,
  FileClock,
  LoaderCircle,
  Printer,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type ReportRun, type ReportSnapshot } from "../lib/api";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function currentShiftLabel() {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date()) + " overnight shift";
}

function titleCase(value: string | null | undefined) {
  return (value ?? "Unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function ReportsWorkspace() {
  const [runs, setRuns] = useState<ReportRun[]>([]);
  const [selected, setSelected] = useState<ReportRun | null>(null);
  const [shiftLabel, setShiftLabel] = useState(currentShiftLabel);
  const [generatedBy, setGeneratedBy] = useState("ZooVision operator");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await api.reports();
      setRuns(payload.reports);
      if (payload.reports[0] && !selected) {
        setSelected(await api.report(payload.reports[0].report_id));
      }
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reports unavailable");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadRuns(), 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns]);

  async function generateReport() {
    setGenerating(true);
    setError(null);
    try {
      const next = await api.createReport(shiftLabel, generatedBy);
      setSelected(next);
      setRuns((current) => [
        {
          report_id: next.report_id,
          shift_label: next.shift_label,
          generated_by: next.generated_by,
          created_at: next.created_at,
        },
        ...current.filter((run) => run.report_id !== next.report_id),
      ]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report could not be saved");
    } finally {
      setGenerating(false);
    }
  }

  async function openRun(reportId: string) {
    setLoading(true);
    try {
      setSelected(await api.report(reportId));
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Saved report unavailable");
    } finally {
      setLoading(false);
    }
  }

  const report = selected?.report as ReportSnapshot | undefined;

  return (
    <div className="reports-page">
      <header className="reports-hero">
        <div>
          <span className="reports-kicker">Operational reporting</span>
          <h1>Turn the shift into a keeper-ready brief</h1>
          <p>
            Save a point-in-time report with every monitored animal, routed event,
            and camera gap. The snapshot stays available after the live queue changes.
          </p>
        </div>
        <div className="reports-hero-actions">
          <button type="button" className="reports-quiet-button" onClick={() => void loadRuns()}>
            <RefreshCw className={loading ? "spin" : undefined} size={15} />
            Refresh history
          </button>
          {selected && (
            <>
              <a className="reports-quiet-button" href={api.reportExportUrl(selected.report_id)} download>
                <Download size={15} />
                Download CSV
              </a>
              <button type="button" className="reports-primary-button" onClick={() => window.print()}>
                <Printer size={15} />
                Print brief
              </button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="reports-error" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button type="button" onClick={() => void loadRuns()}>Retry</button>
        </div>
      )}

      <section className="reports-create" aria-label="Create a report snapshot">
        <div>
          <span className="reports-section-label">New snapshot</span>
          <strong>Save the current evidence record</strong>
          <small>Reports include quiet animals and explicit data gaps.</small>
        </div>
        <label>
          <span>Shift label</span>
          <input value={shiftLabel} onChange={(event) => setShiftLabel(event.target.value)} maxLength={120} />
        </label>
        <label>
          <span>Prepared by</span>
          <input value={generatedBy} onChange={(event) => setGeneratedBy(event.target.value)} maxLength={80} />
        </label>
        <button
          type="button"
          className="reports-primary-button"
          disabled={generating || !shiftLabel.trim() || !generatedBy.trim()}
          onClick={() => void generateReport()}
        >
          {generating ? <LoaderCircle className="spin" size={15} /> : <FileClock size={15} />}
          {generating ? "Saving..." : "Save report"}
        </button>
      </section>

      <div className="reports-layout">
        <aside className="reports-history-panel">
          <header>
            <div>
              <span className="reports-section-label">Saved history</span>
              <strong>{runs.length} report snapshots</strong>
            </div>
          </header>
          {runs.length ? (
            <div className="reports-run-list">
              {runs.map((run) => (
                <button
                  type="button"
                  key={run.report_id}
                  className={selected?.report_id === run.report_id ? "active" : undefined}
                  onClick={() => void openRun(run.report_id)}
                >
                  <CalendarClock size={16} />
                  <span>
                    <strong>{run.shift_label}</strong>
                    <small>{formatDate(run.created_at)} · {run.generated_by}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="reports-empty">
              <FileClock size={22} />
              <span>No saved briefs yet</span>
            </div>
          )}
        </aside>

        <main className="reports-document">
          {report ? (
            <>
              <header className="reports-document-header">
                <div>
                  <span className="reports-section-label">Saved evidence brief</span>
                  <h2>{selected?.shift_label}</h2>
                  <small>Generated {formatDate(selected?.created_at ?? "")} by {selected?.generated_by}</small>
                </div>
                <ShieldCheck size={25} />
              </header>
              <section className="reports-metrics" aria-label="Report summary">
                <div><span>Animals monitored</span><strong>{report.summary.animals_monitored}</strong><small>Quiet animals included</small></div>
                <div><span>Welfare events</span><strong>{report.summary.events}</strong><small>Deterministic rules fired</small></div>
                <div><span>Data gaps</span><strong>{report.summary.data_gaps}</strong><small>Coverage needing attention</small></div>
              </section>
              <section className="reports-animal-table" aria-label="Animal summary">
                <header><span>Animal coverage</span><strong>Every monitored animal</strong></header>
                <div className="reports-table-head"><span>Animal</span><span>Baseline</span><span>Events</span><span>Enclosure</span></div>
                {report.animals.map((animal) => (
                  <div className="reports-table-row" key={animal.animal_id}>
                    <span><strong>{animal.name}</strong><small>{animal.species}</small></span>
                    <span><b data-state={animal.baseline_state}>{titleCase(animal.baseline_state)}</b><small>{animal.baseline_days} daytime shifts</small></span>
                    <span className={animal.events.length ? "has-events" : undefined}>{animal.events.length || "None"}</span>
                    <span>{animal.enclosure_id}</span>
                  </div>
                ))}
              </section>
              <section className="reports-event-table" aria-label="Report events">
                <header><span>Routed events</span><strong>{report.summary.events ? "Preserved with rule provenance" : "No deterministic welfare events"}</strong></header>
                {report.animals.flatMap((animal) =>
                  animal.events.map((event) => (
                    <div className="reports-event-row" key={event.event_id}>
                      <span data-severity={event.severity}>{event.severity}</span>
                      <strong>{animal.name} · {titleCase(event.behavior)}</strong>
                      <span>{event.rule_fired}</span>
                      <small>{titleCase(event.review_state)} · {titleCase(event.ack_state)}</small>
                    </div>
                  )),
                )}
                {!report.summary.events && (
                  <p className="reports-no-events"><CheckCircle2 size={16} /> No rules fired in this snapshot.</p>
                )}
              </section>
              <section className="reports-gap-table" aria-label="Report data gaps">
                <header><span>Coverage notes</span><strong>{report.data_gaps.length ? "Open gaps remain visible" : "No data gaps recorded"}</strong></header>
                {report.data_gaps.map((gap) => (
                  <div key={String(gap.gap_id)}>
                    <AlertTriangle size={15} />
                    <span><strong>{titleCase(String(gap.reason))}</strong><small>{String(gap.detail || "No additional detail")}</small></span>
                    <small>{String(gap.enclosure_id)}</small>
                  </div>
                ))}
              </section>
            </>
          ) : (
            <div className="reports-empty document">
              <FileClock size={28} />
              <strong>{loading ? "Loading saved brief" : "Save a report to begin"}</strong>
              <span>The generated snapshot will appear here for review and export.</span>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
