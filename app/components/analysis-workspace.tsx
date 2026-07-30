"use client";

import {
  Check,
  Clock3,
  ExternalLink,
  FileText,
  Play,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";

type Activity = {
  id: string;
  time: string;
  title: string;
  meta: string;
  type: "source" | "rule" | "human";
  source: string;
};

const activities: Activity[] = [
  {
    id: "water",
    time: "20:30",
    title: "Last water contact",
    meta: "Rex · ENC-07 Camera 2",
    type: "source",
    source: "Camera observation",
  },
  {
    id: "pacing-start",
    time: "02:00",
    title: "Pacing started",
    meta: "Rex · continuous motion",
    type: "source",
    source: "Validated segment",
  },
  {
    id: "pacing-end",
    time: "02:14",
    title: "Pacing ended · 14 min",
    meta: "Rex · confidence 0.91",
    type: "source",
    source: "Validated segment",
  },
  {
    id: "rule",
    time: "02:15",
    title: "Rule fired · pacing > 10 min",
    meta: "Severity fixed as MODERATE",
    type: "rule",
    source: "Deterministic rule engine",
  },
  {
    id: "ack",
    time: "02:18",
    title: "Acknowledged",
    meta: "Maria Chen · welfare check",
    type: "human",
    source: "Human review",
  },
];

export function AnalysisWorkspace() {
  const [selectedId, setSelectedId] = useState("pacing-start");
  const [briefingReady, setBriefingReady] = useState(false);
  const selected = useMemo(
    () => activities.find((activity) => activity.id === selectedId)!,
    [selectedId],
  );

  return (
    <div className="page-stack analysis-page">
      <div className="control-row">
        <div className="analysis-scope-readout">
          <Clock3 size={15} />
          <span>
            <small>ENC-07 · All monitored animals</small>
            <strong>Tonight · 22:00–06:00</strong>
          </span>
        </div>
        <button
          className="primary-button briefing-button"
          type="button"
          onClick={() => setBriefingReady(true)}
        >
          {briefingReady ? <Check size={15} /> : <Sparkles size={15} />}
          {briefingReady ? "Briefing prepared" : "Prepare morning briefing"}
        </button>
      </div>

      <div className="analysis-heading">
        <div>
          <span className="section-kicker">July 30 · Night shift</span>
          <h1>Overnight evidence review</h1>
          <p>Observed evidence, deterministic rules, and human outcomes.</p>
        </div>
        <div className="analysis-summary">
          <div>
            <span>Coverage</span>
            <strong>100%</strong>
            <small>22:00–06:00</small>
          </div>
          <div>
            <span>Animals</span>
            <strong>2</strong>
            <small>monitored</small>
          </div>
          <div>
            <span>Review items</span>
            <strong>1</strong>
            <small>acknowledged</small>
          </div>
          <div>
            <span>Data gaps</span>
            <strong>0</strong>
            <small>detected</small>
          </div>
        </div>
      </div>

      <section className="analysis-layout">
        <div className="analysis-primary-column">
          <article className="analysis-section activity-section">
            <div className="section-heading-row">
              <div>
                <span className="section-kicker">Source-aligned history</span>
                <h2>Activity timeline</h2>
              </div>
              <span className="quiet-meta">
                <Clock3 size={14} />
                Local time
              </span>
            </div>
            <div className="activity-list">
              {activities.map((activity) => (
                <button
                  type="button"
                  className={`activity-row ${
                    selectedId === activity.id ? "selected" : ""
                  }`}
                  onClick={() => setSelectedId(activity.id)}
                  key={activity.id}
                >
                  <time>{activity.time}</time>
                  <span className={`activity-marker ${activity.type}`} />
                  <span className="activity-copy">
                    <strong>{activity.title}</strong>
                    <small>{activity.meta}</small>
                  </span>
                  <span className="activity-source">{activity.source}</span>
                </button>
              ))}
            </div>
          </article>

          <article className="analysis-section animal-table-section">
            <div className="section-heading-row">
              <div>
                <span className="section-kicker">Every monitored animal</span>
                <h2>Animal summary</h2>
              </div>
              <button className="text-button" type="button">
                Full report <ExternalLink size={13} />
              </button>
            </div>
            <div className="animal-table" role="table">
              <div className="animal-table-head" role="row">
                <span>Animal</span>
                <span>Observed behavior</span>
                <span>Baseline delta</span>
                <span>Outcome</span>
                <span>Coverage</span>
              </div>
              <div className="animal-table-row" role="row">
                <span className="animal-cell">
                  <span className="animal-avatar">R</span>
                  <span>
                    <strong>Rex</strong>
                    <small>ENC-07</small>
                  </span>
                </span>
                <span>Pacing · 14 min</span>
                <span className="delta-value">3.1σ above</span>
                <span>
                  <span className="table-status review">Follow up</span>
                </span>
                <span>100%</span>
              </div>
              <div className="animal-table-row" role="row">
                <span className="animal-cell">
                  <span className="animal-avatar">Z</span>
                  <span>
                    <strong>Zuri</strong>
                    <small>ENC-07</small>
                  </span>
                </span>
                <span>No notable events</span>
                <span>Within baseline</span>
                <span>
                  <span className="table-status normal">No action</span>
                </span>
                <span>100%</span>
              </div>
            </div>
          </article>
        </div>

        <div className="analysis-secondary-column">
          <article className="analysis-section comparison-section">
            <div className="section-heading-row">
              <div>
                <span className="section-kicker">Deterministic comparison</span>
                <h2>Behavior vs daytime baseline</h2>
              </div>
              <span className="comparison-value">3.1σ</span>
            </div>
            <div className="bar-chart">
              <div className="chart-row">
                <span>Pacing</span>
                <div className="bar-pair">
                  <span className="bar tonight" style={{ width: "86%" }}>
                    <i>14 min</i>
                  </span>
                  <span className="bar baseline" style={{ width: "28%" }}>
                    <i>4.5 min</i>
                  </span>
                </div>
              </div>
              <div className="chart-row">
                <span>Resting</span>
                <div className="bar-pair">
                  <span className="bar tonight" style={{ width: "67%" }}>
                    <i>62%</i>
                  </span>
                  <span className="bar baseline" style={{ width: "69%" }}>
                    <i>64%</i>
                  </span>
                </div>
              </div>
              <div className="chart-row">
                <span>Water contact</span>
                <div className="bar-pair">
                  <span className="bar tonight" style={{ width: "24%" }}>
                    <i>1</i>
                  </span>
                  <span className="bar baseline" style={{ width: "35%" }}>
                    <i>1.3</i>
                  </span>
                </div>
              </div>
              <div className="chart-legend">
                <span>
                  <i className="tonight" />
                  Tonight
                </span>
                <span>
                  <i className="baseline" />
                  Daytime-only baseline
                </span>
              </div>
            </div>
          </article>

          <article className="analysis-section selected-evidence-section">
            <div className="section-heading-row">
              <div>
                <span className="section-kicker">Selected evidence</span>
                <h2>{selected.title}</h2>
              </div>
              <span className={`activity-marker large ${selected.type}`} />
            </div>
            <dl className="selected-evidence-grid">
              <div>
                <dt>Time</dt>
                <dd>{selected.time}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{selected.source}</dd>
              </div>
              <div>
                <dt>Event ID</dt>
                <dd>EVT-1842</dd>
              </div>
              <div>
                <dt>Acknowledged</dt>
                <dd>02:18 · Maria Chen</dd>
              </div>
            </dl>
            <div className="rule-audit">
              <ShieldCheck size={17} />
              <div>
                <span>Rule provenance</span>
                <strong>pacing &gt; 10 min</strong>
                <small>Severity was not assigned by the assistant.</small>
              </div>
            </div>
            <div className="clip-strip">
              {["02:00", "02:06", "02:14"].map((time, index) => (
                <button
                  type="button"
                  className={index === 1 ? "selected" : undefined}
                  key={time}
                >
                  <span>
                    <Play size={15} />
                  </span>
                  <small>{time}</small>
                </button>
              ))}
            </div>
            <div className="analysis-actions">
              <button className="primary-button" type="button">
                <Play size={15} />
                Review clip
              </button>
              <button className="secondary-button" type="button">
                <FileText size={15} />
                Record outcome
              </button>
            </div>
          </article>
        </div>
      </section>

      {briefingReady && (
        <div className="briefing-toast" role="status">
          <Check size={16} />
          Morning briefing preview is ready. It includes Rex, Zuri, and camera
          coverage.
        </div>
      )}
    </div>
  );
}
