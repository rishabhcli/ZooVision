import { CheckCircle2, CloudUpload, Loader2, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { IngestJobState } from "../types";

const POLL_MS = 2000;

export function IngestPanel({
  jobs,
  onRefresh
}: {
  jobs: IngestJobState[];
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    animal_name: "",
    species: "Unspecified",
    enclosure_id: "ENC-UPLOAD",
    camera_id: "CAM-UPLOAD",
    shift_mode: "night" as "night" | "day",
    segment_seconds: 120
  });
  const fileRef = useRef<HTMLInputElement | null>(null);

  const active = jobs.some(
    (job) => job.status === "queued" || job.status === "running"
  );

  // A running job writes evidence as it goes, so poll while one is in flight.
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(onRefresh, POLL_MS);
    return () => window.clearInterval(timer);
  }, [active, onRefresh]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a video file first.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const uploaded = await api.uploadVideo(file);
      const name = form.animal_name.trim() || file.name.replace(/\.[^.]+$/, "");
      await api.startIngest({
        source_name: uploaded.source_name,
        animal_id: `animal-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        animal_name: name,
        species: form.species,
        enclosure_id: form.enclosure_id,
        camera_id: form.camera_id,
        shift_mode: form.shift_mode,
        segment_seconds: form.segment_seconds
      });
      setNotice(`Analyzing ${uploaded.source_name}.`);
      onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ingest failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ingest-panel">
      <section className="chart-card ingest-form-card">
        <header>
          <span className="eyebrow">Any camera</span>
          <h3>Analyze a video</h3>
        </header>
        <form onSubmit={submit} className="ingest-form">
          <label>
            <span>Video file</span>
            <input ref={fileRef} type="file" accept="video/*" />
          </label>
          <label>
            <span>Animal name</span>
            <input
              value={form.animal_name}
              placeholder="Taken from the file name if blank"
              onChange={(e) => setForm({ ...form, animal_name: e.target.value })}
            />
          </label>
          <label>
            <span>Species</span>
            <input
              value={form.species}
              onChange={(e) => setForm({ ...form, species: e.target.value })}
            />
          </label>
          <label>
            <span>Enclosure</span>
            <input
              value={form.enclosure_id}
              onChange={(e) => setForm({ ...form, enclosure_id: e.target.value })}
            />
          </label>
          <label>
            <span>Camera</span>
            <input
              value={form.camera_id}
              onChange={(e) => setForm({ ...form, camera_id: e.target.value })}
            />
          </label>
          <label>
            <span>Shift</span>
            <select
              value={form.shift_mode}
              onChange={(e) =>
                setForm({ ...form, shift_mode: e.target.value as "night" | "day" })
              }
            >
              <option value="night">Night (can raise events)</option>
              <option value="day">Day (baseline only)</option>
            </select>
          </label>
          <label>
            <span>Segment seconds</span>
            <input
              type="number"
              min={10}
              max={900}
              value={form.segment_seconds}
              onChange={(e) =>
                setForm({ ...form, segment_seconds: Number(e.target.value) })
              }
            />
          </label>
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? <Loader2 size={16} className="spin" /> : <CloudUpload size={16} />}
            Upload and analyze
          </button>
        </form>
        {error && <p className="form-error">{error}</p>}
        {notice && <p className="form-notice">{notice}</p>}
        <footer>
          Segments run the same deterministic triage as fixture footage. Only
          night segments can raise an event.
        </footer>
      </section>

      <section className="job-list">
        <header className="section-heading">
          <div>
            <span className="eyebrow">Pipeline</span>
            <h3>Ingest jobs</h3>
          </div>
        </header>
        {jobs.length === 0 && <p className="chart-empty">No ingest job has run yet.</p>}
        {jobs.map((job) => (
          <article className={`job-card ${job.status}`} key={job.job_id}>
            <div className="job-head">
              {job.status === "complete" && <CheckCircle2 size={17} />}
              {job.status === "failed" && <TriangleAlert size={17} />}
              {(job.status === "running" || job.status === "queued") && (
                <Loader2 size={17} className="spin" />
              )}
              <strong>{job.source_name}</strong>
              <span className="job-status">{job.status}</span>
            </div>
            <div className="job-meta">
              <span>
                {job.completed_segments}/{job.total_segments || "?"} segments
              </span>
              <span>{job.detection_count} motion regions</span>
              <span>{job.event_ids.length} events</span>
              <span>analyzer: {job.analyzer}</span>
              {job.probe && (
                <span>
                  {job.probe.width}×{job.probe.height} ·{" "}
                  {Math.round(job.probe.duration_seconds)}s
                </span>
              )}
            </div>
            {job.rules_fired.length > 0 && (
              <div className="job-rules">
                {[...new Set(job.rules_fired)].map((rule) => (
                  <span key={rule} className="mono">
                    {rule}
                  </span>
                ))}
              </div>
            )}
            {job.data_gap_ids.length > 0 && (
              <p className="job-gap">
                {job.data_gap_ids.length} segment(s) recorded a data gap rather than
                a result.
              </p>
            )}
            {job.error && <p className="form-error">{job.error}</p>}
          </article>
        ))}
      </section>
    </div>
  );
}

export default IngestPanel;
