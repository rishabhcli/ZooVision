from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .chat import ChatReply, ChatRequest, GroundedChat
from .demo import seed_demo
from .graphview import GraphView, build_graph_view
from .ids import stable_id
from .ingest import IngestJob, IngestRequest, VideoIngestService
from .settings import Settings, get_settings
from .store import SQLiteStore

#: Container types the ingest path accepts. ffprobe still validates the bytes.
ALLOWED_UPLOAD_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
UPLOADED_FILE = File(...)


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
    max_segments: int = Field(default=12, ge=1, le=240)
    use_provider: bool = True


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
        return GroundedChat(store)
    try:
        from openai import OpenAI

        return GroundedChat(
            store,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_merge_model,
        )
    except Exception:  # noqa: BLE001 - a missing client must not break startup
        return GroundedChat(store)


def build_ingest_service(
    settings: Settings,
    store: SQLiteStore,
    raw_root: Path,
) -> VideoIngestService:
    def analyzer_factory():
        from .providers import TwelveLabsAnalyzer

        return TwelveLabsAnalyzer(
            settings.twelvelabs_api_key,
            model=settings.twelvelabs_model,
        )

    return VideoIngestService(
        store=store,
        raw_root=raw_root,
        analyzer_factory=analyzer_factory if settings.twelvelabs_api_key else None,
        fixture_mode=settings.fixture_mode,
        delivery_enabled=settings.alert_delivery_enabled,
        webhook_configured=bool(settings.slack_webhook_url),
    )


def create_app(
    settings: Settings | None = None,
    store: SQLiteStore | None = None,
) -> FastAPI:
    if settings is None or store is None:
        settings, store = _services()
    else:
        store.initialize()
        if store.dump_table("animals") == [] and settings.fixture_mode:
            seed_demo(store, settings)
    app = FastAPI(title="ZooVision API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    raw_root = settings.storage_root / "raw"
    upload_root = raw_root / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=raw_root), name="media")
    chat_service = build_chat_service(settings, store)
    ingest_service = build_ingest_service(settings, store, raw_root)

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
            "aws_storage": _integration_state(
                configured=settings.aws_storage_configured,
                enabled=settings.aws_storage_enabled,
            ),
            "neo4j": _integration_state(
                configured=bool(
                    settings.neo4j_uri and settings.neo4j_username and settings.neo4j_password
                ),
                enabled=not settings.fixture_mode,
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
        return build_graph_view(
            store,
            enclosure_id=enclosure_id,
            include_observations=include_observations,
        )

    @app.post("/api/chat", response_model=ChatReply)
    def chat(payload: ChatRequest) -> ChatReply:
        return chat_service.reply(payload)

    @app.get("/api/videos")
    def videos() -> dict:
        sources = store.video_sources()
        for source in sources:
            source["media_url"] = f"/media/{source['source_path']}"
            source["animal_names"] = sorted(
                set(filter(None, (source.get("animal_names") or "").split(",")))
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

    @app.post("/api/ingest/jobs", response_model=IngestJob)
    def start_ingest(payload: IngestStartRequest) -> IngestJob:
        try:
            ingest_service.resolve_source(payload.source_name)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
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
                use_provider=payload.use_provider and bool(settings.twelvelabs_api_key),
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

    @app.post("/api/alerts/{alert_id}/ack")
    def acknowledge(alert_id: str, payload: AckRequest) -> dict:
        changed = store.acknowledge_alert(
            alert_id,
            keeper=payload.keeper,
            acknowledged_at=datetime.now(UTC).isoformat(),
        )
        if not changed:
            raise HTTPException(status_code=409, detail="alert is not pending")
        return {"status": "acknowledged", "alert_id": alert_id}

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
        return store.morning_report()

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
