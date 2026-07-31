from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from zoovision.store import SQLiteStore

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_neo4j_provenance.py"
SPEC = importlib.util.spec_from_file_location(
    "reconcile_neo4j_provenance_script",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCRIPT
SPEC.loader.exec_module(SCRIPT)

_arguments = SCRIPT._arguments
_load_reconciliation = SCRIPT._load_reconciliation


def test_arguments_support_validation_only_runs(tmp_path: Path) -> None:
    database = tmp_path / "zoovision.db"

    arguments = _arguments(["--database", str(database), "--dry-run"])

    assert arguments.database == database
    assert arguments.dry_run is True


def test_load_reconciliation_uses_chunk_bounds_and_observation_provenance(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "zoovision.db")
    store.initialize()
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO animals VALUES (?, ?, ?, ?, ?)",
            ("animal-1", "Nox", "African lion", "ENC-07", "shadow"),
        )
        connection.execute(
            "INSERT INTO video_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "chunk-1",
                "ENC-07",
                "CAM-07L",
                start.isoformat(),
                (start + timedelta(minutes=15)).isoformat(),
                "uploads/lion.mp4",
                0.0,
                "a" * 64,
                "analyzed",
            ),
        )
        connection.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "obs-1",
                "chunk-1",
                "animal-1",
                "walking",
                (start + timedelta(seconds=5)).isoformat(),
                (start + timedelta(seconds=12)).isoformat(),
                0.9,
                "The lion walks across the enclosure.",
                "twelvelabs",
                "pegasus1.5",
                "provider-item-1",
                "provider_structured",
                "Lion walking across the enclosure",
            ),
        )

    chunks, observations = _load_reconciliation(store)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "chunk-1"
    assert chunks[0].source_path == "uploads/lion.mp4"
    assert chunks[0].start_ts == start
    assert chunks[0].end_ts == start + timedelta(minutes=15)
    assert len(observations) == 1
    assert observations[0].model_dump() == {
        "observation_id": "obs-1",
        "provider_item_id": "provider-item-1",
        "activity_label": "Lion walking across the enclosure",
    }


def test_load_reconciliation_rejects_missing_chunk_provenance() -> None:
    class MissingChunkStore:
        @staticmethod
        def dump_table(table: str) -> list[dict]:
            if table == "observations":
                return [{"observation_id": "obs-1", "chunk_id": "chunk-missing"}]
            return []

    with pytest.raises(ValueError, match="missing video chunks"):
        _load_reconciliation(MissingChunkStore())
