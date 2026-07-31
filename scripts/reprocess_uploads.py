from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta

from zoovision.domain import ShiftMode
from zoovision.graph import Neo4jGraphWriter
from zoovision.ingest import IngestRequest, VideoIngestService
from zoovision.providers import TwelveLabsAnalyzer
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reprocess existing uploaded recordings with TwelveLabs Pegasus."
    )
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="Uploaded source name, without the uploads/ prefix. Repeat as needed.",
    )
    parser.add_argument(
        "--segment-seconds",
        type=int,
        default=120,
        choices=range(10, 901),
        metavar="10-900",
        help="Full-file analysis segment length. Defaults to 120 seconds.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    settings = get_settings()
    if not settings.twelvelabs_api_key:
        raise SystemExit("TWELVELABS_API_KEY is not configured")
    if not (settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password):
        raise SystemExit("Neo4j writer credentials are not configured")

    store = SQLiteStore(settings.database_path)
    store.initialize()
    graph_writer = Neo4jGraphWriter(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
    )
    graph_writer.verify_connectivity()
    graph_writer.initialize_schema()
    chunks = store.dump_table("video_chunks")
    animals = {row["animal_id"]: row for row in store.dump_table("animals")}
    jobs = store.recent_ingest_jobs(200)

    backup_root = settings.storage_root / "raw" / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / (
        f"{settings.database_path.name}.before-twelvelabs-reprocess-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    shutil.copy2(settings.database_path, backup)
    print(json.dumps({"database_backup": str(backup)}), flush=True)

    service = VideoIngestService(
        store=store,
        raw_root=settings.storage_root / "raw",
        analyzer_factory=lambda: TwelveLabsAnalyzer(
            settings.twelvelabs_api_key,
            model=settings.twelvelabs_model,
        ),
        graph_writer=graph_writer,
        fixture_mode=settings.fixture_mode,
    )

    for source_name in arguments.source:
        source_path = f"uploads/{source_name}"
        source_chunks = sorted(
            (row for row in chunks if row["source_path"] == source_path),
            key=lambda row: row["source_offset_seconds"],
        )
        if not source_chunks:
            raise SystemExit(f"no analyzed upload found for {source_name}")
        prior_job = next(
            (row for row in jobs if row["source_name"] == source_name),
            None,
        )
        if prior_job is None:
            raise SystemExit(f"no ingest metadata found for {source_name}")
        animal_id = prior_job["animal_id"]
        animal = animals.get(animal_id)
        if animal is None:
            raise SystemExit(f"animal metadata missing for {source_name}")

        first = source_chunks[0]
        first_start = datetime.fromisoformat(first["start_ts"]) - timedelta(
            seconds=float(first["source_offset_seconds"])
        )
        shift_mode = (
            ShiftMode.DAY
            if prior_job.get("segments")
            and prior_job["segments"][0].get("route") == "day_observation"
            else ShiftMode.NIGHT
        )
        request = IngestRequest(
            source_name=source_name,
            animal_id=animal_id,
            animal_name=animal["name"],
            species=animal["species"],
            enclosure_id=prior_job["enclosure_id"],
            camera_id=first["camera_id"],
            start_ts=first_start,
            shift_mode=shift_mode,
            segment_seconds=arguments.segment_seconds,
            max_segments=240,
        )
        print(
            json.dumps(
                {
                    "source": source_name,
                    "status": "processing",
                    "segment_seconds": arguments.segment_seconds,
                }
            ),
            flush=True,
        )
        result = service.run(request)
        print(
            json.dumps(
                {
                    "source": source_name,
                    "status": result.status,
                    "analyzer": result.analyzer,
                    "segments": result.total_segments,
                    "observations": sum(
                        segment.observation_count for segment in result.segments
                    ),
                    "data_gaps": len(result.data_gap_ids),
                    "error": result.error,
                }
            ),
            flush=True,
        )
        if result.status != "complete" or result.data_gap_ids:
            raise SystemExit(f"TwelveLabs reprocessing was incomplete for {source_name}")


if __name__ == "__main__":
    main()
