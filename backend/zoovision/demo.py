from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

from .baselines import calculate_baseline
from .detection import DetectorConfig, detections_for_chunk
from .domain import (
    AckState,
    Behavior,
    DataGap,
    Detection,
    EventRecord,
    EvidenceKind,
    Observation,
    Severity,
    ShiftMetric,
    ShiftMode,
    TriageInput,
)
from .ids import event_id, stable_id
from .settings import Settings
from .stitching import stitch_observations
from .store import SQLiteStore
from .triage import classify

ANIMALS = (
    {
        "animal_id": "animal-nox",
        "name": "Nox",
        "species": "African lion",
        "enclosure_id": "ENC-07",
        "baseline_state": "shadow",
    },
    {
        "animal_id": "animal-mara",
        "name": "Mara",
        "species": "African elephant",
        "enclosure_id": "ENC-05",
        "baseline_state": "active",
    },
    {
        "animal_id": "animal-juniper",
        "name": "Juniper",
        "species": "Mountain gorilla",
        "enclosure_id": "ENC-03",
        "baseline_state": "learning",
    },
)


def _night_anchor(settings: Settings, now: datetime | None = None) -> datetime:
    local_now = now.astimezone(settings.timezone) if now else datetime.now(settings.timezone)
    date = local_now.date()
    if local_now.timetz().replace(tzinfo=None) < time(6):
        date -= timedelta(days=1)
    else:
        date -= timedelta(days=1)
    return datetime.combine(date, time(19), tzinfo=settings.timezone)


def _day_metrics(
    animal_id: str,
    behavior: Behavior,
    count: int,
    anchor: datetime,
) -> list[ShiftMetric]:
    durations = (4.8, 5.4, 4.9, 5.8, 5.1, 4.6, 5.2, 5.5, 4.7, 5.0)
    return [
        ShiftMetric(
            shift_id=f"day-{animal_id}-{index}",
            animal_id=animal_id,
            behavior=behavior,
            mode=ShiftMode.DAY,
            shift_start=anchor - timedelta(days=count - index, hours=7),
            duration_minutes=durations[index],
            frequency=2 + (index % 2),
        )
        for index in range(count)
    ]


def seed_demo(store: SQLiteStore, settings: Settings, *, now: datetime | None = None) -> None:
    store.reset_demo()
    anchor = _night_anchor(settings, now)
    prepared = settings.storage_root / "raw" / "fixtures"

    for animal in ANIMALS:
        store.upsert_animal(**animal)

    baseline_specs = (
        ("animal-nox", Behavior.PACING, 8, False),
        ("animal-mara", Behavior.INACTIVITY, 10, True),
        ("animal-juniper", Behavior.WATER_BOWL_TIPPED, 4, False),
    )
    for animal_id, behavior, count, approved in baseline_specs:
        store.save_baseline(
            calculate_baseline(
                animal_id,
                behavior,
                _day_metrics(animal_id, behavior, count, anchor),
                approved=approved,
                now=anchor,
            )
        )

    chunks = (
        (
            "chunk-nox-01",
            "ENC-07",
            "CAM-07A",
            anchor + timedelta(hours=3, minutes=10),
            anchor + timedelta(hours=3, minutes=25),
            "enc07_lion_night_30m.mp4",
            0,
        ),
        (
            "chunk-nox-02",
            "ENC-07",
            "CAM-07A",
            anchor + timedelta(hours=3, minutes=25),
            anchor + timedelta(hours=3, minutes=40),
            "enc07_lion_night_30m.mp4",
            900,
        ),
        (
            "chunk-mara-01",
            "ENC-05",
            "CAM-05N",
            anchor + timedelta(hours=6),
            anchor + timedelta(hours=6, minutes=15),
            "enc05_elephant_15m.mp4",
            0,
        ),
        (
            "chunk-juniper-01",
            "ENC-03",
            "CAM-03Y",
            anchor + timedelta(hours=8),
            anchor + timedelta(hours=8, minutes=15),
            "enc03_mountain_gorilla_15m.mp4",
            15,
        ),
    )
    for chunk_id, enclosure_id, camera_id, start, end, filename, offset in chunks:
        path = prepared / filename
        store.upsert_video_chunk(
            chunk_id=chunk_id,
            enclosure_id=enclosure_id,
            camera_id=camera_id,
            start_ts=start.isoformat(),
            end_ts=end.isoformat(),
            source_path=f"fixtures/{filename}",
            source_offset_seconds=offset,
            content_sha256=_media_fingerprint(path),
            status="ready" if path.exists() else "fixture_missing",
        )
        store.save_detections(
            _fixture_detections(
                path,
                chunk_id,
                offset,
                detector_config=settings.detector_config,
            )
        )

    observations = [
        Observation(
            observation_id="obs-nox-pacing-01",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            chunk_id="chunk-nox-01",
            behavior=Behavior.PACING,
            start_ts=anchor + timedelta(hours=3, minutes=10),
            end_ts=anchor + timedelta(hours=3, minutes=25),
            confidence=0.92,
            evidence="Synthetic scenario: repeated route along the east boundary.",
            provider="fixture",
            provider_model="scenario-v1",
            provider_item_id="nox-route-a",
            evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
        ),
        Observation(
            observation_id="obs-nox-pacing-02",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            chunk_id="chunk-nox-02",
            behavior=Behavior.PACING,
            start_ts=anchor + timedelta(hours=3, minutes=25),
            end_ts=anchor + timedelta(hours=3, minutes=36, seconds=30),
            confidence=0.89,
            evidence="Synthetic scenario: the same route continued across the chunk boundary.",
            provider="fixture",
            provider_model="scenario-v1",
            provider_item_id="nox-route-b",
            evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
        ),
        Observation(
            observation_id="obs-mara-resting-01",
            animal_id="animal-mara",
            enclosure_id="ENC-05",
            chunk_id="chunk-mara-01",
            behavior=Behavior.RESTING,
            start_ts=anchor + timedelta(hours=6, minutes=1),
            end_ts=anchor + timedelta(hours=6, minutes=12),
            confidence=0.95,
            evidence="Synthetic scenario: stationary posture in the nest alcove.",
            provider="fixture",
            provider_model="scenario-v1",
            evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
        ),
        Observation(
            observation_id="obs-juniper-water-01",
            animal_id="animal-juniper",
            enclosure_id="ENC-03",
            chunk_id="chunk-juniper-01",
            behavior=Behavior.WATER_BOWL_TIPPED,
            start_ts=anchor + timedelta(hours=8, minutes=4),
            end_ts=anchor + timedelta(hours=8, minutes=5),
            confidence=0.87,
            evidence="Synthetic scenario: the water bowl changed from upright to its side.",
            provider="fixture",
            provider_model="scenario-v1",
            evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
        ),
    ]
    for observation in observations:
        store.save_observation(observation)

    for stitched in stitch_observations(observations):
        context = {
            Behavior.PACING: {"hours_since_water_contact": 7.4},
            Behavior.WATER_BOWL_TIPPED: {},
        }.get(stitched.behavior, {})
        decision = classify(
            TriageInput(
                animal_id=stitched.animal_id,
                behavior=stitched.behavior,
                continuous_duration_minutes=stitched.duration_minutes,
                source_observation_ids=stitched.source_observation_ids,
                **context,
            )
        )
        if decision.severity is Severity.NONE:
            continue
        stable_event_id = event_id(
            stitched.animal_id,
            stitched.behavior,
            stitched.source_observation_ids,
            decision.rule_version,
        )
        store.save_event(
            EventRecord(
                event_id=stable_event_id,
                animal_id=stitched.animal_id,
                enclosure_id=stitched.enclosure_id,
                behavior=stitched.behavior,
                start_ts=stitched.start_ts,
                end_ts=stitched.end_ts,
                severity=decision.severity,
                rule_fired=decision.rule_fired,
                action=decision.action,
                confidence=stitched.confidence,
                source_observation_ids=stitched.source_observation_ids,
                explanation_facts=decision.explanation_facts,
                rule_version=decision.rule_version,
                shift_mode=ShiftMode.NIGHT,
                created_at=anchor + timedelta(hours=12),
            )
        )
        store.save_alert(
            alert_id=stable_id("alt", stable_event_id, "shadow-console"),
            event_id=stable_event_id,
            channel="keeper_console",
            delivery_status="shadowed",
            ack_state=AckState.PENDING.value,
        )

    store.save_data_gap(
        DataGap(
            gap_id=stable_id("gap", "ENC-05", anchor.isoformat()),
            enclosure_id="ENC-05",
            chunk_id="chunk-mara-01",
            start_ts=anchor + timedelta(hours=9),
            end_ts=anchor + timedelta(hours=9, minutes=18),
            reason="camera_signal_loss",
            detail="The fixture scenario records an 18-minute coverage gap.",
        )
    )


#: Seeding runs at first console start, so fixture motion is measured over a
#: bounded window rather than a whole 15-minute chunk.
FIXTURE_DETECTION_SECONDS = 120.0


def _fixture_detections(
    path: Path,
    chunk_id: str,
    offset: float,
    *,
    detector_config: DetectorConfig,
) -> list[Detection]:
    """Measure real object and motion regions for a fixture chunk.

    The observations seeded alongside these are synthetic scenarios, but the
    boxes are measured from the actual licensed footage, so the console's
    overlay always reflects real pixels. A missing or unreadable fixture yields
    no boxes rather than invented ones.
    """
    if not path.exists():
        return []
    try:
        return detections_for_chunk(
            path,
            chunk_id=chunk_id,
            start_seconds=offset,
            duration_seconds=FIXTURE_DETECTION_SECONDS,
            config=detector_config,
        )
    except (ValueError, OSError):
        return []


def _media_fingerprint(path: Path) -> str:
    if not path.exists():
        return "fixture-not-prepared"
    stat = path.stat()
    return stable_id("media", path.name, stat.st_size)
