from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from zoovision.aws_storage import S3Archive, S3BucketSet
from zoovision.domain import BaselineState, ShiftMode
from zoovision.graph import Neo4jGraphWriter
from zoovision.ids import stable_id
from zoovision.providers import TwelveLabsAnalyzer, VideoChunkContext
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore
from zoovision.workflow import SegmentWorkflow, SegmentWorkflowInput


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--animal-id", required=True)
    parser.add_argument("--animal-name", required=True)
    parser.add_argument("--species", required=True)
    parser.add_argument("--enclosure-id", required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--duration-seconds", type=float, required=True)
    parser.add_argument("--shift", type=ShiftMode, choices=list(ShiftMode), required=True)
    parser.add_argument(
        "--baseline-state",
        type=BaselineState,
        choices=list(BaselineState),
        default=BaselineState.SHADOW,
    )
    parser.add_argument("--hours-since-water-contact", type=float)
    parser.add_argument("--inactivity-z", type=float)
    parser.add_argument("--baseline-delta-z", type=float)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    arguments = _arguments()
    settings = get_settings()
    if not settings.twelvelabs_api_key:
        raise SystemExit("TWELVELABS_API_KEY is not configured")
    source = arguments.source.resolve()
    raw_root = (settings.storage_root / "raw").resolve()
    if not source.is_file() or not source.is_relative_to(raw_root):
        raise SystemExit(f"source must be an existing file below {raw_root}")
    if arguments.start.tzinfo is None:
        raise SystemExit("--start must include a timezone offset")
    if arguments.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be positive")

    content_sha256 = _sha256(source)
    chunk_id = stable_id(
        "chunk",
        arguments.animal_id,
        arguments.enclosure_id,
        arguments.start.isoformat(),
        content_sha256,
    )
    graph_writer = None
    if all((settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)):
        graph_writer = Neo4jGraphWriter(
            settings.neo4j_uri,
            settings.neo4j_username,
            settings.neo4j_password,
        )
    store = SQLiteStore(settings.database_path)
    store.initialize()
    archive = None
    if settings.aws_storage_enabled and settings.aws_storage_configured:
        session = boto3.Session(**settings.aws_session_kwargs)
        archive = S3Archive(
            S3BucketSet(
                raw=settings.s3_raw_bucket,
                analysis=settings.s3_analysis_bucket,
                clips=settings.s3_clips_bucket,
            ),
            region=settings.aws_region,
            client=session.client("s3"),
        )
    workflow = SegmentWorkflow(
        analyzer=TwelveLabsAnalyzer(
            settings.twelvelabs_api_key,
            model=settings.twelvelabs_model,
        ),
        store=store,
        graph_writer=graph_writer,
        archive=archive,
    )
    try:
        result = workflow.run(
            SegmentWorkflowInput(
                chunk=VideoChunkContext(
                    chunk_id=chunk_id,
                    animal_id=arguments.animal_id,
                    enclosure_id=arguments.enclosure_id,
                    start_ts=arguments.start,
                    end_ts=arguments.start + timedelta(seconds=arguments.duration_seconds),
                ),
                animal_name=arguments.animal_name,
                species=arguments.species,
                camera_id=arguments.camera_id,
                source_path=str(source.relative_to(raw_root)),
                content_sha256=content_sha256,
                local_video_path=source,
                shift_mode=arguments.shift,
                baseline_state=arguments.baseline_state,
                fixture_mode=settings.fixture_mode,
                delivery_enabled=settings.alert_delivery_enabled,
                webhook_configured=bool(settings.slack_webhook_url),
                hours_since_water_contact=arguments.hours_since_water_contact,
                inactivity_z=arguments.inactivity_z,
                baseline_delta_z=arguments.baseline_delta_z,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    finally:
        if graph_writer is not None:
            graph_writer.close()


if __name__ == "__main__":
    main()
