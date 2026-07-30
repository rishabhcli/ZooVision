from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from zoovision.domain import BaselineState, ShiftMode
from zoovision.ids import stable_id
from zoovision.ingest import _provider_ready, segment_video
from zoovision.providers import TwelveLabsAnalyzer, VideoChunkContext
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore
from zoovision.workflow import SegmentWorkflow, SegmentWorkflowInput

DEMO_SOURCES = (
    {
        "source_path": "fixtures/enc07_lion_night_30m.mp4",
        "animal_id": "animal-nox",
        "animal_name": "Nox",
        "species": "African lion",
        "enclosure_id": "ENC-07",
        "camera_id": "CAM-07A",
        "start_ts": "2026-07-29T22:10:00-07:00",
    },
    {
        "source_path": "fixtures/enc05_elephant_15m.mp4",
        "animal_id": "animal-mara",
        "animal_name": "Mara",
        "species": "African elephant",
        "enclosure_id": "ENC-05",
        "camera_id": "CAM-05N",
        "start_ts": "2026-07-30T01:00:00-07:00",
    },
    {
        "source_path": "fixtures/enc03_mountain_gorilla_15m.mp4",
        "animal_id": "animal-juniper",
        "animal_name": "Juniper",
        "species": "Mountain gorilla",
        "enclosure_id": "ENC-03",
        "camera_id": "CAM-03Y",
        "start_ts": "2026-07-30T03:00:00-07:00",
    },
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Precompute dense TwelveLabs moments for the stage demo recordings."
    )
    parser.add_argument("--segment-seconds", type=int, default=120)
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument(
        "--only-gaps",
        action="store_true",
        help="Retry only stable chunks whose current status is coverage_gap.",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    arguments = _arguments()
    if not 30 <= arguments.segment_seconds <= 300:
        raise SystemExit("--segment-seconds must be between 30 and 300")

    settings = get_settings()
    if not settings.twelvelabs_api_key:
        raise SystemExit("TWELVELABS_API_KEY is not configured")

    store = SQLiteStore(settings.database_path)
    store.initialize()
    backup_root = settings.storage_root / "raw" / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / (
        f"{settings.database_path.name}.before-stage-preprocess-"
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    shutil.copy2(settings.database_path, backup)
    print(json.dumps({"database_backup": str(backup)}), flush=True)

    selected = [
        item
        for item in DEMO_SOURCES
        if not arguments.sources or item["source_path"] in arguments.sources
    ]
    if not selected:
        raise SystemExit("no matching demo sources")

    analyzer = TwelveLabsAnalyzer(
        settings.twelvelabs_api_key,
        model=settings.twelvelabs_model,
    )
    total_observations = 0
    total_events = 0
    total_gaps = 0
    chunk_statuses = {
        row["chunk_id"]: row["status"] for row in store.dump_table("video_chunks")
    }

    for item in selected:
        source_path = item["source_path"]
        source = settings.storage_root / "raw" / source_path
        if not source.is_file():
            raise SystemExit(f"missing demo source: {source}")
        content_sha256 = _sha256(source)
        start_ts = datetime.fromisoformat(item["start_ts"])
        workspace = Path(tempfile.mkdtemp(prefix="zoovision-stage-"))
        try:
            pieces = segment_video(
                source,
                workspace,
                segment_seconds=arguments.segment_seconds,
                max_segments=240,
            )
            print(
                json.dumps(
                    {
                        "source": source_path,
                        "status": "processing",
                        "segments": len(pieces),
                    }
                ),
                flush=True,
            )
            for ordinal, offset, duration, piece in pieces:
                chunk_id = stable_id(
                    "stage-chunk",
                    source_path,
                    content_sha256,
                    ordinal,
                    round(offset, 3),
                )
                if arguments.only_gaps and chunk_statuses.get(chunk_id) != "coverage_gap":
                    continue
                analyzable = _provider_ready(piece)
                request = SegmentWorkflowInput(
                        chunk=VideoChunkContext(
                            chunk_id=chunk_id,
                            animal_id=item["animal_id"],
                            enclosure_id=item["enclosure_id"],
                            start_ts=start_ts + timedelta(seconds=offset),
                            end_ts=start_ts + timedelta(seconds=offset + duration),
                        ),
                        animal_name=item["animal_name"],
                        species=item["species"],
                        camera_id=item["camera_id"],
                        source_path=source_path,
                        content_sha256=content_sha256,
                        source_offset_seconds=offset,
                        local_video_path=analyzable,
                        shift_mode=ShiftMode.NIGHT,
                        baseline_state=BaselineState.SHADOW,
                        fixture_mode=True,
                        delivery_enabled=False,
                        webhook_configured=False,
                    )
                result = SegmentWorkflow(analyzer=analyzer, store=store).run(request)
                if result.data_gap_id is not None:
                    result = SegmentWorkflow(analyzer=analyzer, store=store).run(request)
                total_observations += result.observation_count
                total_events += len(result.event_ids)
                total_gaps += int(result.data_gap_id is not None)
                print(
                    json.dumps(
                        {
                            "source": source_path,
                            "segment": ordinal + 1,
                            "segments": len(pieces),
                            "observations": result.observation_count,
                            "events": len(result.event_ids),
                            "data_gap": result.data_gap_id,
                        }
                    ),
                    flush=True,
                )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    print(
        json.dumps(
            {
                "status": "complete",
                "sources": len(selected),
                "observations": total_observations,
                "events": total_events,
                "data_gaps": total_gaps,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
