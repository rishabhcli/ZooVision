import type {
  ChatResponse,
  ChatTurn,
  Dashboard,
  EventDetail,
  GraphPayload,
  IngestJobState,
  MorningReport,
  Readiness,
  VideoSource,
  VideoTrack
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<Dashboard>("/api/dashboard"),
  event: (eventId: string) => request<EventDetail>(`/api/events/${eventId}`),
  readiness: () => request<Readiness>("/api/readiness"),
  report: () => request<MorningReport>("/api/morning-report"),
  acknowledge: (alertId: string, keeper: string) =>
    request(`/api/alerts/${alertId}/ack`, {
      method: "POST",
      body: JSON.stringify({ keeper })
    }),
  outcome: (
    eventId: string,
    resolution: string,
    note: string,
    enteredBy: string
  ) =>
    request(`/api/events/${eventId}/outcomes`, {
      method: "POST",
      body: JSON.stringify({
        resolution,
        note: note || null,
        entered_by: enteredBy
      })
    }),
  baseline: (animalId: string, state: string) =>
    request(`/api/animals/${animalId}/baseline`, {
      method: "POST",
      body: JSON.stringify({ state })
    }),
  reset: () => request("/api/demo/reset", { method: "POST" }),
  graph: (enclosureId?: string | null) =>
    request<GraphPayload>(
      enclosureId
        ? `/api/graph?enclosure_id=${encodeURIComponent(enclosureId)}`
        : "/api/graph"
    ),
  chat: (
    messages: ChatTurn[],
    scope?: { enclosureId?: string | null; animalId?: string | null }
  ) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        messages,
        enclosure_id: scope?.enclosureId ?? null,
        animal_id: scope?.animalId ?? null
      })
    }),
  videos: () => request<{ videos: VideoSource[] }>("/api/videos"),
  videoTrack: (sourcePath: string) =>
    request<VideoTrack>(
      `/api/videos/track?source_path=${encodeURIComponent(sourcePath)}`
    ),
  ingestJobs: () => request<{ jobs: IngestJobState[] }>("/api/ingest/jobs"),
  ingestJob: (jobId: string) =>
    request<IngestJobState>(`/api/ingest/jobs/${jobId}`),
  startIngest: (payload: Record<string, unknown>) =>
    request<IngestJobState>("/api/ingest/jobs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  uploadVideo: async (file: File) => {
    const chunkSize = 2 * 1024 * 1024;
    const chunkCount = Math.ceil(file.size / chunkSize);
    const uploadId = crypto.randomUUID();
    let completed:
      | { source_name: string; bytes: number; media_url: string }
      | undefined;

    for (let index = 0; index < chunkCount; index += 1) {
      const form = new FormData();
      form.append(
        "file",
        file.slice(index * chunkSize, Math.min(file.size, (index + 1) * chunkSize)),
        `${file.name}.part`
      );
      form.append("upload_id", uploadId);
      form.append("filename", file.name);
      form.append("chunk_index", String(index));
      form.append("chunk_count", String(chunkCount));
      form.append("total_bytes", String(file.size));
      const response = await fetch("/api/ingest/upload/chunks", {
        method: "POST",
        body: form
      });
      if (!response.ok) {
        const body = await response
          .json()
          .catch(() => ({ detail: response.statusText }));
        throw new Error(body.detail || "Upload failed");
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
  }
};
