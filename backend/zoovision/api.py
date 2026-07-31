from __future__ import annotations

import hmac
import shutil
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

import boto3
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .aws_storage import S3Archive, S3BucketSet
from .bedrock import BedrockMarengoEmbedder
from .chat import ChatReply, ChatRequest, GroundedChat
from .demo import seed_demo
from .enrichment import (
    MorningAnimalFacts,
    MorningReportRequest,
    StrandsEvidenceEnricher,
    StrandsMorningReportWriter,
)
from .graph import Neo4jGraphReader, Neo4jGraphWriter
from .graphview import GraphView, build_graph_view
from .ids import stable_id
from .ingest import IngestJob, IngestRequest, VideoIngestService
from .scheduler import EventBridgeEscalationScheduler
from .settings import Settings, get_settings
from .store import SQLiteStore

#: Container types the ingest path accepts. ffprobe still validates the bytes.
ALLOWED_UPLOAD_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_UPLOAD_CHUNK_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_CHUNKS = MAX_UPLOAD_BYTES // MAX_UPLOAD_CHUNK_BYTES
UPLOADED_FILE = File(...)
UPLOAD_ID_FORM = Form(..., min_length=36, max_length=36)
UPLOAD_NAME_FORM = Form(..., min_length=1, max_length=255)
UPLOAD_CHUNK_INDEX_FORM = Form(..., ge=0, lt=MAX_UPLOAD_CHUNKS)
UPLOAD_CHUNK_COUNT_FORM = Form(..., ge=1, le=MAX_UPLOAD_CHUNKS)
UPLOAD_TOTAL_BYTES_FORM = Form(..., ge=1, le=MAX_UPLOAD_BYTES)


def _source_analysis_metadata(source: dict, job: dict | None) -> dict:
    """Describe whether a visible source is still partial or fully analyzed."""
    if job is not None:
        segments = job.get("segments") or []
        analyzed_duration = sum(
            float(segment.get("duration_seconds") or 0)
            for segment in segments
            if not segment.get("data_gap_id")
        )
        probe = job.get("probe") or {}
        probe_duration = float(probe.get("duration_seconds") or 0)
        coverage_percent = (
            min(100.0, analyzed_duration / probe_duration * 100) if probe_duration > 0 else 0.0
        )
        completed_segments = int(job.get("completed_segments") or 0)
        total_segments = int(job.get("total_segments") or 0)
        data_gap_count = len(job.get("data_gap_ids") or [])
        job_status = str(job.get("status") or "queued")
        if job_status in {"queued", "running"}:
            analysis_status = "analyzing"
        elif (
            job_status == "complete"
            and total_segments > 0
            and completed_segments == total_segments
            and data_gap_count == 0
            and coverage_percent >= 99
        ):
            analysis_status = "complete"
        else:
            analysis_status = "incomplete"
        reported_coverage = 100.0 if analysis_status == "complete" else coverage_percent
        return {
            "analysis_status": analysis_status,
            "is_fully_analyzed": analysis_status == "complete",
            "latest_job_status": job_status,
            "completed_segments": completed_segments,
            "total_segments": total_segments,
            "data_gap_count": data_gap_count,
            "analyzed_duration_seconds": round(analyzed_duration, 3),
            "probe_duration_seconds": round(probe_duration, 3),
            "coverage_percent": round(reported_coverage, 1),
        }

    chunk_count = int(source.get("chunk_count") or 0)
    analyzed_chunks = int(source.get("analyzed_chunk_count") or 0)
    gap_chunks = int(source.get("gap_chunk_count") or 0)
    analyzing_chunks = int(source.get("analyzing_chunk_count") or 0)
    if analyzing_chunks:
        analysis_status = "analyzing"
    elif chunk_count > 0 and analyzed_chunks == chunk_count and gap_chunks == 0:
        analysis_status = "complete"
    else:
        analysis_status = "incomplete"
    analyzed_duration = max(0.0, float(source.get("stored_analyzed_duration_seconds") or 0))
    source_duration = max(0.0, float(source.get("stored_source_duration_seconds") or 0))
    coverage_percent = (
        min(100.0, analyzed_duration / source_duration * 100) if source_duration > 0 else 0.0
    )
    reported_coverage = 100.0 if analysis_status == "complete" else coverage_percent
    return {
        "analysis_status": analysis_status,
        "is_fully_analyzed": analysis_status == "complete",
        "latest_job_status": None,
        "completed_segments": analyzed_chunks + gap_chunks,
        "total_segments": chunk_count,
        "data_gap_count": gap_chunks,
        "analyzed_duration_seconds": round(analyzed_duration, 3),
        "probe_duration_seconds": round(source_duration, 3),
        "coverage_percent": round(reported_coverage, 1),
    }


class AckRequest(BaseModel):
    keeper: str = Field(min_length=1, max_length=80)


class OutcomeRequest(BaseModel):
    resolution: Literal[
        "welfare_check_completed",
        "water_available",
        "continued_observation",
        "false_positive",
        "camera_issue",
    ]
    note: str | None = Field(default=None, max_length=500)
    entered_by: str = Field(min_length=1, max_length=80)


class BaselineRequest(BaseModel):
    state: Literal["shadow", "active", "paused"]


class IngestStartRequest(BaseModel):
    source_name: str = Field(min_length=1, max_length=255)
    animal_id: str = Field(min_length=1, max_length=120)
    animal_name: str = Field(min_length=1, max_length=120)
    species: str = Field(default="Unspecified", min_length=1, max_length=160)
    enclosure_id: str = Field(min_length=1, max_length=120)
    camera_id: str = Field(default="CAM-UPLOAD", min_length=1, max_length=120)
    start_ts: datetime | None = None
    shift_mode: Literal["day", "night"] = "night"
    segment_seconds: int = Field(default=120, ge=10, le=900)
    max_segments: int = Field(default=240, ge=1, le=240)


@lru_cache
def _services() -> tuple[Settings, SQLiteStore]:
    settings = get_settings()
    store = SQLiteStore(settings.database_path)
    store.initialize()
    if store.dump_table("animals") == [] and settings.fixture_mode:
        seed_demo(store, settings)
    return settings, store


def build_chat_service(settings: Settings, store: SQLiteStore) -> GroundedChat:
    """Wire the assistant to OpenAI when configured, or to the grounded summarizer.

    The console always has a working chat: without a key, answers are assembled
    from the shift record itself rather than failing.
    """
    if not settings.openai_api_key:
        if settings.production_mode:
            raise RuntimeError("production requires live OpenAI chat")
        return GroundedChat(store)
    try:
        from openai import OpenAI

        return GroundedChat(
            store,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_merge_model,
            allow_fallback=True,
        )
    except Exception:  # noqa: BLE001 - a missing client must not break startup
        if settings.production_mode:
            raise
        return GroundedChat(store)


def build_ingest_service(
    settings: Settings,
    store: SQLiteStore,
    raw_root: Path,
    graph_writer: Neo4jGraphWriter | None = None,
    archive: S3Archive | None = None,
    embedder: BedrockMarengoEmbedder | None = None,
    evidence_enricher: StrandsEvidenceEnricher | None = None,
    escalation_scheduler: EventBridgeEscalationScheduler | None = None,
) -> VideoIngestService:
    def analyzer_factory():
        from .providers import TwelveLabsAnalyzer

        return TwelveLabsAnalyzer(
            settings.twelvelabs_api_key,
            model=settings.twelvelabs_model,
        )

    def fallback_analyzer_factory():
        from .providers import OpenAIFrameAnalyzer

        return OpenAIFrameAnalyzer(
            settings.openai_api_key,
            model=settings.openai_merge_model,
        )

    return VideoIngestService(
        store=store,
        raw_root=raw_root,
        analyzer_factory=analyzer_factory if settings.twelvelabs_api_key else None,
        fallback_analyzer_factory=(fallback_analyzer_factory if settings.openai_api_key else None),
        detector_config=settings.detector_config,
        fixture_mode=settings.fixture_mode,
        delivery_enabled=settings.alert_delivery_enabled,
        webhook_configured=bool(settings.slack_webhook_url),
        graph_writer=graph_writer,
        archive=archive,
        embedder=embedder,
        evidence_enricher=evidence_enricher,
        escalation_scheduler=escalation_scheduler,
        alert_ack_minutes=settings.alert_ack_minutes,
    )


def build_graph_reader(settings: Settings) -> Neo4jGraphReader | None:
    username = settings.neo4j_read_username or settings.neo4j_username
    password = settings.neo4j_read_password or settings.neo4j_password
    if not (settings.neo4j_uri and username and password):
        return None
    return Neo4jGraphReader(settings.neo4j_uri, username, password)


def build_graph_writer(settings: Settings) -> Neo4jGraphWriter | None:
    if settings.fixture_mode:
        return None
    if not (settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password):
        return None
    return Neo4jGraphWriter(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
    )


def _aws_session(settings: Settings, *, bedrock: bool = False) -> boto3.Session:
    kwargs = settings.bedrock_session_kwargs if bedrock else settings.aws_session_kwargs
    return boto3.Session(**kwargs)


def build_archive(settings: Settings) -> S3Archive | None:
    if not settings.aws_storage_enabled or not settings.aws_storage_configured:
        return None
    client = _aws_session(settings).client("s3")
    return S3Archive(
        S3BucketSet(
            raw=settings.s3_raw_bucket,
            analysis=settings.s3_analysis_bucket,
            clips=settings.s3_clips_bucket,
        ),
        region=settings.aws_region,
        client=client,
    )


def build_embedder(settings: Settings) -> BedrockMarengoEmbedder | None:
    if not settings.bedrock_embedding_enabled:
        return None
    client = _aws_session(settings, bedrock=True).client("bedrock-runtime")
    return BedrockMarengoEmbedder(
        model_id=settings.bedrock_marengo_model,
        region=settings.aws_region,
        client=client,
    )


def build_evidence_enricher(settings: Settings) -> StrandsEvidenceEnricher | None:
    if not settings.openai_enrichment_enabled or not settings.openai_api_key:
        return None
    return StrandsEvidenceEnricher(
        settings.openai_api_key,
        model=settings.openai_merge_model,
    )


def build_report_writer(settings: Settings) -> StrandsMorningReportWriter | None:
    if not settings.openai_enrichment_enabled or not settings.openai_api_key:
        return None
    return StrandsMorningReportWriter(
        settings.openai_api_key,
        model=settings.openai_report_model,
    )


def build_escalation_scheduler(
    settings: Settings,
) -> EventBridgeEscalationScheduler | None:
    if not settings.eventbridge_scheduler_configured:
        return None
    return EventBridgeEscalationScheduler(
        target_arn=settings.eventbridge_scheduler_target_arn,
        role_arn=settings.eventbridge_scheduler_role_arn,
        group_name=settings.eventbridge_scheduler_group,
        region=settings.aws_region,
        client=_aws_session(settings).client("scheduler"),
    )


def create_app(
    settings: Settings | None = None,
    store: SQLiteStore | None = None,
    graph_reader: Neo4jGraphReader | None = None,
    graph_writer: Neo4jGraphWriter | None = None,
    archive: S3Archive | None = None,
    embedder: BedrockMarengoEmbedder | None = None,
    evidence_enricher: StrandsEvidenceEnricher | None = None,
    report_writer: StrandsMorningReportWriter | None = None,
    escalation_scheduler: EventBridgeEscalationScheduler | None = None,
) -> FastAPI:
    if settings is None or store is None:
        settings, store = _services()
    else:
        store.initialize()
        if store.dump_table("animals") == [] and settings.fixture_mode:
            seed_demo(store, settings)
    app = FastAPI(
        title="ZooVision API",
        version="0.1.0",
        docs_url=None if settings.production_mode else "/docs",
        redoc_url=None if settings.production_mode else "/redoc",
        openapi_url=None if settings.production_mode else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_trusted_proxy(request, call_next):
        protected = request.url.path.startswith(("/api/", "/media/"))
        health_check = request.url.path == "/api/health"
        if protected and not health_check and settings.proxy_shared_secret:
            supplied = request.headers.get("x-zoovision-proxy-secret", "")
            if not hmac.compare_digest(supplied, settings.proxy_shared_secret):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "trusted frontend proxy required"},
                    headers={"cache-control": "no-store"},
                )
        return await call_next(request)

    raw_root = settings.storage_root / "raw"
    upload_root = raw_root / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=raw_root), name="media")
    chat_service = build_chat_service(settings, store)
    graph_reader = graph_reader or build_graph_reader(settings)
    graph_writer = graph_writer or build_graph_writer(settings)
    archive = archive or build_archive(settings)
    embedder = embedder or build_embedder(settings)
    evidence_enricher = evidence_enricher or build_evidence_enricher(settings)
    report_writer = report_writer or build_report_writer(settings)
    escalation_scheduler = escalation_scheduler or build_escalation_scheduler(settings)
    ingest_service = build_ingest_service(
        settings,
        store,
        raw_root,
        graph_writer,
        archive,
        embedder,
        evidence_enricher,
        escalation_scheduler,
    )
    if graph_reader is not None:
        app.router.add_event_handler("shutdown", graph_reader.close)
    if graph_writer is not None:
        app.router.add_event_handler("shutdown", graph_writer.close)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/readiness")
    def readiness() -> dict:
        provider_states = {
            "openai": _integration_state(
                configured=bool(settings.openai_api_key),
                enabled=settings.openai_enrichment_enabled,
            ),
            "twelvelabs": _integration_state(
                configured=bool(settings.twelvelabs_api_key),
                enabled=not settings.fixture_mode,
            ),
            "yolo": _integration_state(
                configured=bool(settings.yolo_model),
                enabled=settings.yolo_enabled,
            ),
            "aws_storage": _integration_state(
                configured=settings.aws_storage_configured,
                enabled=settings.aws_storage_enabled,
            ),
            "bedrock_marengo": _integration_state(
                configured=bool(embedder),
                enabled=settings.bedrock_embedding_enabled,
            ),
            "eventbridge_scheduler": _integration_state(
                configured=settings.eventbridge_scheduler_configured,
                enabled=settings.alert_delivery_enabled,
            ),
            "agentcore": _integration_state(
                configured=bool(settings.agentcore_runtime_arn),
                enabled=bool(settings.agentcore_runtime_arn),
            ),
            "neo4j": _neo4j_integration_state(
                graph_reader,
                write_enabled=graph_writer is not None,
            ),
            "slack": _integration_state(
                configured=bool(settings.slack_webhook_url),
                enabled=settings.alert_delivery_enabled and not settings.fixture_mode,
            ),
        }
        return {
            "status": "ready",
            "environment": settings.environment,
            "fixture_mode": settings.fixture_mode,
            "delivery_mode": "shadow" if settings.fixture_mode else "configured",
            "external_delivery_ready": (
                not settings.fixture_mode
                and provider_states["slack"]["status"] == "enabled_unverified"
            ),
            "providers": provider_states,
            "retention_days": {
                "raw": settings.raw_retention_days,
                "analysis": settings.analysis_retention_days,
                "clips": settings.clip_retention_days,
            },
        }

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        result = store.dashboard()
        for event in result["events"]:
            detail = store.event_detail(event["event_id"])
            if detail and detail["sources"]:
                source = detail["sources"][0]
                event["media_url"] = f"/media/{source['source_path']}"
                event["media_offset_seconds"] = source["source_offset_seconds"]
                event["evidence_kind"] = source["evidence_kind"]
        result["mode"] = {
            "fixture": settings.fixture_mode,
            "delivery": "shadow" if settings.fixture_mode else "configured",
        }
        return result

    @app.get("/api/events/{event_id}")
    def event_detail(event_id: str) -> dict:
        result = store.event_detail(event_id)
        if result is None:
            raise HTTPException(status_code=404, detail="event not found")
        detections: list[dict] = []
        seen_chunks: set[str] = set()
        for source in result["sources"]:
            source["media_url"] = f"/media/{source['source_path']}"
            if source["chunk_id"] not in seen_chunks:
                seen_chunks.add(source["chunk_id"])
                detections.extend(store.detections_for_chunk(source["chunk_id"]))
        result["detections"] = detections
        return result

    @app.get("/api/graph", response_model=GraphView)
    def graph(
        enclosure_id: str | None = Query(default=None, max_length=120),
        include_observations: bool = Query(default=True),
    ) -> GraphView:
        if graph_reader is None:
            raise HTTPException(status_code=503, detail="Neo4j graph is not configured")
        try:
            return build_graph_view(
                graph_reader,
                enclosure_id=enclosure_id,
                include_observations=include_observations,
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail="Neo4j graph is unavailable") from error

    @app.post("/api/chat", response_model=ChatReply)
    def chat(payload: ChatRequest) -> ChatReply:
        return chat_service.reply(payload)

    @app.get("/api/videos")
    def videos() -> dict:
        sources = store.video_sources()
        latest_jobs = store.latest_ingest_jobs_by_source()
        for source in sources:
            source["media_url"] = f"/media/{source['source_path']}"
            for field in ("animal_ids", "animal_names", "animal_species"):
                source[field] = sorted(set(filter(None, (source.get(field) or "").split(","))))
            source.update(
                _source_analysis_metadata(
                    source,
                    latest_jobs.get(Path(source["source_path"]).name),
                )
            )
        return {"videos": sources}

    @app.get("/api/videos/track")
    def video_track(source_path: str = Query(min_length=1, max_length=400)) -> dict:
        track = store.video_track(source_path)
        if not track["chunks"]:
            raise HTTPException(status_code=404, detail="no analyzed video for that source")
        track["media_url"] = f"/media/{source_path}"
        return track

    @app.get("/api/chunks/{chunk_id}/detections")
    def chunk_detections(chunk_id: str) -> dict:
        return {"chunk_id": chunk_id, "detections": store.detections_for_chunk(chunk_id)}

    @app.post("/api/ingest/upload")
    async def upload_video(file: UploadFile = UPLOADED_FILE) -> dict:
        name = Path(file.filename or "").name
        suffix = Path(name).suffix.lower()
        if not name or suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"supported video types are {sorted(ALLOWED_UPLOAD_SUFFIXES)}",
            )
        destination = upload_root / name
        written = 0
        try:
            with destination.open("wb") as handle:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="video exceeds the size limit")
                    handle.write(chunk)
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
        return {
            "source_name": name,
            "bytes": written,
            "media_url": f"/media/uploads/{name}",
        }

    @app.post("/api/ingest/upload/chunks")
    async def upload_video_chunk(
        file: UploadFile = UPLOADED_FILE,
        upload_id: str = UPLOAD_ID_FORM,
        filename: str = UPLOAD_NAME_FORM,
        chunk_index: int = UPLOAD_CHUNK_INDEX_FORM,
        chunk_count: int = UPLOAD_CHUNK_COUNT_FORM,
        total_bytes: int = UPLOAD_TOTAL_BYTES_FORM,
    ) -> dict:
        """Receive a bounded upload part and assemble it after the final part.

        Keeping each proxied request small avoids body-stream loss and gateway
        timeouts in the production Worker while retaining the same aggregate
        size and filename checks as the single-request endpoint.
        """
        try:
            canonical_upload_id = str(UUID(upload_id))
        except ValueError as error:
            raise HTTPException(status_code=422, detail="upload_id must be a UUID") from error
        if canonical_upload_id != upload_id.lower():
            raise HTTPException(status_code=422, detail="upload_id must use canonical UUID form")
        if chunk_index >= chunk_count:
            raise HTTPException(status_code=422, detail="chunk_index must be below chunk_count")

        name = Path(filename).name
        suffix = Path(name).suffix.lower()
        if not name or suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"supported video types are {sorted(ALLOWED_UPLOAD_SUFFIXES)}",
            )

        parts_root = upload_root / ".parts"
        upload_parts = parts_root / canonical_upload_id
        upload_parts.mkdir(parents=True, exist_ok=True)
        part_path = upload_parts / f"{chunk_index:04d}.part"
        written = 0
        try:
            with part_path.open("wb") as handle:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > MAX_UPLOAD_CHUNK_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="upload chunk exceeds the size limit",
                        )
                    handle.write(chunk)
        except HTTPException:
            part_path.unlink(missing_ok=True)
            raise

        received_parts = sorted(upload_parts.glob("*.part"))
        if len(received_parts) < chunk_count:
            return {
                "complete": False,
                "upload_id": canonical_upload_id,
                "received_chunks": len(received_parts),
                "chunk_count": chunk_count,
            }
        if len(received_parts) != chunk_count:
            shutil.rmtree(upload_parts, ignore_errors=True)
            raise HTTPException(status_code=409, detail="upload contains unexpected chunks")

        assembled_bytes = sum(part.stat().st_size for part in received_parts)
        if assembled_bytes != total_bytes or assembled_bytes > MAX_UPLOAD_BYTES:
            shutil.rmtree(upload_parts, ignore_errors=True)
            raise HTTPException(status_code=422, detail="assembled upload size does not match")

        destination = upload_root / name
        temporary = upload_root / f".{canonical_upload_id}.assembling"
        try:
            with temporary.open("wb") as output:
                for part in received_parts:
                    with part.open("rb") as source:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
            shutil.rmtree(upload_parts, ignore_errors=True)

        return {
            "complete": True,
            "source_name": name,
            "bytes": assembled_bytes,
            "media_url": f"/media/uploads/{name}",
        }

    @app.post("/api/ingest/jobs", response_model=IngestJob)
    def start_ingest(payload: IngestStartRequest) -> IngestJob:
        try:
            ingest_service.resolve_source(payload.source_name)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if not settings.twelvelabs_api_key:
            raise HTTPException(
                status_code=503,
                detail="TwelveLabs is required for video ingestion but is not configured",
            )
        start_ts = payload.start_ts or datetime.now(settings.timezone)
        if start_ts.tzinfo is None:
            start_ts = start_ts.replace(tzinfo=settings.timezone)
        return ingest_service.start(
            IngestRequest(
                source_name=payload.source_name,
                animal_id=payload.animal_id,
                animal_name=payload.animal_name,
                species=payload.species,
                enclosure_id=payload.enclosure_id,
                camera_id=payload.camera_id,
                start_ts=start_ts,
                shift_mode=payload.shift_mode,
                segment_seconds=payload.segment_seconds,
                max_segments=payload.max_segments,
            )
        )

    @app.get("/api/ingest/jobs")
    def list_ingest_jobs(limit: int = Query(default=20, ge=1, le=200)) -> dict:
        return {"jobs": [job.model_dump(mode="json") for job in ingest_service.recent(limit)]}

    @app.get("/api/ingest/jobs/{job_id}", response_model=IngestJob)
    def ingest_job(job_id: str) -> IngestJob:
        job = ingest_service.status(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="ingest job not found")
        return job

    @app.post(
        "/api/ingest/jobs/{job_id}/retry-gaps",
        response_model=IngestJob,
        status_code=202,
    )
    def retry_ingest_gaps(
        job_id: str,
        payload: IngestRequest | None = None,
    ) -> IngestJob:
        if not settings.twelvelabs_api_key:
            raise HTTPException(
                status_code=503,
                detail="TwelveLabs is required for provider gap retries",
            )
        try:
            return ingest_service.start_gap_retry(job_id, payload)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/alerts/{alert_id}/ack")
    def acknowledge(alert_id: str, payload: AckRequest) -> dict:
        schedule_name = store.alert_schedule_name(alert_id)
        changed = store.acknowledge_alert(
            alert_id,
            keeper=payload.keeper,
            acknowledged_at=datetime.now(UTC).isoformat(),
        )
        if not changed:
            raise HTTPException(status_code=409, detail="alert is not pending")
        schedule_status = "not_scheduled"
        if schedule_name and escalation_scheduler is not None:
            try:
                escalation_scheduler.cancel(schedule_name)
                schedule_status = "cancelled"
            except Exception:  # noqa: BLE001 - acknowledgement remains durable
                schedule_status = "cancel_failed"
        return {
            "status": "acknowledged",
            "alert_id": alert_id,
            "escalation_schedule": schedule_status,
        }

    @app.post("/api/events/{event_id}/outcomes")
    def outcome(event_id: str, payload: OutcomeRequest) -> dict:
        if store.event_detail(event_id) is None:
            raise HTTPException(status_code=404, detail="event not found")
        now = datetime.now(UTC)
        outcome_id = stable_id(
            "out",
            event_id,
            payload.resolution,
            payload.entered_by,
            now.isoformat(),
        )
        store.record_outcome(
            outcome_id=outcome_id,
            event_id=event_id,
            resolution=payload.resolution,
            note=payload.note,
            entered_by=payload.entered_by,
            created_at=now.isoformat(),
        )
        return {"status": "recorded", "outcome_id": outcome_id}

    @app.post("/api/animals/{animal_id}/baseline")
    def update_baseline(animal_id: str, payload: BaselineRequest) -> dict:
        animals = {row["animal_id"]: row for row in store.dump_table("animals")}
        animal = animals.get(animal_id)
        if animal is None:
            raise HTTPException(status_code=404, detail="animal not found")
        profiles = [
            row for row in store.dump_table("baseline_profiles") if row["animal_id"] == animal_id
        ]
        if payload.state == "active":
            if animal["baseline_state"] != "shadow":
                raise HTTPException(
                    status_code=409,
                    detail="only a reviewed shadow baseline can be activated",
                )
            if not profiles or min(row["n_day_shifts"] for row in profiles) < 7:
                raise HTTPException(
                    status_code=409,
                    detail="at least seven daytime shifts are required",
                )
        store.set_baseline_state(animal_id, payload.state)
        return {"animal_id": animal_id, "baseline_state": payload.state}

    @app.get("/api/morning-report")
    def morning_report() -> dict:
        report = store.morning_report()
        if report_writer is None:
            return {**report, "narrative": None, "narrative_mode": "not_configured"}
        request = MorningReportRequest(
            shift_label=datetime.now(settings.timezone).date().isoformat(),
            animals=[
                MorningAnimalFacts(
                    animal_id=animal["animal_id"],
                    animal_name=animal["name"],
                    event_facts=[
                        (
                            f"{event['behavior']} from {event['start_ts']} to {event['end_ts']}; "
                            f"rule {event['rule_fired']}"
                        )
                        for event in animal["events"]
                    ],
                    data_gap_facts=[
                        f"{gap['reason']} from {gap['start_ts']} to {gap['end_ts']}"
                        for gap in report["data_gaps"]
                        if gap["enclosure_id"] == animal["enclosure_id"]
                        and gap["reason"] != "bedrock_embedding_failed"
                    ],
                    no_notable_events=not animal["events"],
                )
                for animal in report["animals"]
            ],
        )
        narrative = report_writer.write(request)
        return {
            **report,
            "narrative": narrative.model_dump(mode="json"),
            "narrative_mode": "strands_openai",
        }

    @app.post("/api/demo/reset")
    def reset_demo() -> dict:
        if not settings.fixture_mode:
            raise HTTPException(status_code=404, detail="fixture mode is disabled")
        seed_demo(store, settings)
        return {"status": "reset"}

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (frontend_dist / path).resolve()
            if (
                candidate.is_relative_to(frontend_dist.resolve())
                and candidate.is_file()
                and candidate.name != "index.html"
            ):
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()


def media_root() -> Path:
    return _services()[0].storage_root / "raw"


def _integration_state(*, configured: bool, enabled: bool) -> dict[str, object]:
    if not configured:
        status = "not_configured"
    elif not enabled:
        status = "configured_disabled"
    else:
        status = "enabled_unverified"
    return {"configured": configured, "enabled": enabled, "status": status}


def _neo4j_integration_state(
    graph_reader: Neo4jGraphReader | None,
    *,
    write_enabled: bool,
) -> dict[str, object]:
    if graph_reader is None:
        return {
            "configured": False,
            "enabled": False,
            "status": "not_configured",
            "read_connected": False,
            "write_enabled": False,
        }
    try:
        graph_reader.verify_connectivity()
    except Exception:  # noqa: BLE001 - readiness must report, not expose driver details
        status = "unavailable"
        connected = False
    else:
        status = "healthy"
        connected = True
    return {
        "configured": True,
        "enabled": True,
        "status": status,
        "read_connected": connected,
        "write_enabled": write_enabled,
    }
