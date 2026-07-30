from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .demo import seed_demo
from .ids import stable_id
from .settings import Settings, get_settings
from .store import SQLiteStore


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


@lru_cache
def _services() -> tuple[Settings, SQLiteStore]:
    settings = get_settings()
    store = SQLiteStore(settings.database_path)
    store.initialize()
    if store.dump_table("animals") == [] and settings.fixture_mode:
        seed_demo(store, settings)
    return settings, store


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
    raw_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=raw_root), name="media")

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
        for source in result["sources"]:
            source["media_url"] = f"/media/{source['source_path']}"
        return result

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
