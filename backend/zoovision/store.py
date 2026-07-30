from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path

from .domain import EventRecord

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
    provider_item_id TEXT
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
    delivery_attempts_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(event_id),
    resolution TEXT NOT NULL,
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
                    severity, rule_fired, action, confidence, baseline_delta_z, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    start_ts = excluded.start_ts,
                    end_ts = excluded.end_ts,
                    severity = excluded.severity,
                    rule_fired = excluded.rule_fired,
                    action = excluded.action,
                    confidence = excluded.confidence,
                    baseline_delta_z = excluded.baseline_delta_z
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
