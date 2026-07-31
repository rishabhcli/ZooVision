from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from zoovision.graph import (
    GraphClipProvenance,
    GraphObservationProvenance,
    Neo4jGraphWriter,
)
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile existing Neo4j clip bounds and observation provenance "
            "from the authoritative SQLite records."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="SQLite database path. Defaults to ZOOVISION_STORAGE_ROOT/zoovision.db.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count the SQLite records without changing Neo4j.",
    )
    return parser.parse_args(argv)


def _load_reconciliation(
    store: SQLiteStore,
) -> tuple[list[GraphClipProvenance], list[GraphObservationProvenance]]:
    observation_rows = sorted(
        store.dump_table("observations"),
        key=lambda row: str(row["observation_id"]),
    )
    chunk_rows = {str(row["chunk_id"]): row for row in store.dump_table("video_chunks")}
    referenced_chunk_ids = sorted({str(row["chunk_id"]) for row in observation_rows})
    missing_chunks = [chunk_id for chunk_id in referenced_chunk_ids if chunk_id not in chunk_rows]
    if missing_chunks:
        raise ValueError("SQLite observations reference missing video chunks")

    chunks = [
        GraphClipProvenance(
            chunk_id=chunk_id,
            source_path=str(chunk_rows[chunk_id]["source_path"]),
            start_ts=chunk_rows[chunk_id]["start_ts"],
            end_ts=chunk_rows[chunk_id]["end_ts"],
        )
        for chunk_id in referenced_chunk_ids
    ]
    observations = [
        GraphObservationProvenance(
            observation_id=str(row["observation_id"]),
            provider_item_id=row.get("provider_item_id"),
            activity_label=row.get("activity_label"),
        )
        for row in observation_rows
    ]
    return chunks, observations


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _arguments(argv)
    settings = get_settings()
    database_path = arguments.database or settings.database_path
    if not database_path.is_file():
        raise SystemExit("ZooVision SQLite database was not found")

    try:
        chunks, observations = _load_reconciliation(SQLiteStore(database_path))
    except (KeyError, ValueError) as error:
        raise SystemExit(str(error)) from error

    counts = {"chunks": len(chunks), "observations": len(observations)}
    if arguments.dry_run:
        print(json.dumps({"status": "validated", **counts}, sort_keys=True))
        return

    if not (settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password):
        raise SystemExit("Neo4j writer credentials are not configured")

    writer = Neo4jGraphWriter(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
    )
    try:
        writer.verify_connectivity()
        reconciled = writer.reconcile_provenance(
            chunks=chunks,
            observations=observations,
        )
    finally:
        writer.close()

    print(json.dumps({"status": "reconciled", **reconciled}, sort_keys=True))


if __name__ == "__main__":
    main()
