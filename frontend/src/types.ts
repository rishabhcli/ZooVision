export type Severity = "CRITICAL" | "HIGH" | "MODERATE" | "LOW" | "NONE";

export interface Animal {
  animal_id: string;
  name: string;
  species: string;
  enclosure_id: string;
  baseline_state: "learning" | "shadow" | "active" | "paused";
  baseline_days: number;
  event_count: number;
  latest_severity: Severity | null;
}

export interface EventItem {
  event_id: string;
  animal_id: string;
  animal_name: string;
  species: string;
  enclosure_id: string;
  behavior: string;
  start_ts: string;
  end_ts: string;
  severity: Severity;
  rule_fired: string;
  action: string;
  confidence: number;
  explanation_facts: string[];
  source_observation_ids: string[];
  rule_version: string;
  review_state: string;
  baseline_state: string;
  alert_id: string;
  delivery_status: string;
  ack_state: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  media_url?: string;
  media_offset_seconds?: number;
  evidence_kind?: string;
}

export interface DataGap {
  gap_id: string;
  enclosure_id: string;
  start_ts: string;
  end_ts: string;
  reason: string;
  detail: string;
}

export interface Dashboard {
  animals: Animal[];
  events: EventItem[];
  data_gaps: DataGap[];
  mode: { fixture: boolean; delivery: string };
}

export interface SourceEvidence {
  observation_id: string;
  chunk_id: string;
  start_ts: string;
  end_ts: string;
  evidence: string;
  evidence_kind: string;
  provider: string;
  provider_model: string;
  media_url: string;
  source_offset_seconds: number;
  camera_id: string;
}

export interface EventDetail extends EventItem {
  sources: SourceEvidence[];
  outcomes: {
    outcome_id: string;
    resolution: string;
    note: string | null;
    entered_by: string;
    created_at: string;
  }[];
}

export interface Readiness {
  status: string;
  environment: string;
  fixture_mode: boolean;
  delivery_mode: string;
  external_delivery_ready: boolean;
  providers: Record<
    string,
    { configured: boolean; enabled: boolean; status: string }
  >;
  retention_days: Record<string, number>;
}

export interface MorningReport {
  animals: (Animal & { events: EventItem[] })[];
  data_gaps: DataGap[];
  summary: {
    animals_monitored: number;
    events: number;
    data_gaps: number;
  };
}
