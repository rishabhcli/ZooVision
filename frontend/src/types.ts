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
  detections?: DetectionItem[];
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

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** A measured motion region. Never a species or behavior classification. */
export interface DetectionItem {
  detection_id: string;
  chunk_id: string;
  track_id: string;
  video_seconds: number;
  box: BoundingBox;
  score: number;
  source: string;
}

export interface TimelineEvent {
  event_id: string;
  animal_name: string;
  behavior: string;
  severity: Severity;
  rule_fired: string | null;
  ack_state: string | null;
  start_ts: string;
  end_ts: string;
  start_seconds: number;
  end_seconds: number;
}

export interface TimelineObservation {
  observation_id: string;
  behavior: string;
  evidence: string;
  provider: string;
  evidence_kind: string;
  start_seconds: number;
  end_seconds: number;
}

export interface VideoSource {
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
}

export interface VideoTrack {
  source_path: string;
  media_url: string;
  chunks: {
    chunk_id: string;
    camera_id: string;
    start_ts: string;
    end_ts: string;
    source_offset_seconds: number;
    status: string;
  }[];
  detections: DetectionItem[];
  events: TimelineEvent[];
  observations: TimelineObservation[];
}

export interface GraphNodeItem {
  id: string;
  label: string;
  caption: string;
  properties: Record<string, string | number | boolean | null>;
  severity: Severity | null;
  size: number;
}

export interface GraphRelationshipItem {
  id: string;
  from: string;
  to: string;
  caption: string;
}

export interface GraphPayload {
  nodes: GraphNodeItem[];
  relationships: GraphRelationshipItem[];
  enclosures: string[];
  scope: string | null;
  counts: Record<string, number>;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  cited_ids: string[];
  uncertainty: string[];
  mode: string;
  model: string | null;
  context_record_count: number;
}

export interface IngestSegment {
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
}

export interface IngestJobState {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
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
    frame_rate: number;
  } | null;
  error: string | null;
}
