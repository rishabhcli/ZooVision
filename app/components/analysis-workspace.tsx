"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Check,
  CircleAlert,
  FileText,
  Film,
  LoaderCircle,
  PawPrint,
  Play,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  Upload,
  Video,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type DashboardPayload,
  type IngestJob,
  type ReadinessPayload,
  type VideoSource,
  type VideoTrack,
} from "../lib/api";

type FeedItem = {
  id: string;
  kind: "observation" | "event";
  start: number;
  end: number;
  title: string;
  detail: string;
  source: string;
  severity?: string;
  rule?: string;
};

const TERMINAL_JOB_STATES = new Set(["complete", "failed"]);

function titleCase(value: string | null | undefined) {
  if (!value) return "Not recorded";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function duration(value: number) {
  const seconds = Math.max(0, Math.round(value));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function jobProgress(job: IngestJob) {
  if (job.status === "complete") return 100;
  if (!job.total_segments) return 3;
  return Math.max(3, Math.round((job.completed_segments / job.total_segments) * 100));
}

export function AnalysisWorkspace() {
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null);
  const [videos, setVideos] = useState<VideoSource[]>([]);
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [readiness, setReadiness] = useState<ReadinessPayload | null>(null);
  const [sourcePath, setSourcePath] = useState("");
  const [track, setTrack] = useState<VideoTrack | null>(null);
  const [selectedItemId, setSelectedItemId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [showIngest, setShowIngest] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [briefingReady, setBriefingReady] = useState(false);
  const [uploadAnimalId] = useState(
    () => `animal-upload-${Math.random().toString(36).slice(2, 9)}`,
  );

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const [dashboardPayload, videoPayload, jobPayload, readinessPayload] =
        await Promise.all([
          api.dashboard(),
          api.videos(),
          api.ingestJobs(),
          api.readiness(),
        ]);
      setDashboard(dashboardPayload);
      setVideos(videoPayload.videos);
      setJobs(jobPayload.jobs);
      setReadiness(readinessPayload);
      setSourcePath((current) => {
        if (current && videoPayload.videos.some((video) => video.source_path === current)) {
          return current;
        }
        return videoPayload.videos[0]?.source_path ?? "";
      });
      setLoadError(null);
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : "Analysis service unavailable");
    } finally {
      if (!quiet) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(true), 3_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    if (!sourcePath) return;
    let active = true;
    api
      .videoTrack(sourcePath)
      .then((payload) => {
        if (active) setTrack(payload);
      })
      .catch((caught: unknown) => {
        if (active) {
          setLoadError(
            caught instanceof Error ? caught.message : "Unable to load analyzed source",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [sourcePath, jobs]);

  const selectedVideo = videos.find((video) => video.source_path === sourcePath) ?? null;
  const activeJobs = jobs.filter((job) => !TERMINAL_JOB_STATES.has(job.status));
  const feed = useMemo<FeedItem[]>(() => {
    if (!track) return [];
    return [
      ...track.observations.map((observation) => ({
        id: observation.observation_id,
        kind: "observation" as const,
        start: observation.start_seconds,
        end: observation.end_seconds,
        title: observation.activity_label || titleCase(observation.behavior),
        detail: observation.evidence,
        source: `${observation.provider} · ${titleCase(observation.evidence_kind)}`,
      })),
      ...track.events.map((event) => ({
        id: event.event_id,
        kind: "event" as const,
        start: event.start_seconds,
        end: event.end_seconds,
        title: `${titleCase(event.behavior)} · ${event.severity}`,
        detail: event.action
          ? `Constrained response: ${titleCase(event.action)}`
          : "No response action recorded",
        source: "Deterministic Python triage",
        severity: event.severity,
        rule: event.rule_fired,
      })),
    ].sort((left, right) => left.start - right.start || left.kind.localeCompare(right.kind));
  }, [track]);
  const selectedItem =
    feed.find((item) => item.id === selectedItemId) ?? feed[0] ?? null;
  const totalObservations = videos.reduce((sum, video) => sum + video.observation_count, 0);
  const totalDetections = videos.reduce((sum, video) => sum + video.detection_count, 0);
  const providerReady = Boolean(
    readiness?.providers.twelvelabs?.configured &&
      readiness?.providers.twelvelabs?.enabled,
  );

  async function submitIngest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("video");
    if (!(file instanceof File) || !file.size) {
      setIngestError("Choose a video file to analyze.");
      return;
    }
    setSubmitting(true);
    setIngestError(null);
    try {
      const uploaded = await api.uploadVideo(file);
      await api.startIngest({
        source_name: uploaded.source_name,
        animal_id: String(data.get("animal_id")),
        animal_name: String(data.get("animal_name")),
        species: String(data.get("species")),
        enclosure_id: String(data.get("enclosure_id")),
        camera_id: String(data.get("camera_id")),
        shift_mode: data.get("shift_mode") === "day" ? "day" : "night",
        segment_seconds: 120,
        max_segments: 240,
        use_provider: data.get("use_provider") === "on",
      });
      form.reset();
      setShowIngest(false);
      await refresh();
    } catch (caught) {
      setIngestError(caught instanceof Error ? caught.message : "Ingest could not start");
    } finally {
      setSubmitting(false);
    }
  }

  function openInMonitor(seconds: number) {
    if (!sourcePath) return;
    sessionStorage.setItem(
      "zoovision:pending-moment",
      JSON.stringify({ sourcePath, seconds }),
    );
    window.location.assign("/monitor");
  }

  if (!dashboard && loadError) {
    return (
      <div className="analysis-state" role="alert">
        <AlertTriangle size={22} />
        <strong>Analysis service unavailable</strong>
        <p>{loadError}</p>
        <button type="button" onClick={() => void refresh()}>
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="analysis-state" role="status">
        <LoaderCircle className="spin" size={24} />
        <strong>Connecting analysis records</strong>
        <p>Loading video sources, observations, detections, and ingest jobs.</p>
      </div>
    );
  }

  return (
    <div className="live-analysis-page">
      <header className="analysis-commandbar">
        <div>
          <span className="analysis-live-dot" data-active={activeJobs.length > 0} />
          <span>{activeJobs.length ? "Analysis running" : "Analysis records live"}</span>
          <small>Auto-refreshes every 3 seconds</small>
        </div>
        <label className="analysis-source-select">
          <Video size={14} />
          <span>Analyzed source</span>
          <select
            value={sourcePath}
            onChange={(event) => {
              setSourcePath(event.target.value);
              setSelectedItemId("");
            }}
            disabled={!videos.length}
            aria-label="Analyzed video source"
          >
            {!videos.length && <option value="">No analyzed videos yet</option>}
            {videos.map((video) => (
              <option value={video.source_path} key={video.source_path}>
                {video.camera_id} · {video.animal_names.join(", ") || video.source_path}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="analysis-refresh-button"
          onClick={() => void refresh()}
          disabled={refreshing}
          title="Refresh analysis"
        >
          <RefreshCw className={refreshing ? "spin" : undefined} size={15} />
        </button>
        <button
          type="button"
          className="primary-button analysis-upload-button"
          onClick={() => setShowIngest((current) => !current)}
          aria-expanded={showIngest}
        >
          <Upload size={14} />
          Analyze video
        </button>
      </header>

      {showIngest && (
        <form className="analysis-ingest-form" onSubmit={submitIngest}>
          <header>
            <div>
              <strong>New video analysis</strong>
              <span>Upload, segment, localize, extract observations, then run deterministic triage.</span>
            </div>
            <button type="button" onClick={() => setShowIngest(false)} aria-label="Close upload">
              <span aria-hidden="true">×</span>
            </button>
          </header>
          <label className="analysis-file-input">
            <Film size={18} />
            <span>
              <strong>Video file</strong>
              <small>MP4, WebM, MOV, MKV, MPEG, or AVI · up to 2 GB</small>
            </span>
            <input name="video" type="file" accept="video/*,.mkv" required />
          </label>
          <div className="analysis-form-grid">
            <label>
              Animal name
              <input name="animal_name" defaultValue="New animal" required />
            </label>
            <label>
              Animal ID
              <input name="animal_id" defaultValue={uploadAnimalId} required />
            </label>
            <label>
              Species
              <input name="species" defaultValue="Unspecified" required />
            </label>
            <label>
              Enclosure
              <input name="enclosure_id" defaultValue="ENC-UPLOAD" required />
            </label>
            <label>
              Camera
              <input name="camera_id" defaultValue="CAM-UPLOAD" required />
            </label>
            <label>
              Shift
              <select name="shift_mode" defaultValue="night">
                <option value="night">Night · eligible for rule events</option>
                <option value="day">Day · baseline context only</option>
              </select>
            </label>
          </div>
          <footer>
            <label className="analysis-provider-toggle">
              <input
                name="use_provider"
                type="checkbox"
                defaultChecked={providerReady}
                disabled={!providerReady}
              />
              <span>
                <strong>TwelveLabs behavior analysis</strong>
                <small>
                  {providerReady
                    ? "Configured and enabled; motion localization also runs."
                    : "Unavailable; measured motion analysis will still run."}
                </small>
              </span>
            </label>
            {ingestError && <p role="alert">{ingestError}</p>}
            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? <LoaderCircle className="spin" size={14} /> : <Play size={14} />}
              {submitting ? "Uploading…" : "Start analysis"}
            </button>
          </footer>
        </form>
      )}

      <section className="analysis-heading">
        <div>
          <span>Overnight evidence pipeline</span>
          <h1>Video analysis</h1>
          <p>
            Live structured observations, spatial detections, deterministic rule
            results, and coverage gaps from the active source.
          </p>
        </div>
        <button
          type="button"
          onClick={() =>
            api.morningReport().then(() => setBriefingReady(true))
          }
        >
          {briefingReady ? <Check size={14} /> : <FileText size={14} />}
          {briefingReady ? "Briefing ready" : "Prepare briefing"}
        </button>
      </section>

      <section className="analysis-metrics" aria-label="Analysis summary">
        <article>
          <ScanLine size={18} />
          <div><span>Observations</span><strong>{totalObservations}</strong><small>Structured evidence records</small></div>
        </article>
        <article>
          <Activity size={18} />
          <div><span>Spatial detections</span><strong>{totalDetections}</strong><small>Measured across all sources</small></div>
        </article>
        <article>
          <ShieldCheck size={18} />
          <div><span>Rule events</span><strong>{dashboard.events.length}</strong><small>Deterministic, non-NONE</small></div>
        </article>
        <article>
          <CircleAlert size={18} />
          <div><span>Coverage gaps</span><strong>{dashboard.data_gaps.length}</strong><small>Explicitly recorded</small></div>
        </article>
      </section>

      {jobs.length > 0 && (
        <section className="analysis-jobs" aria-label="Video processing jobs">
          <header>
            <div><span>Pipeline activity</span><strong>Recent analysis jobs</strong></div>
            <small>{activeJobs.length ? `${activeJobs.length} active` : "All jobs settled"}</small>
          </header>
          <div>
            {jobs.slice(0, 4).map((job) => (
              <article key={job.job_id} data-status={job.status}>
                <span className="job-state-icon">
                  {TERMINAL_JOB_STATES.has(job.status) ? (
                    job.status === "failed" ? <AlertTriangle size={15} /> : <Check size={15} />
                  ) : <LoaderCircle className="spin" size={15} />}
                </span>
                <div>
                  <strong>{job.source_name}</strong>
                  <span>
                    {titleCase(job.status)} · {job.completed_segments}/{job.total_segments || "?"} segments
                    · {job.detection_count} detections
                  </span>
                  <i><b style={{ width: `${jobProgress(job)}%` }} /></i>
                  {job.error && <small>{job.error}</small>}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="analysis-work-grid">
        <article className="analysis-panel analysis-feed">
          <header>
            <div>
              <span>Active source</span>
              <h2>{selectedVideo?.camera_id ?? "No analyzed source"}</h2>
            </div>
            <small>
              {selectedVideo
                ? `${selectedVideo.chunk_count} chunks · ${selectedVideo.observation_count} observations`
                : "Upload a video to begin"}
            </small>
          </header>
          {feed.length ? (
            <div className="analysis-feed-list">
              {feed.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  data-kind={item.kind}
                  data-selected={selectedItem?.id === item.id}
                  onClick={() => setSelectedItemId(item.id)}
                >
                  <time>{duration(item.start)}</time>
                  <i />
                  <span>
                    <strong>{item.title}</strong>
                    <small>{item.detail}</small>
                    <em>{item.source}</em>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="analysis-empty">
              <BarChart3 size={24} />
              <strong>No analysis records for this source yet</strong>
              <p>
                Processing progress will appear above. Observations are shown here
                as each completed segment is persisted.
              </p>
            </div>
          )}
        </article>

        <aside className="analysis-detail-column">
          <article className="analysis-panel analysis-selected">
            <header>
              <div><span>Selected record</span><h2>{selectedItem ? titleCase(selectedItem.kind) : "Waiting for evidence"}</h2></div>
              {selectedItem?.severity && <b data-severity={selectedItem.severity}>{selectedItem.severity}</b>}
            </header>
            {selectedItem ? (
              <>
                <div className="analysis-record-summary">
                  {selectedItem.kind === "event" ? <ShieldCheck size={20} /> : <Activity size={20} />}
                  <div>
                    <strong>{selectedItem.title}</strong>
                    <p>{selectedItem.detail}</p>
                  </div>
                </div>
                <dl>
                  <div><dt>Window</dt><dd>{duration(selectedItem.start)}–{duration(selectedItem.end)}</dd></div>
                  <div><dt>Source</dt><dd>{selectedItem.source}</dd></div>
                  <div><dt>Rule fired</dt><dd>{selectedItem.rule ?? "None"}</dd></div>
                  <div><dt>Camera</dt><dd>{selectedVideo?.camera_id ?? "Not recorded"}</dd></div>
                  <div><dt>Animal</dt><dd>{selectedVideo?.animal_names.join(", ") || "Unassigned"}</dd></div>
                </dl>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => openInMonitor(selectedItem.start)}
                >
                  <Play size={14} />
                  Open this moment in Monitor
                </button>
              </>
            ) : (
              <div className="analysis-empty compact">
                <Activity size={22} />
                <p>Select an analyzed source or start a new analysis.</p>
              </div>
            )}
          </article>

          <article className="analysis-panel analysis-animal-status">
            <header><div><span>Monitored subjects</span><h2>Animal status</h2></div><PawPrint size={16} /></header>
            <div>
              {dashboard.animals.map((animal) => {
                const eventCount = dashboard.events.filter(
                  (event) => event.animal_id === animal.animal_id,
                ).length;
                return (
                  <article key={animal.animal_id}>
                    <span>{animal.name.slice(0, 1)}</span>
                    <div>
                      <strong>{animal.name}</strong>
                      <small>{animal.species} · {animal.enclosure_id}</small>
                    </div>
                    <em>{eventCount ? `${eventCount} event${eventCount === 1 ? "" : "s"}` : "No rule event"}</em>
                  </article>
                );
              })}
            </div>
          </article>
        </aside>
      </section>

      {loadError && (
        <div className="analysis-inline-error" role="status">
          <AlertTriangle size={14} />
          Last refresh failed: {loadError}
        </div>
      )}
    </div>
  );
}
