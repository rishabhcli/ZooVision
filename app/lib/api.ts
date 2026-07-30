export type GraphNodeItem = {
  id: string;
  label: string;
  caption: string;
  properties: Record<string, unknown>;
  severity: string | null;
  size: number;
};

export type GraphRelationshipItem = {
  id: string;
  from: string;
  to: string;
  caption: string;
};

export type GraphPayload = {
  source: "neo4j";
  nodes: GraphNodeItem[];
  relationships: GraphRelationshipItem[];
  enclosures: string[];
  scope: string | null;
  counts: Record<string, number>;
};

export type DashboardAnimal = {
  animal_id: string;
  name: string;
  species: string;
  enclosure_id: string;
  baseline_state: string;
  baseline_days: number;
  event_count: number;
};

export type DashboardEvent = {
  event_id: string;
  animal_id: string;
  animal_name: string;
  enclosure_id: string;
  behavior: string;
  severity: string;
  rule_fired: string;
  rule_version: string;
  action: string | null;
  start_ts: string;
  end_ts: string;
  confidence: number;
  review_state: string;
  alert_id: string | null;
  ack_state: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  media_url?: string;
  media_offset_seconds?: number;
  evidence_kind?: string;
};

export type DashboardPayload = {
  animals: DashboardAnimal[];
  events: DashboardEvent[];
  data_gaps: Array<Record<string, unknown>>;
  mode: { fixture: boolean; delivery: string };
};

export type VideoSource = {
  source_path: string;
  media_url: string;
  enclosure_id: string;
  camera_id: string;
  chunk_count: number;
  first_start_ts: string;
  last_end_ts: string;
  detection_count: number;
  observation_count: number;
  event_count: number;
  animal_names: string[];
  animal_species: string[];
};

export type VideoDetection = {
  detection_id: string;
  track_id: string;
  video_seconds: number;
  score: number;
  source: string;
  label: string | null;
  class_id: number | null;
  model: string | null;
  box: { x: number; y: number; width: number; height: number };
};

export type VideoTrack = {
  source_path: string;
  media_url: string;
  chunks: Array<Record<string, unknown>>;
  detections: VideoDetection[];
  events: Array<{
    event_id: string;
    animal_id: string;
    animal_name: string;
    enclosure_id: string;
    behavior: string;
    severity: string;
    rule_fired: string;
    rule_version: string;
    action: string | null;
    confidence: number;
    review_state: string;
    ack_state: string | null;
    start_ts: string;
    end_ts: string;
    start_seconds: number;
    end_seconds: number;
  }>;
  observations: Array<{
    observation_id: string;
    behavior: string;
    evidence: string;
    provider: string;
    evidence_kind: string;
    activity_label: string | null;
    start_seconds: number;
    end_seconds: number;
  }>;
};

export type ReadinessPayload = {
  status: string;
  environment: string;
  fixture_mode: boolean;
  delivery_mode: string;
  providers: Record<
    string,
    {
      status: string;
      configured: boolean;
      enabled: boolean;
      read_connected?: boolean;
      write_enabled?: boolean;
    }
  >;
};

export type IngestSegment = {
  index: number;
  chunk_id: string;
  start_ts: string;
  duration_seconds: number;
  route: string;
  observation_count: number;
  detection_count: number;
  event_ids: string[];
  rules_fired: string[];
  data_gap_id: string | null;
};

export type IngestJob = {
  job_id: string;
  status: string;
  source_name: string;
  animal_id: string;
  enclosure_id: string;
  created_at: string;
  updated_at: string;
  analyzer: string;
  total_segments: number;
  completed_segments: number;
  detection_count: number;
  event_ids: string[];
  rules_fired: string[];
  data_gap_ids: string[];
  segments: IngestSegment[];
  probe: {
    duration_seconds: number;
    width: number;
    height: number;
    fps: number;
    codec: string;
    has_audio: boolean;
  } | null;
  error: string | null;
};

export type ChatMoment = {
  observation_id: string;
  source_path: string;
  start_seconds: number;
  end_seconds: number;
  label: string;
  camera_id: string;
  enclosure_id: string;
  animal_name: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(payload?.detail || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export const api = {
  readiness: () => request<ReadinessPayload>("/api/readiness"),
  dashboard: () => request<DashboardPayload>("/api/dashboard"),
  graph: (enclosureId?: string | null) =>
    request<GraphPayload>(
      enclosureId
        ? `/api/graph?enclosure_id=${encodeURIComponent(enclosureId)}`
        : "/api/graph",
    ),
  videos: () => request<{ videos: VideoSource[] }>("/api/videos"),
  videoTrack: (sourcePath: string) =>
    request<VideoTrack>(
      `/api/videos/track?source_path=${encodeURIComponent(sourcePath)}`,
    ),
  morningReport: () => request<Record<string, unknown>>("/api/morning-report"),
  ingestJobs: () => request<{ jobs: IngestJob[] }>("/api/ingest/jobs"),
  uploadVideo: async (file: File) => {
    const chunkSize = 2 * 1024 * 1024;
    const chunkCount = Math.ceil(file.size / chunkSize);
    const uploadId = crypto.randomUUID();
    let completed:
      | { source_name: string; bytes: number; media_url: string }
      | undefined;

    for (let index = 0; index < chunkCount; index += 1) {
      const body = new FormData();
      body.append(
        "file",
        file.slice(index * chunkSize, Math.min(file.size, (index + 1) * chunkSize)),
        `${file.name}.part`,
      );
      body.append("upload_id", uploadId);
      body.append("filename", file.name);
      body.append("chunk_index", String(index));
      body.append("chunk_count", String(chunkCount));
      body.append("total_bytes", String(file.size));
      const response = await fetch("/api/ingest/upload/chunks", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(payload?.detail || `Upload failed (${response.status})`);
      }
      const payload = (await response.json()) as
        | { complete: false }
        | {
            complete: true;
            source_name: string;
            bytes: number;
            media_url: string;
          };
      if (payload.complete) completed = payload;
    }
    if (!completed) throw new Error("Upload did not complete");
    return completed;
  },
  startIngest: (payload: {
    source_name: string;
    animal_id: string;
    animal_name: string;
    species: string;
    enclosure_id: string;
    camera_id: string;
    shift_mode: "day" | "night";
    segment_seconds: number;
    max_segments: number;
    use_provider: boolean;
  }) =>
    request<IngestJob>("/api/ingest/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  chat: (messages: Array<{ role: "user" | "assistant"; content: string }>) =>
    request<{
      answer: string;
      cited_ids: string[];
      uncertainty: string[];
      mode: string;
      context_record_count: number;
      moments: ChatMoment[];
    }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ messages }),
    }),
  recordOutcome: (
    eventId: string,
    resolution: string,
    enteredBy = "ZooVision operator",
  ) =>
    request<{ status: string; outcome_id: string }>(
      `/api/events/${encodeURIComponent(eventId)}/outcomes`,
      {
        method: "POST",
        body: JSON.stringify({
          resolution,
          entered_by: enteredBy,
          note: "Recorded from the evidence review workspace.",
        }),
      },
    ),
};
