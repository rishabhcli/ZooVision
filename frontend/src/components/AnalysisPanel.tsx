import { Activity, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { MEASURE_HUE, MOTION_HUE, SEVERITY_COLOR, SEVERITY_ORDER } from "../severity";
import type { Dashboard, Severity, VideoTrack } from "../types";

const SPARK_BUCKETS = 48;

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function clockLabel(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(
    total % 60
  ).padStart(2, "0")}`;
}

/** Horizontal bars: one measure across named rows, direct-labeled. */
function BarRows({
  rows,
  caption
}: {
  rows: { key: string; label: string; sub?: string; value: number; color: string }[];
  caption: string;
}) {
  const max = Math.max(1, ...rows.map((row) => row.value));
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="bar-rows" role="img" aria-label={caption}>
      {rows.map((row) => (
        <div
          className={hovered === row.key ? "bar-row hovered" : "bar-row"}
          key={row.key}
          onMouseEnter={() => setHovered(row.key)}
          onMouseLeave={() => setHovered(null)}
        >
          <span className="bar-label">
            <span className="bar-swatch" style={{ background: row.color }} />
            <strong>{row.label}</strong>
            {row.sub && <small>{row.sub}</small>}
          </span>
          <span className="bar-lane">
            <span
              className="bar-fill"
              style={{
                width: `${Math.max(2, (row.value / max) * 100)}%`,
                background: row.color
              }}
            />
          </span>
          <span className="bar-value">{row.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Change over time for a single measured series. */
function MotionSparkline({ track }: { track: VideoTrack | null }) {
  const [hover, setHover] = useState<number | null>(null);

  const { points, buckets, span, peak } = useMemo(() => {
    const detections = track?.detections ?? [];
    if (detections.length === 0) {
      return { points: "", buckets: [] as number[], span: 0, peak: 0 };
    }
    const maxSeconds = Math.max(...detections.map((d) => d.video_seconds), 1);
    const counts = new Array(SPARK_BUCKETS).fill(0);
    detections.forEach((item) => {
      const index = Math.min(
        SPARK_BUCKETS - 1,
        Math.floor((item.video_seconds / maxSeconds) * SPARK_BUCKETS)
      );
      counts[index] += 1;
    });
    const highest = Math.max(1, ...counts);
    const path = counts
      .map((value, index) => {
        const x = (index / (SPARK_BUCKETS - 1)) * 100;
        const y = 30 - (value / highest) * 26;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
    return { points: path, buckets: counts, span: maxSeconds, peak: highest };
  }, [track]);

  if (!points) {
    return (
      <p className="chart-empty">
        No motion measured on the selected feed.
      </p>
    );
  }

  return (
    <div className="sparkline-wrap">
      <svg viewBox="0 0 100 32" preserveAspectRatio="none" role="img"
        aria-label="Measured motion regions over the length of the feed">
        <polyline
          className="spark-line"
          points={points}
          fill="none"
          stroke={MOTION_HUE}
          strokeWidth={0.9}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        <polygon
          points={`0,32 ${points} 100,32`}
          fill={MOTION_HUE}
          opacity={0.12}
        />
        {buckets.map((_, index) => (
          <rect
            key={index}
            x={(index / SPARK_BUCKETS) * 100}
            y={0}
            width={100 / SPARK_BUCKETS}
            height={32}
            fill="transparent"
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      <div className="spark-axis">
        <span>00:00</span>
        <span>
          {hover !== null
            ? `${buckets[hover]} region(s) near ${clockLabel(
                (hover / SPARK_BUCKETS) * span
              )}`
            : `peak ${peak} per bucket`}
        </span>
        <span>{clockLabel(span)}</span>
      </div>
    </div>
  );
}

export function AnalysisPanel({
  dashboard,
  track,
  onOpenEvent
}: {
  dashboard: Dashboard;
  track: VideoTrack | null;
  onOpenEvent: (eventId: string) => void;
}) {
  const severityRows = useMemo(() => {
    const counts = new Map<Severity, number>();
    dashboard.events.forEach((event) =>
      counts.set(event.severity, (counts.get(event.severity) ?? 0) + 1)
    );
    return SEVERITY_ORDER.map((severity) => ({
      key: severity,
      label: severity,
      value: counts.get(severity) ?? 0,
      color: SEVERITY_COLOR[severity]
    }));
  }, [dashboard.events]);

  const animalRows = useMemo(
    () =>
      [...dashboard.animals]
        .sort((a, b) => b.event_count - a.event_count)
        .map((animal) => ({
          key: animal.animal_id,
          label: animal.name,
          sub: `${animal.species} · ${animal.enclosure_id}`,
          value: animal.event_count,
          color: MEASURE_HUE
        })),
    [dashboard.animals]
  );

  const ruleRows = useMemo(() => {
    const counts = new Map<string, number>();
    dashboard.events.forEach((event) => {
      if (event.rule_fired) {
        counts.set(event.rule_fired, (counts.get(event.rule_fired) ?? 0) + 1);
      }
    });
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([rule, value]) => ({
        key: rule,
        label: rule,
        value,
        color: MEASURE_HUE
      }));
  }, [dashboard.events]);

  return (
    <div className="analysis-panel">
      <section className="analysis-grid">
        <article className="chart-card">
          <header>
            <span className="eyebrow">Deterministic triage</span>
            <h3>Events by severity</h3>
          </header>
          <BarRows rows={severityRows} caption="Recorded events by severity" />
          <footer>
            Severity comes only from a fired rule. No model sets it.
          </footer>
        </article>

        <article className="chart-card">
          <header>
            <span className="eyebrow">Per animal</span>
            <h3>Recorded events</h3>
          </header>
          <BarRows rows={animalRows} caption="Recorded events per animal" />
          <footer>
            Animals with zero events are shown so a quiet night is visible.
          </footer>
        </article>

        <article className="chart-card">
          <header>
            <span className="eyebrow">Rule activity</span>
            <h3>Rules fired</h3>
          </header>
          {ruleRows.length ? (
            <BarRows rows={ruleRows} caption="Events grouped by the rule that fired" />
          ) : (
            <p className="chart-empty">No rule fired in this shift.</p>
          )}
          <footer>First-match ordering means one rule per event.</footer>
        </article>

        <article className="chart-card">
          <header>
            <span className="eyebrow">Selected feed</span>
            <h3>Measured motion over time</h3>
          </header>
          <MotionSparkline track={track} />
          <footer>
            Motion regions locate movement. They do not identify species or
            behavior.
          </footer>
        </article>
      </section>

      <section className="analysis-table">
        <header className="section-heading">
          <div>
            <span className="eyebrow">Full record</span>
            <h3>Every recorded event</h3>
          </div>
          <span className="count-label">{dashboard.events.length} rows</span>
        </header>
        <table>
          <thead>
            <tr>
              <th scope="col">Severity</th>
              <th scope="col">Animal</th>
              <th scope="col">Behavior</th>
              <th scope="col">Rule</th>
              <th scope="col">Evidence</th>
              <th scope="col">Review</th>
            </tr>
          </thead>
          <tbody>
            {dashboard.events.map((event) => (
              <tr key={event.event_id} onClick={() => onOpenEvent(event.event_id)}>
                <td>
                  <span className="severity-cell">
                    <span
                      className="bar-swatch"
                      style={{ background: SEVERITY_COLOR[event.severity] }}
                    />
                    {event.severity}
                  </span>
                </td>
                <td>
                  <strong>{event.animal_name}</strong>
                  <small>{event.enclosure_id}</small>
                </td>
                <td>{titleCase(event.behavior)}</td>
                <td className="mono">{event.rule_fired}</td>
                <td className="evidence-cell">{event.explanation_facts.join(" ")}</td>
                <td>{titleCase(event.ack_state)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {dashboard.data_gaps.length > 0 && (
        <section className="analysis-gaps">
          <header className="section-heading">
            <div>
              <span className="eyebrow">Coverage</span>
              <h3>Data gaps</h3>
            </div>
          </header>
          {dashboard.data_gaps.map((gap) => (
            <div className="gap-row" key={gap.gap_id}>
              <TriangleAlert size={17} />
              <strong>{gap.enclosure_id}</strong>
              <span>{titleCase(gap.reason)}</span>
              <small>{gap.detail}</small>
            </div>
          ))}
        </section>
      )}

      {dashboard.events.length === 0 && (
        <div className="analysis-quiet">
          <Activity size={22} />
          <p>No deterministic events recorded. Coverage still applies.</p>
        </div>
      )}
    </div>
  );
}

export default AnalysisPanel;
