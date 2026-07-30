from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

from .domain import BaselineProfile, DataGap, EventRecord, Observation

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
    evidence_kind TEXT NOT NULL
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
                    evidence_kind
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_id) DO UPDATE SET
                    confidence = excluded.confidence,
                    evidence = excluded.evidence,
                    provider_item_id = excluded.provider_item_id
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
                ),
            )

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

    def save_alert(
        self,
        *,
        alert_id: str,
        event_id: str,
        channel: str,
        delivery_status: str,
        ack_state: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO alerts(
                    alert_id, event_id, channel, delivery_status, ack_state
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    delivery_status = excluded.delivery_status,
                    ack_state = excluded.ack_state
                """,
                (alert_id, event_id, channel, delivery_status, ack_state),
            )

    def reset_demo(self) -> None:
        with self.connect() as connection:
            for table in (
                "outcomes",
                "alerts",
                "event_sources",
                "events",
                "observations",
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
            return result

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
            "events",
            "event_sources",
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
