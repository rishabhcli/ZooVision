from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .domain import (
    BaselineProfile,
    DataGap,
    Detection,
    DetectionSource,
    EventRecord,
    Observation,
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS animals (
    animal_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    enclosure_id TEXT NOT NULL,
    baseline_state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS video_chunks (
    chunk_id TEXT PRIMARY KEY,
    enclosure_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_offset_seconds REAL NOT NULL DEFAULT 0,
    content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES video_chunks(chunk_id) ON DELETE CASCADE,
    animal_id TEXT NOT NULL REFERENCES animals(animal_id),
    behavior TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_model TEXT NOT NULL,
    provider_item_id TEXT,
    evidence_kind TEXT NOT NULL,
    activity_label TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    animal_id TEXT NOT NULL REFERENCES animals(animal_id),
    enclosure_id TEXT NOT NULL,
    behavior TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    severity TEXT NOT NULL,
    rule_fired TEXT,
    action TEXT,
    confidence REAL NOT NULL,
    baseline_delta_z REAL,
    explanation_facts_json TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    shift_mode TEXT NOT NULL,
    review_state TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_sources (
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    observation_id TEXT NOT NULL,
    PRIMARY KEY (event_id, observation_id)
);

CREATE TABLE IF NOT EXISTS event_narratives (
    event_id TEXT PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    headline TEXT NOT NULL,
    factual_summary TEXT NOT NULL,
    uncertainty_json TEXT NOT NULL,
    cited_source_ids_json TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS baseline_profiles (
    animal_id TEXT NOT NULL REFERENCES animals(animal_id),
    behavior TEXT NOT NULL,
    state TEXT NOT NULL,
    duration_mean REAL,
    duration_std REAL,
    frequency_mean REAL,
    frequency_std REAL,
    n_day_shifts INTEGER NOT NULL,
    window_size INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (animal_id, behavior)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    channel TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    ack_state TEXT NOT NULL,
    sent_at TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    delivery_attempts_json TEXT NOT NULL DEFAULT '[]'
    ,scheduler_schedule_name TEXT
    ,scheduler_schedule_arn TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    resolution TEXT NOT NULL,
    note TEXT,
    entered_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_gaps (
    gap_id TEXT PRIMARY KEY,
    enclosure_id TEXT NOT NULL,
    chunk_id TEXT,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    reason TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    source_name TEXT NOT NULL,
    animal_id TEXT NOT NULL,
    enclosure_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ingest_jobs_created ON ingest_jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS detections (
    detection_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES video_chunks(chunk_id) ON DELETE CASCADE,
    track_id TEXT NOT NULL,
    relative_seconds REAL NOT NULL,
    box_x REAL NOT NULL,
    box_y REAL NOT NULL,
    box_width REAL NOT NULL,
    box_height REAL NOT NULL,
    score REAL NOT NULL,
    source TEXT NOT NULL,
    label TEXT,
    class_id INTEGER,
    model TEXT
);

CREATE INDEX IF NOT EXISTS idx_detections_chunk_time
    ON detections(chunk_id, relative_seconds);
CREATE INDEX IF NOT EXISTS idx_events_animal_start ON events(animal_id, start_ts);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_observations_chunk ON observations(chunk_id);
"""


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_detection_provenance(connection)
            self._migrate_observation_activity(connection)
            self._migrate_alert_scheduler(connection)

    @staticmethod
    def _migrate_detection_provenance(connection: sqlite3.Connection) -> None:
        """Add provenance columns to databases created before labeled detections."""
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(detections)")}
        for name, sql_type in (
            ("label", "TEXT"),
            ("class_id", "INTEGER"),
            ("model", "TEXT"),
        ):
            if name not in columns:
                connection.execute(f"ALTER TABLE detections ADD COLUMN {name} {sql_type}")

    @staticmethod
    def _migrate_observation_activity(connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(observations)")}
        if "activity_label" not in columns:
            connection.execute("ALTER TABLE observations ADD COLUMN activity_label TEXT")

    @staticmethod
    def _migrate_alert_scheduler(connection: sqlite3.Connection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(alerts)")}
        for name in ("scheduler_schedule_name", "scheduler_schedule_arn"):
            if name not in columns:
                connection.execute(f"ALTER TABLE alerts ADD COLUMN {name} TEXT")

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upsert_animal(
        self,
        *,
        animal_id: str,
        name: str,
        species: str,
        enclosure_id: str,
        baseline_state: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO animals(animal_id, name, species, enclosure_id, baseline_state)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(animal_id) DO UPDATE SET
                    name = excluded.name,
                    species = excluded.species,
                    enclosure_id = excluded.enclosure_id,
                    baseline_state = excluded.baseline_state
                """,
                (animal_id, name, species, enclosure_id, baseline_state),
            )

    def save_event(self, event: EventRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events(
                    event_id, animal_id, enclosure_id, behavior, start_ts, end_ts,
                    severity, rule_fired, action, confidence, baseline_delta_z,
                    explanation_facts_json, rule_version, shift_mode, review_state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    start_ts = excluded.start_ts,
                    end_ts = excluded.end_ts,
                    severity = excluded.severity,
                    rule_fired = excluded.rule_fired,
                    action = excluded.action,
                    confidence = excluded.confidence,
                    baseline_delta_z = excluded.baseline_delta_z,
                    explanation_facts_json = excluded.explanation_facts_json,
                    rule_version = excluded.rule_version,
                    shift_mode = excluded.shift_mode,
                    review_state = excluded.review_state
                """,
                (
                    event.event_id,
                    event.animal_id,
                    event.enclosure_id,
                    event.behavior.value,
                    event.start_ts.isoformat(),
                    event.end_ts.isoformat(),
                    event.severity.value,
                    event.rule_fired,
                    event.action.value if event.action else None,
                    event.confidence,
                    event.baseline_delta_z,
                    json.dumps(event.explanation_facts),
                    event.rule_version,
                    event.shift_mode.value,
                    event.review_state.value,
                    event.created_at.isoformat(),
                ),
            )
            connection.execute("DELETE FROM event_sources WHERE event_id = ?", (event.event_id,))
            connection.executemany(
                "INSERT INTO event_sources(event_id, observation_id) VALUES (?, ?)",
                (
                    (event.event_id, source_id)
                    for source_id in sorted(set(event.source_observation_ids))
                ),
            )

    def upsert_video_chunk(
        self,
        *,
        chunk_id: str,
        enclosure_id: str,
        camera_id: str,
        start_ts: str,
        end_ts: str,
        source_path: str,
        source_offset_seconds: float,
        content_sha256: str,
        status: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO video_chunks(
                    chunk_id, enclosure_id, camera_id, start_ts, end_ts, source_path,
                    source_offset_seconds, content_sha256, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    status = excluded.status,
                    content_sha256 = excluded.content_sha256,
                    source_path = excluded.source_path
                """,
                (
                    chunk_id,
                    enclosure_id,
                    camera_id,
                    start_ts,
                    end_ts,
                    source_path,
                    source_offset_seconds,
                    content_sha256,
                    status,
                ),
            )

    def save_observation(self, observation: Observation) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO observations(
                    observation_id, chunk_id, animal_id, behavior, start_ts, end_ts,
                    confidence, evidence, provider, provider_model, provider_item_id,
                    evidence_kind, activity_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    confidence = excluded.confidence,
                    evidence = excluded.evidence,
                    provider_item_id = excluded.provider_item_id,
                    activity_label = excluded.activity_label
                """,
                (
                    observation.observation_id,
                    observation.chunk_id,
                    observation.animal_id,
                    observation.behavior.value,
                    observation.start_ts.isoformat(),
                    observation.end_ts.isoformat(),
                    observation.confidence,
                    observation.evidence,
                    observation.provider,
                    observation.provider_model,
                    observation.provider_item_id,
                    observation.evidence_kind.value,
                    observation.activity_label,
                ),
            )

    def observations_for_chunks(self, chunk_ids: Iterable[str]) -> list[Observation]:
        """Return normalized observations for an explicit completed-chunk set."""
        identifiers = sorted(set(chunk_ids))
        if not identifiers:
            return []
        placeholders = ",".join("?" for _ in identifiers)
        with self.connect() as connection:
            return [
                Observation.model_validate(dict(row))
                for row in connection.execute(
                    f"""
                    SELECT o.*, vc.enclosure_id
                    FROM observations o
                    JOIN video_chunks vc ON vc.chunk_id = o.chunk_id
                    WHERE o.chunk_id IN ({placeholders})
                    ORDER BY o.start_ts, o.end_ts, o.observation_id
                    """,
                    identifiers,
                )
            ]

    def save_ingest_job(self, job: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ingest_jobs(
                    job_id, status, source_name, animal_id, enclosure_id,
                    created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    job["job_id"],
                    job["status"],
                    job["source_name"],
                    job["animal_id"],
                    job["enclosure_id"],
                    job["created_at"],
                    job["updated_at"],
                    json.dumps(job),
                ),
            )

    def ingest_job(self, job_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM ingest_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def recent_ingest_jobs(self, limit: int = 20) -> list[dict]:
        bounded = max(1, min(limit, 200))
        with self.connect() as connection:
            return [
                json.loads(row["payload_json"])
                for row in connection.execute(
                    "SELECT payload_json FROM ingest_jobs ORDER BY created_at DESC LIMIT ?",
                    (bounded,),
                )
            ]

    def latest_ingest_jobs_by_source(self) -> dict[str, dict]:
        """Return the newest persisted job for each uploaded source name."""
        latest: dict[str, dict] = {}
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT source_name, payload_json
                FROM ingest_jobs
                ORDER BY created_at DESC, updated_at DESC
                """
            )
            for row in rows:
                latest.setdefault(row["source_name"], json.loads(row["payload_json"]))
        return latest

    def save_detections(self, detections: Iterable[Detection]) -> int:
        rows = self._detection_rows(detections)
        if not rows:
            return 0
        with self.connect() as connection:
            self._upsert_detection_rows(connection, rows)
        return len(rows)

    def replace_chunk_detections(
        self,
        chunk_id: str,
        detections: Iterable[Detection],
    ) -> int:
        """Atomically replace the spatial samples for one stable video chunk."""
        values = list(detections)
        if any(detection.chunk_id != chunk_id for detection in values):
            raise ValueError("every replacement detection must belong to the requested chunk")
        rows = self._detection_rows(values)
        with self.connect() as connection:
            connection.execute("DELETE FROM detections WHERE chunk_id = ?", (chunk_id,))
            self._upsert_detection_rows(connection, rows)
        return len(rows)

    def replace_chunk_motion_detections(
        self,
        chunk_id: str,
        detections: Iterable[Detection],
    ) -> int:
        """Atomically replace only motion samples, preserving every other source."""
        values = list(detections)
        if any(detection.chunk_id != chunk_id for detection in values):
            raise ValueError("every replacement detection must belong to the requested chunk")
        if any(detection.source is not DetectionSource.MOTION_REGION for detection in values):
            raise ValueError("motion replacement accepts only motion_region detections")
        rows = self._detection_rows(values)
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM detections WHERE chunk_id = ? AND source = ?",
                (chunk_id, DetectionSource.MOTION_REGION.value),
            )
            self._upsert_detection_rows(connection, rows)
        return len(rows)

    def replace_chunk_yolo_detections(
        self,
        chunk_id: str,
        detections: Iterable[Detection],
    ) -> int:
        """Atomically replace YOLO samples while preserving motion and other sources."""
        values = list(detections)
        if any(detection.chunk_id != chunk_id for detection in values):
            raise ValueError("every replacement detection must belong to the requested chunk")
        if any(detection.source is not DetectionSource.YOLOV8_OBJECT for detection in values):
            raise ValueError("YOLO replacement accepts only yolov8_object detections")
        rows = self._detection_rows(values)
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM detections WHERE chunk_id = ? AND source = ?",
                (chunk_id, DetectionSource.YOLOV8_OBJECT.value),
            )
            self._upsert_detection_rows(connection, rows)
        return len(rows)

    def replace_chunk_spatial_detections(
        self,
        chunk_id: str,
        detections: Iterable[Detection],
    ) -> int:
        """Atomically replace motion and YOLO samples for one video chunk."""
        values = list(detections)
        if any(detection.chunk_id != chunk_id for detection in values):
            raise ValueError("every replacement detection must belong to the requested chunk")
        allowed = {DetectionSource.MOTION_REGION, DetectionSource.YOLOV8_OBJECT}
        if any(detection.source not in allowed for detection in values):
            raise ValueError("spatial replacement accepts only motion_region and yolov8_object")
        rows = self._detection_rows(values)
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM detections
                WHERE chunk_id = ? AND source IN (?, ?)
                """,
                (
                    chunk_id,
                    DetectionSource.MOTION_REGION.value,
                    DetectionSource.YOLOV8_OBJECT.value,
                ),
            )
            self._upsert_detection_rows(connection, rows)
        return len(rows)

    @staticmethod
    def _detection_rows(detections: Iterable[Detection]) -> list[tuple]:
        return [
            (
                detection.detection_id,
                detection.chunk_id,
                detection.track_id,
                detection.relative_seconds,
                detection.box.x,
                detection.box.y,
                detection.box.width,
                detection.box.height,
                detection.score,
                detection.source.value,
                detection.label,
                detection.class_id,
                detection.model,
            )
            for detection in detections
        ]

    @staticmethod
    def _upsert_detection_rows(
        connection: sqlite3.Connection,
        rows: list[tuple],
    ) -> None:
        if rows:
            connection.executemany(
                """
                INSERT INTO detections(
                    detection_id, chunk_id, track_id, relative_seconds,
                    box_x, box_y, box_width, box_height, score, source,
                    label, class_id, model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(detection_id) DO UPDATE SET
                    track_id = excluded.track_id,
                    box_x = excluded.box_x,
                    box_y = excluded.box_y,
                    box_width = excluded.box_width,
                    box_height = excluded.box_height,
                    score = excluded.score,
                    source = excluded.source,
                    label = excluded.label,
                    class_id = excluded.class_id,
                    model = excluded.model
                """,
                rows,
            )

    def detections_for_chunk(self, chunk_id: str) -> list[dict]:
        with self.connect() as connection:
            return [
                {
                    "detection_id": row["detection_id"],
                    "chunk_id": row["chunk_id"],
                    "track_id": row["track_id"],
                    "relative_seconds": row["relative_seconds"],
                    "box": {
                        "x": row["box_x"],
                        "y": row["box_y"],
                        "width": row["box_width"],
                        "height": row["box_height"],
                    },
                    "score": row["score"],
                    "source": row["source"],
                    "label": row["label"],
                    "class_id": row["class_id"],
                    "model": row["model"],
                }
                for row in connection.execute(
                    """
                    SELECT * FROM detections
                    WHERE chunk_id = ?
                    ORDER BY relative_seconds, box_x
                    """,
                    (chunk_id,),
                )
            ]

    def save_baseline(self, profile: BaselineProfile) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO baseline_profiles(
                    animal_id, behavior, state, duration_mean, duration_std,
                    frequency_mean, frequency_std, n_day_shifts, window_size, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(animal_id, behavior) DO UPDATE SET
                    state = excluded.state,
                    duration_mean = excluded.duration_mean,
                    duration_std = excluded.duration_std,
                    frequency_mean = excluded.frequency_mean,
                    frequency_std = excluded.frequency_std,
                    n_day_shifts = excluded.n_day_shifts,
                    window_size = excluded.window_size,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.animal_id,
                    profile.behavior.value,
                    profile.state.value,
                    profile.duration_mean,
                    profile.duration_std,
                    profile.frequency_mean,
                    profile.frequency_std,
                    profile.n_day_shifts,
                    profile.window_size,
                    profile.updated_at.isoformat(),
                ),
            )

    def save_data_gap(self, gap: DataGap) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO data_gaps(
                    gap_id, enclosure_id, chunk_id, start_ts, end_ts, reason, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gap_id) DO UPDATE SET
                    reason = excluded.reason,
                    detail = excluded.detail
                """,
                (
                    gap.gap_id,
                    gap.enclosure_id,
                    gap.chunk_id,
                    gap.start_ts.isoformat(),
                    gap.end_ts.isoformat(),
                    gap.reason,
                    gap.detail,
                ),
            )

    def clear_provider_gaps(self, chunk_id: str) -> int:
        """Remove stale provider gaps after the same stable chunk succeeds."""
        with self.connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM data_gaps
                WHERE chunk_id = ? AND reason LIKE 'provider_%'
                """,
                (chunk_id,),
            )
            return cursor.rowcount

    def replace_chunk_provider_analysis(
        self,
        *,
        chunk_id: str,
        enclosure_id: str,
        camera_id: str,
        start_ts: str,
        end_ts: str,
        source_path: str,
        source_offset_seconds: float,
        content_sha256: str,
        observations: Iterable[Observation],
    ) -> int:
        """Atomically replace provider evidence while preserving spatial tracks.

        A provider-only retry must not erase the YOLO detections already saved
        for the stable chunk. The old provider gap is removed in the same
        transaction that writes the replacement observations and marks the
        chunk analyzed, so readers never see a false complete state.
        """
        values = list(observations)
        if any(observation.chunk_id != chunk_id for observation in values):
            raise ValueError("every replacement observation must belong to the requested chunk")

        with self.connect() as connection:
            event_ids = [
                row["event_id"]
                for row in connection.execute(
                    """
                    SELECT DISTINCT es.event_id
                    FROM event_sources es
                    JOIN observations o ON o.observation_id = es.observation_id
                    WHERE o.chunk_id = ?
                    """,
                    (chunk_id,),
                )
            ]
            for event_id in event_ids:
                connection.execute("DELETE FROM outcomes WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM alerts WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM event_narratives WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM events WHERE event_id = ?", (event_id,))

            connection.execute("DELETE FROM observations WHERE chunk_id = ?", (chunk_id,))
            connection.execute(
                """
                DELETE FROM data_gaps
                WHERE chunk_id = ? AND reason LIKE 'provider_%'
                """,
                (chunk_id,),
            )
            connection.execute(
                """
                INSERT INTO video_chunks(
                    chunk_id, enclosure_id, camera_id, start_ts, end_ts, source_path,
                    source_offset_seconds, content_sha256, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'analyzed')
                ON CONFLICT(chunk_id) DO UPDATE SET
                    enclosure_id = excluded.enclosure_id,
                    camera_id = excluded.camera_id,
                    start_ts = excluded.start_ts,
                    end_ts = excluded.end_ts,
                    source_path = excluded.source_path,
                    source_offset_seconds = excluded.source_offset_seconds,
                    content_sha256 = excluded.content_sha256,
                    status = excluded.status
                """,
                (
                    chunk_id,
                    enclosure_id,
                    camera_id,
                    start_ts,
                    end_ts,
                    source_path,
                    source_offset_seconds,
                    content_sha256,
                ),
            )
            connection.executemany(
                """
                INSERT INTO observations(
                    observation_id, chunk_id, animal_id, behavior, start_ts, end_ts,
                    confidence, evidence, provider, provider_model, provider_item_id,
                    evidence_kind, activity_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    confidence = excluded.confidence,
                    evidence = excluded.evidence,
                    provider_item_id = excluded.provider_item_id,
                    activity_label = excluded.activity_label
                """,
                (
                    (
                        observation.observation_id,
                        observation.chunk_id,
                        observation.animal_id,
                        observation.behavior.value,
                        observation.start_ts.isoformat(),
                        observation.end_ts.isoformat(),
                        observation.confidence,
                        observation.evidence,
                        observation.provider,
                        observation.provider_model,
                        observation.provider_item_id,
                        observation.evidence_kind.value,
                        observation.activity_label,
                    )
                    for observation in values
                ),
            )
            return len(values)

    def replace_chunk_analysis(self, chunk_id: str) -> None:
        """Remove superseded derived evidence before a successful reanalysis.

        Stable chunk IDs make reruns idempotent, but provider observations can
        change when a prompt or model improves. Replacing the derived rows keeps
        stale fallback observations, detections, and their rule events from
        surviving alongside the new provider result.
        """
        with self.connect() as connection:
            event_ids = [
                row["event_id"]
                for row in connection.execute(
                    """
                    SELECT DISTINCT es.event_id
                    FROM event_sources es
                    JOIN observations o ON o.observation_id = es.observation_id
                    WHERE o.chunk_id = ?
                    """,
                    (chunk_id,),
                )
            ]
            for event_id in event_ids:
                connection.execute("DELETE FROM outcomes WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM alerts WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM event_narratives WHERE event_id = ?", (event_id,))
                connection.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
            connection.execute("DELETE FROM observations WHERE chunk_id = ?", (chunk_id,))
            connection.execute("DELETE FROM detections WHERE chunk_id = ?", (chunk_id,))
            connection.execute("DELETE FROM data_gaps WHERE chunk_id = ?", (chunk_id,))

    def replace_source_analysis(self, source_path: str) -> int:
        """Atomically remove a prior analysis generation for one media source.

        Chunk IDs include animal metadata, so a source reingested with corrected
        metadata or a different segment size can otherwise leave an older set
        beside the current one. Ingest-job history is intentionally preserved.
        """
        with self.connect() as connection:
            chunk_rows = connection.execute(
                "SELECT chunk_id FROM video_chunks WHERE source_path = ?",
                (source_path,),
            ).fetchall()
            chunk_ids = [row["chunk_id"] for row in chunk_rows]
            if not chunk_ids:
                return 0

            placeholders = ",".join("?" for _ in chunk_ids)
            observation_rows = connection.execute(
                f"""
                SELECT animal_id
                FROM observations
                WHERE chunk_id IN ({placeholders})
                """,
                chunk_ids,
            ).fetchall()
            candidate_animal_ids = {row["animal_id"] for row in observation_rows}
            if source_path.startswith("uploads/"):
                source_name = source_path.removeprefix("uploads/")
                candidate_animal_ids.update(
                    row["animal_id"]
                    for row in connection.execute(
                        """
                        SELECT DISTINCT animal_id
                        FROM ingest_jobs
                        WHERE source_name = ?
                        """,
                        (source_name,),
                    )
                )

            event_ids: list[str] = []
            if observation_rows:
                event_rows = connection.execute(
                    """
                    SELECT DISTINCT e.event_id, e.animal_id
                    FROM events e
                    JOIN event_sources es ON es.event_id = e.event_id
                    JOIN observations o ON o.observation_id = es.observation_id
                    JOIN video_chunks vc ON vc.chunk_id = o.chunk_id
                    WHERE vc.source_path = ?
                    """,
                    (source_path,),
                ).fetchall()
                event_ids = [row["event_id"] for row in event_rows]
                candidate_animal_ids.update(row["animal_id"] for row in event_rows)

                connection.execute(
                    """
                    DELETE FROM event_sources
                    WHERE observation_id IN (
                        SELECT o.observation_id
                        FROM observations o
                        JOIN video_chunks vc ON vc.chunk_id = o.chunk_id
                        WHERE vc.source_path = ?
                    )
                    """,
                    (source_path,),
                )

            if event_ids:
                event_placeholders = ",".join("?" for _ in event_ids)
                for table in ("outcomes", "alerts", "event_narratives"):
                    connection.execute(
                        f"DELETE FROM {table} WHERE event_id IN ({event_placeholders})",
                        event_ids,
                    )
                connection.execute(
                    f"DELETE FROM events WHERE event_id IN ({event_placeholders})",
                    event_ids,
                )

            connection.execute(
                f"DELETE FROM data_gaps WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            )
            connection.execute(
                "DELETE FROM video_chunks WHERE source_path = ?",
                (source_path,),
            )

            for animal_id in candidate_animal_ids:
                connection.execute(
                    """
                    DELETE FROM animals
                    WHERE animal_id = ?
                      AND NOT EXISTS (
                          SELECT 1 FROM observations
                          WHERE observations.animal_id = animals.animal_id
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM events
                          WHERE events.animal_id = animals.animal_id
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM baseline_profiles
                          WHERE baseline_profiles.animal_id = animals.animal_id
                      )
                    """,
                    (animal_id,),
                )
            return len(chunk_ids)

    def save_alert(
        self,
        *,
        alert_id: str,
        event_id: str,
        channel: str,
        delivery_status: str,
        ack_state: str,
        scheduler_schedule_name: str | None = None,
        scheduler_schedule_arn: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO alerts(
                    alert_id, event_id, channel, delivery_status, ack_state,
                    scheduler_schedule_name, scheduler_schedule_arn
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    delivery_status = excluded.delivery_status,
                    ack_state = excluded.ack_state,
                    scheduler_schedule_name = excluded.scheduler_schedule_name,
                    scheduler_schedule_arn = excluded.scheduler_schedule_arn
                """,
                (
                    alert_id,
                    event_id,
                    channel,
                    delivery_status,
                    ack_state,
                    scheduler_schedule_name,
                    scheduler_schedule_arn,
                ),
            )

    def save_event_narrative(
        self,
        *,
        event_id: str,
        headline: str,
        factual_summary: str,
        uncertainty: list[str],
        cited_source_ids: list[str],
        model: str,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO event_narratives(
                    event_id, headline, factual_summary, uncertainty_json,
                    cited_source_ids_json, model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    headline = excluded.headline,
                    factual_summary = excluded.factual_summary,
                    uncertainty_json = excluded.uncertainty_json,
                    cited_source_ids_json = excluded.cited_source_ids_json,
                    model = excluded.model,
                    created_at = excluded.created_at
                """,
                (
                    event_id,
                    headline,
                    factual_summary,
                    json.dumps(uncertainty),
                    json.dumps(cited_source_ids),
                    model,
                    created_at,
                ),
            )

    def alert_schedule_name(self, alert_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT scheduler_schedule_name FROM alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
            return row["scheduler_schedule_name"] if row else None

    def alert_state(self, alert_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT ack_state FROM alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
            return row["ack_state"] if row else None

    def escalate_pending_alert(self, alert_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE alerts
                SET ack_state = 'escalated', escalated = 1
                WHERE alert_id = ? AND ack_state = 'pending'
                """,
                (alert_id,),
            )
            return cursor.rowcount == 1

    def reset_demo(self) -> None:
        with self.connect() as connection:
            for table in (
                "outcomes",
                "alerts",
                "event_narratives",
                "event_sources",
                "events",
                "observations",
                "detections",
                "data_gaps",
                "video_chunks",
                "baseline_profiles",
                "animals",
            ):
                connection.execute(f"DELETE FROM {table}")

    def acknowledge_alert(self, alert_id: str, *, keeper: str, acknowledged_at: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE alerts
                SET ack_state = 'acknowledged',
                    acknowledged_by = ?,
                    acknowledged_at = ?
                WHERE alert_id = ? AND ack_state = 'pending'
                """,
                (keeper, acknowledged_at, alert_id),
            )
            return cursor.rowcount == 1

    def record_outcome(
        self,
        *,
        outcome_id: str,
        event_id: str,
        resolution: str,
        note: str | None,
        entered_by: str,
        created_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO outcomes(
                    outcome_id, event_id, resolution, note, entered_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (outcome_id, event_id, resolution, note, entered_by, created_at),
            )
            connection.execute(
                "UPDATE events SET review_state = 'confirmed' WHERE event_id = ?",
                (event_id,),
            )

    def set_baseline_state(self, animal_id: str, state: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE animals SET baseline_state = ? WHERE animal_id = ?",
                (state, animal_id),
            )
            connection.execute(
                "UPDATE baseline_profiles SET state = ? WHERE animal_id = ?",
                (state, animal_id),
            )
            return cursor.rowcount == 1

    def dashboard(self) -> dict:
        with self.connect() as connection:
            animals = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT a.*,
                           count(DISTINCT e.event_id) AS event_count,
                           max(e.severity) AS latest_severity,
                           coalesce(max(bp.n_day_shifts), 0) AS baseline_days
                    FROM animals a
                    LEFT JOIN events e ON e.animal_id = a.animal_id
                    LEFT JOIN baseline_profiles bp ON bp.animal_id = a.animal_id
                    GROUP BY a.animal_id
                    ORDER BY a.enclosure_id
                    """
                )
            ]
            events = [
                self._event_dict(connection, row)
                for row in connection.execute(
                    """
                    SELECT e.*, a.name AS animal_name, a.species, a.baseline_state,
                           al.alert_id, al.delivery_status, al.ack_state,
                           al.acknowledged_at, al.acknowledged_by
                    FROM events e
                    JOIN animals a ON a.animal_id = e.animal_id
                    LEFT JOIN alerts al ON al.event_id = e.event_id
                    WHERE e.severity != 'NONE'
                    ORDER BY
                      CASE e.severity
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                        WHEN 'MODERATE' THEN 3 WHEN 'LOW' THEN 4 ELSE 5
                      END,
                      e.start_ts DESC
                    """
                )
            ]
            gaps = [
                dict(row)
                for row in connection.execute("SELECT * FROM data_gaps ORDER BY start_ts DESC")
            ]
            return {"animals": animals, "events": events, "data_gaps": gaps}

    def event_detail(self, event_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT e.*, a.name AS animal_name, a.species, a.baseline_state,
                       al.alert_id, al.delivery_status, al.ack_state,
                       al.acknowledged_at, al.acknowledged_by
                FROM events e
                JOIN animals a ON a.animal_id = e.animal_id
                LEFT JOIN alerts al ON al.event_id = e.event_id
                WHERE e.event_id = ?
                """,
                (event_id,),
            ).fetchone()
            if row is None:
                return None
            result = self._event_dict(connection, row)
            result["sources"] = [
                dict(source)
                for source in connection.execute(
                    """
                    SELECT o.*, vc.source_path, vc.source_offset_seconds, vc.camera_id
                    FROM event_sources es
                    JOIN observations o ON o.observation_id = es.observation_id
                    JOIN video_chunks vc ON vc.chunk_id = o.chunk_id
                    WHERE es.event_id = ?
                    ORDER BY o.start_ts
                    """,
                    (event_id,),
                )
            ]
            result["outcomes"] = [
                dict(outcome)
                for outcome in connection.execute(
                    "SELECT * FROM outcomes WHERE event_id = ? ORDER BY created_at DESC",
                    (event_id,),
                )
            ]
            narrative = connection.execute(
                "SELECT * FROM event_narratives WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            result["narrative"] = (
                {
                    **dict(narrative),
                    "uncertainty": json.loads(narrative["uncertainty_json"]),
                    "cited_source_ids": json.loads(narrative["cited_source_ids_json"]),
                }
                if narrative
                else None
            )
            return result

    def video_sources(self) -> list[dict]:
        """One row per distinct media file, with what was recorded against it."""
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    WITH source_chunks AS (
                        SELECT source_path,
                               min(enclosure_id) AS enclosure_id,
                               min(camera_id) AS camera_id,
                               count(*) AS chunk_count,
                               sum(CASE WHEN status = 'analyzed' THEN 1 ELSE 0 END)
                                   AS analyzed_chunk_count,
                               sum(CASE WHEN status = 'coverage_gap' THEN 1 ELSE 0 END)
                                   AS gap_chunk_count,
                               sum(CASE WHEN status = 'analyzing' THEN 1 ELSE 0 END)
                                   AS analyzing_chunk_count,
                               coalesce(sum(CASE
                                   WHEN status = 'analyzed' THEN
                                       (julianday(end_ts) - julianday(start_ts)) * 86400.0
                                   ELSE 0
                               END), 0) AS stored_analyzed_duration_seconds,
                               coalesce(sum(
                                   (julianday(end_ts) - julianday(start_ts)) * 86400.0
                               ), 0) AS stored_source_duration_seconds,
                               min(start_ts) AS first_start_ts,
                               max(end_ts) AS last_end_ts
                        FROM video_chunks
                        GROUP BY source_path
                    ),
                    source_detections AS (
                        SELECT vc.source_path,
                               count(d.detection_id) AS detection_count
                        FROM video_chunks vc
                        JOIN detections d ON d.chunk_id = vc.chunk_id
                        GROUP BY vc.source_path
                    ),
                    source_observations AS (
                        SELECT vc.source_path,
                               count(o.observation_id) AS observation_count,
                               group_concat(DISTINCT a.animal_id) AS animal_ids,
                               group_concat(DISTINCT a.name) AS animal_names,
                               group_concat(DISTINCT a.species) AS animal_species
                        FROM video_chunks vc
                        JOIN observations o ON o.chunk_id = vc.chunk_id
                        LEFT JOIN animals a ON a.animal_id = o.animal_id
                        GROUP BY vc.source_path
                    ),
                    source_events AS (
                        SELECT vc.source_path,
                               count(DISTINCT es.event_id) AS event_count
                        FROM video_chunks vc
                        JOIN observations o ON o.chunk_id = vc.chunk_id
                        JOIN event_sources es ON es.observation_id = o.observation_id
                        GROUP BY vc.source_path
                    )
                    SELECT chunks.*,
                           coalesce(detections.detection_count, 0) AS detection_count,
                           coalesce(observations.observation_count, 0) AS observation_count,
                           coalesce(events.event_count, 0) AS event_count,
                           observations.animal_ids,
                           observations.animal_names,
                           observations.animal_species
                    FROM source_chunks chunks
                    LEFT JOIN source_detections detections
                        ON detections.source_path = chunks.source_path
                    LEFT JOIN source_observations observations
                        ON observations.source_path = chunks.source_path
                    LEFT JOIN source_events events
                        ON events.source_path = chunks.source_path
                    ORDER BY chunks.source_path
                    """
                )
            ]

    def video_track(self, source_path: str) -> dict:
        """Detections and events for one media file, placed on that file's timeline.

        Chunk rows carry ``source_offset_seconds``, the point in the media file
        where the chunk begins, and detections carry an offset within the chunk.
        Composing the two yields a position in the file the player can seek to,
        while wall-clock provenance stays intact on the underlying records.
        """
        with self.connect() as connection:
            chunks = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM video_chunks
                    WHERE source_path = ?
                    ORDER BY source_offset_seconds
                    """,
                    (source_path,),
                )
            ]
            if not chunks:
                return {
                    "source_path": source_path,
                    "chunks": [],
                    "detections": [],
                    "events": [],
                    "observations": [],
                    "rule_checks": [],
                }
            offsets = {chunk["chunk_id"]: chunk["source_offset_seconds"] for chunk in chunks}
            starts = {chunk["chunk_id"]: chunk["start_ts"] for chunk in chunks}
            source_anchor = chunks[0]
            placeholders = ",".join("?" for _ in chunks)
            chunk_ids = [chunk["chunk_id"] for chunk in chunks]

            detections = [
                {
                    "detection_id": row["detection_id"],
                    "chunk_id": row["chunk_id"],
                    "track_id": row["track_id"],
                    "video_seconds": round(offsets[row["chunk_id"]] + row["relative_seconds"], 3),
                    "box": {
                        "x": row["box_x"],
                        "y": row["box_y"],
                        "width": row["box_width"],
                        "height": row["box_height"],
                    },
                    "score": row["score"],
                    "source": row["source"],
                    "label": row["label"],
                    "class_id": row["class_id"],
                    "model": row["model"],
                }
                for row in connection.execute(
                    f"""
                    SELECT * FROM detections
                    WHERE chunk_id IN ({placeholders})
                    ORDER BY relative_seconds
                    """,
                    chunk_ids,
                )
            ]
            detections.sort(
                key=lambda item: (
                    item["video_seconds"],
                    item["source"],
                    item["detection_id"],
                )
            )

            events = []
            for row in connection.execute(
                f"""
                SELECT DISTINCT e.*, a.name AS animal_name, al.ack_state
                FROM events e
                JOIN animals a ON a.animal_id = e.animal_id
                LEFT JOIN alerts al ON al.event_id = e.event_id
                WHERE e.severity != 'NONE'
                  AND EXISTS (
                      SELECT 1
                      FROM event_sources es
                      JOIN observations o ON o.observation_id = es.observation_id
                      WHERE es.event_id = e.event_id
                        AND o.chunk_id IN ({placeholders})
                  )
                ORDER BY e.start_ts
                """,
                chunk_ids,
            ):
                base = _seconds_between(source_anchor["start_ts"], row["start_ts"])
                end = _seconds_between(source_anchor["start_ts"], row["end_ts"])
                source_offset = float(source_anchor["source_offset_seconds"])
                events.append(
                    {
                        "event_id": row["event_id"],
                        "animal_id": row["animal_id"],
                        "animal_name": row["animal_name"],
                        "enclosure_id": row["enclosure_id"],
                        "behavior": row["behavior"],
                        "severity": row["severity"],
                        "rule_fired": row["rule_fired"],
                        "rule_version": row["rule_version"],
                        "action": row["action"],
                        "confidence": row["confidence"],
                        "review_state": row["review_state"],
                        "ack_state": row["ack_state"],
                        "start_ts": row["start_ts"],
                        "end_ts": row["end_ts"],
                        "start_seconds": round(max(0.0, source_offset + base), 3),
                        "end_seconds": round(max(0.0, source_offset + end), 3),
                    }
                )

            linked_rule_events: dict[str, dict] = {}
            for row in connection.execute(
                f"""
                SELECT es.observation_id,
                       e.event_id,
                       e.severity,
                       e.rule_fired,
                       e.rule_version,
                       e.action,
                       e.review_state
                FROM event_sources es
                JOIN events e ON e.event_id = es.event_id
                JOIN observations o ON o.observation_id = es.observation_id
                WHERE o.chunk_id IN ({placeholders})
                  AND e.severity != 'NONE'
                ORDER BY e.start_ts, e.event_id
                """,
                chunk_ids,
            ):
                linked_rule_events.setdefault(row["observation_id"], dict(row))

            observation_rows = connection.execute(
                f"""
                SELECT o.*, a.name AS animal_name, a.species AS animal_species
                FROM observations o
                JOIN animals a ON a.animal_id = o.animal_id
                WHERE o.chunk_id IN ({placeholders})
                ORDER BY o.start_ts, o.observation_id
                """,
                chunk_ids,
            )
            observations = []
            rule_checks = []
            for row in observation_rows:
                start_seconds = round(
                    max(
                        0.0,
                        offsets[row["chunk_id"]]
                        + _seconds_between(starts[row["chunk_id"]], row["start_ts"]),
                    ),
                    3,
                )
                end_seconds = round(
                    max(
                        0.0,
                        offsets[row["chunk_id"]]
                        + _seconds_between(starts[row["chunk_id"]], row["end_ts"]),
                    ),
                    3,
                )
                observations.append(
                    {
                        "observation_id": row["observation_id"],
                        "animal_id": row["animal_id"],
                        "animal_name": row["animal_name"],
                        "animal_species": row["animal_species"],
                        "behavior": row["behavior"],
                        "evidence": row["evidence"],
                        "provider": row["provider"],
                        "evidence_kind": row["evidence_kind"],
                        "activity_label": row["activity_label"],
                        "start_seconds": start_seconds,
                        "end_seconds": end_seconds,
                    }
                )

                linked_event = linked_rule_events.get(row["observation_id"])
                rule_checks.append(
                    {
                        "observation_id": row["observation_id"],
                        "animal_id": row["animal_id"],
                        "animal_name": row["animal_name"],
                        "animal_species": row["animal_species"],
                        "behavior": row["behavior"],
                        "start_seconds": start_seconds,
                        "end_seconds": end_seconds,
                        "event_id": linked_event["event_id"] if linked_event else None,
                        "severity": linked_event["severity"] if linked_event else "NONE",
                        "rule_fired": (
                            linked_event["rule_fired"] if linked_event else "NO_RULE_FIRED"
                        ),
                        "rule_version": linked_event["rule_version"] if linked_event else None,
                        "action": linked_event["action"] if linked_event else None,
                        "review_state": linked_event["review_state"] if linked_event else None,
                    }
                )

            return {
                "source_path": source_path,
                "chunks": chunks,
                "detections": detections,
                "events": events,
                "observations": observations,
                "rule_checks": rule_checks,
            }

    def searchable_moments(
        self,
        *,
        enclosure_id: str | None = None,
        animal_id: str | None = None,
        camera_id: str | None = None,
        source_path: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Return provider observations with stable, browser-seekable positions."""
        conditions = ["1 = 1"]
        parameters: list[object] = []
        if enclosure_id:
            conditions.append("vc.enclosure_id = ?")
            parameters.append(enclosure_id)
        if animal_id:
            conditions.append("o.animal_id = ?")
            parameters.append(animal_id)
        if source_path:
            conditions.append("vc.source_path = ?")
            parameters.append(source_path)
        elif camera_id:
            conditions.append("vc.camera_id = ?")
            parameters.append(camera_id)
        parameters.append(limit)

        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT o.*, a.name AS animal_name, a.species,
                       vc.source_path, vc.camera_id, vc.source_offset_seconds,
                       vc.start_ts AS chunk_start_ts,
                       vc.enclosure_id AS moment_enclosure_id
                FROM observations o
                JOIN animals a ON a.animal_id = o.animal_id
                JOIN video_chunks vc ON vc.chunk_id = o.chunk_id
                WHERE {" AND ".join(conditions)}
                ORDER BY o.start_ts
                LIMIT ?
                """,
                parameters,
            )
            return [
                {
                    "observation_id": row["observation_id"],
                    "animal_id": row["animal_id"],
                    "animal_name": row["animal_name"],
                    "species": row["species"],
                    "enclosure_id": row["moment_enclosure_id"],
                    "camera_id": row["camera_id"],
                    "behavior": row["behavior"],
                    "activity_label": row["activity_label"],
                    "evidence": row["evidence"],
                    "provider": row["provider"],
                    "provider_model": row["provider_model"],
                    "evidence_kind": row["evidence_kind"],
                    "source_path": row["source_path"],
                    "start_ts": row["start_ts"],
                    "end_ts": row["end_ts"],
                    "start_seconds": round(
                        max(
                            0.0,
                            row["source_offset_seconds"]
                            + _seconds_between(row["chunk_start_ts"], row["start_ts"]),
                        ),
                        3,
                    ),
                    "end_seconds": round(
                        max(
                            0.0,
                            row["source_offset_seconds"]
                            + _seconds_between(row["chunk_start_ts"], row["end_ts"]),
                        ),
                        3,
                    ),
                }
                for row in rows
            ]

    def morning_report(self) -> dict:
        dashboard = self.dashboard()
        by_animal = {animal["animal_id"]: [] for animal in dashboard["animals"]}
        for event in dashboard["events"]:
            by_animal[event["animal_id"]].append(event)
        animals = []
        for animal in dashboard["animals"]:
            item = dict(animal)
            item["events"] = by_animal[animal["animal_id"]]
            animals.append(item)
        return {
            "animals": animals,
            "data_gaps": dashboard["data_gaps"],
            "summary": {
                "animals_monitored": len(animals),
                "events": len(dashboard["events"]),
                "data_gaps": len(dashboard["data_gaps"]),
            },
        }

    @staticmethod
    def _event_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        result = dict(row)
        result["explanation_facts"] = json.loads(result.pop("explanation_facts_json"))
        result["source_observation_ids"] = [
            source["observation_id"]
            for source in connection.execute(
                "SELECT observation_id FROM event_sources WHERE event_id = ?",
                (result["event_id"],),
            )
        ]
        return result

    def event_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT count(*) AS count FROM events").fetchone()
            return int(row["count"])

    def dump_table(self, table: str) -> list[dict]:
        allowed = {
            "animals",
            "video_chunks",
            "observations",
            "detections",
            "events",
            "event_sources",
            "event_narratives",
            "baseline_profiles",
            "alerts",
            "outcomes",
            "data_gaps",
        }
        if table not in allowed:
            raise ValueError("unsupported table")
        with self.connect() as connection:
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            return [json.loads(json.dumps(dict(row))) for row in rows]


def _seconds_between(start_iso: str, end_iso: str) -> float:
    """Offset in seconds between two stored ISO timestamps.

    Rows are written with ``datetime.isoformat`` so they round-trip through
    ``fromisoformat``. A malformed row must not take down a whole video
    timeline, so an unparseable pair collapses to the start of the media.
    """
    try:
        return (datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).total_seconds()
    except (TypeError, ValueError):
        return 0.0
