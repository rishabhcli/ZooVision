import type {
  Dashboard,
  EventDetail,
  MorningReport,
  Readiness
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
  reset: () => request("/api/demo/reset", { method: "POST" })
};
