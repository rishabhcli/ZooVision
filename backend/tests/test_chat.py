from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import zoovision.chat as chat_module
from zoovision.chat import (
    ChatAnswer,
    ChatMessage,
    ChatReply,
    ChatRequest,
    GroundedChat,
    build_context,
    retrieve_context,
    summarize,
)
from zoovision.domain import (
    Behavior,
    DataGap,
    EventRecord,
    EvidenceKind,
    Observation,
    Severity,
    ShiftMode,
)
from zoovision.store import SQLiteStore

START = datetime(2026, 7, 30, 2, 0, tzinfo=UTC)


def _seeded_store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "chat.db")
    store.initialize()
    store.upsert_animal(
        animal_id="animal-nox",
        name="Nox",
        species="European badger",
        enclosure_id="ENC-07",
        baseline_state="shadow",
    )
    store.upsert_animal(
        animal_id="animal-quiet",
        name="Juniper",
        species="Domestic cat",
        enclosure_id="ENC-03",
        baseline_state="learning",
    )
    store.upsert_video_chunk(
        chunk_id="chunk-1",
        enclosure_id="ENC-07",
        camera_id="CAM-07A",
        start_ts=START.isoformat(),
        end_ts=(START + timedelta(minutes=15)).isoformat(),
        source_path="fixtures/badger.mp4",
        source_offset_seconds=0,
        content_sha256="sha",
        status="ready",
    )
    store.save_observation(
        Observation(
            observation_id="obs-1",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            chunk_id="chunk-1",
            behavior=Behavior.PACING,
            start_ts=START,
            end_ts=START + timedelta(minutes=12),
            confidence=0.92,
            evidence="Synthetic scenario: repeated route along the east boundary.",
            provider="fixture",
            provider_model="scenario-v1",
            evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
        )
    )
    store.save_event(
        EventRecord(
            event_id="evt-1",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            behavior=Behavior.PACING,
            start_ts=START,
            end_ts=START + timedelta(minutes=12),
            severity=Severity.MODERATE,
            rule_fired="R005_PACING_10M",
            action=None,
            confidence=0.92,
            source_observation_ids=["obs-1"],
            explanation_facts=["Continuous pacing lasted 12.0 minutes."],
            rule_version="test.v1",
            shift_mode=ShiftMode.NIGHT,
            created_at=START,
        )
    )
    store.save_alert(
        alert_id="alt-1",
        event_id="evt-1",
        channel="keeper_console",
        delivery_status="shadowed",
        ack_state="pending",
    )
    store.save_data_gap(
        DataGap(
            gap_id="gap-1",
            enclosure_id="ENC-07",
            chunk_id="chunk-1",
            start_ts=START + timedelta(hours=1),
            end_ts=START + timedelta(hours=1, minutes=18),
            reason="camera_signal_loss",
            detail="Eighteen minutes of coverage were lost.",
        )
    )
    return store


def _temporal_squirrel_store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "temporal-chat.db")
    store.initialize()
    store.upsert_animal(
        animal_id="animal-backyard",
        name="Squirrel staircase wildlife",
        species="Eastern gray squirrel and backyard birds",
        enclosure_id="ENC-BACKYARD",
        baseline_state="shadow",
    )
    chunk_start = START + timedelta(minutes=32)
    store.upsert_video_chunk(
        chunk_id="chunk-near-33m",
        enclosure_id="ENC-BACKYARD",
        camera_id="CAM-BY1",
        start_ts=chunk_start.isoformat(),
        end_ts=(chunk_start + timedelta(minutes=2)).isoformat(),
        source_path="uploads/backyard-squirrel-staircase.mp4",
        source_offset_seconds=32 * 60,
        content_sha256="sha-staircase",
        status="analyzed",
    )
    store.save_observation(
        Observation(
            observation_id="obs-near-33m",
            animal_id="animal-backyard",
            enclosure_id="ENC-BACKYARD",
            chunk_id="chunk-near-33m",
            behavior=Behavior.EATING,
            start_ts=chunk_start + timedelta(seconds=55),
            end_ts=chunk_start + timedelta(seconds=63),
            confidence=0.91,
            evidence="A sparrow flies onto the platform and begins eating seeds.",
            provider="twelvelabs",
            provider_model="test",
            evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            activity_label="One sparrow eating seeds on the platform",
        )
    )
    store.save_observation(
        Observation(
            observation_id="obs-after-33m",
            animal_id="animal-backyard",
            enclosure_id="ENC-BACKYARD",
            chunk_id="chunk-near-33m",
            behavior=Behavior.FORAGING,
            start_ts=chunk_start + timedelta(seconds=64),
            end_ts=chunk_start + timedelta(seconds=77),
            confidence=0.89,
            evidence="A second sparrow joins on the ground.",
            provider="twelvelabs",
            provider_model="test",
            evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            activity_label="Two sparrows foraging near the platform",
        )
    )
    store.save_data_gap(
        DataGap(
            gap_id="gap-embedding-near-33m",
            enclosure_id="ENC-BACKYARD",
            chunk_id="chunk-near-33m",
            start_ts=chunk_start,
            end_ts=chunk_start + timedelta(minutes=2),
            reason="bedrock_embedding_failed",
            detail="Vector indexing failed after structured analysis completed.",
        )
    )

    store.upsert_video_chunk(
        chunk_id="chunk-other-camera-33m",
        enclosure_id="ENC-BACKYARD",
        camera_id="CAM-BY2",
        start_ts=chunk_start.isoformat(),
        end_ts=(chunk_start + timedelta(minutes=2)).isoformat(),
        source_path="uploads/backyard-squirrels-and-birds.mp4",
        source_offset_seconds=32 * 60,
        content_sha256="sha-feeder",
        status="analyzed",
    )
    store.save_observation(
        Observation(
            observation_id="obs-other-camera-33m",
            animal_id="animal-backyard",
            enclosure_id="ENC-BACKYARD",
            chunk_id="chunk-other-camera-33m",
            behavior=Behavior.WALKING,
            start_ts=chunk_start + timedelta(seconds=58),
            end_ts=chunk_start + timedelta(seconds=66),
            confidence=0.93,
            evidence="A squirrel walks across the feeder camera.",
            provider="twelvelabs",
            provider_model="test",
            evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            activity_label="One squirrel walking across the feeder",
        )
    )
    return store


def _backyard_bird_timing_context() -> dict[str, Any]:
    base_moment = {
        "animal_id": "animal-backyard",
        "animal_name": "Backyard squirrels and birds",
        "species": "Eastern gray squirrel and backyard birds",
        "enclosure_id": "ENC-BACKYARD",
        "camera_id": "CAM-BY2",
        "source_path": "uploads/backyard-squirrels-and-birds.mp4",
        "behavior": "foraging",
        "evidence_kind": "provider_structured",
    }
    moments = [
        {
            **base_moment,
            "observation_id": f"obs-squirrel-{index:02d}",
            "activity_label": "One squirrel foraging",
            "evidence": "One squirrel is visible foraging for seeds.",
            "start_seconds": float(index * 100),
            "end_seconds": float(index * 100 + 50),
        }
        for index in range(25)
    ]
    bird_intervals = [
        (
            "obs-bird-41m49",
            2509.475,
            2518.475,
            "Two pigeons forage on scattered seed in the foreground.",
        ),
        (
            "obs-bird-42m43",
            2563.6,
            2644.384,
            "One squirrel foraging while two birds forage in the background.",
        ),
        ("obs-bird-46m23", 2783.168, 2800.168, "One bird forages briefly."),
        ("obs-bird-46m40", 2800.168, 2809.168, "One bird forages briefly."),
        (
            "obs-bird-1h05m52",
            3951.588,
            3962.372,
            "Two birds enter and forage while one squirrel continues foraging.",
        ),
        (
            "obs-bird-1h06m02",
            3962.372,
            4087.472,
            "Two birds forage for seeds in the background.",
        ),
        (
            "obs-bird-1h08m21",
            4101.497,
            4109.497,
            "One sparrow enters the frame and forages nearby.",
        ),
        (
            "obs-bird-1h08m29",
            4109.497,
            4204.281,
            "One squirrel and one sparrow forage together.",
        ),
        (
            "obs-bird-1h10m32",
            4232.281,
            4236.281,
            "One bird enters from the right and forages with one squirrel.",
        ),
        (
            "obs-bird-1h10m36",
            4236.281,
            4247.281,
            "One squirrel and one bird forage; a second bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h10m47",
            4247.281,
            4265.281,
            "One squirrel and two birds forage; a third bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h11m05",
            4265.281,
            4276.281,
            "One squirrel and three birds forage; a fourth bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h11m16",
            4276.281,
            4288.281,
            "One squirrel and four birds forage; a fifth bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h11m28",
            4288.281,
            4300.281,
            "One squirrel and five birds forage; a sixth bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h11m40",
            4300.281,
            4312.281,
            "One squirrel and six birds forage; a seventh bird enters and begins foraging.",
        ),
        (
            "obs-bird-1h11m52",
            4312.281,
            4321.065,
            "One squirrel and seven birds continue foraging.",
        ),
    ]
    moments.extend(
        {
            **base_moment,
            "observation_id": observation_id,
            "activity_label": evidence,
            "evidence": evidence,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
        }
        for observation_id, start_seconds, end_seconds, evidence in bird_intervals
    )
    return {
        "scope": {
            "enclosure_id": "ENC-BACKYARD",
            "animal_id": "animal-backyard",
            "camera_id": "CAM-BY2",
            "source_path": "uploads/backyard-squirrels-and-birds.mp4",
        },
        "animals": [
            {
                "animal_id": "animal-backyard",
                "name": "Backyard squirrels and birds",
                "species": "Eastern gray squirrel and backyard birds",
                "enclosure_id": "ENC-BACKYARD",
                "baseline_state": "shadow",
                "baseline_day_shifts": 0,
                "event_count": 0,
            }
        ],
        "events": [],
        "moments": moments,
        "data_gaps": [],
        "recording_summary": {
            "source_path": "uploads/backyard-squirrels-and-birds.mp4",
            "camera_id": "CAM-BY2",
            "observation_count": len(moments),
            "event_count": 0,
            "coverage_gap_count": 0,
            "indexing_gap_count": 0,
        },
        "policy": {},
    }


def test_context_includes_events_animals_and_gaps(tmp_path: Path) -> None:
    context = build_context(_seeded_store(tmp_path))

    assert {a["name"] for a in context["animals"]} == {"Nox", "Juniper"}
    assert context["events"][0]["rule_fired"] == "R005_PACING_10M"
    assert context["events"][0]["sources"][0]["observation_id"] == "obs-1"
    assert context["data_gaps"][0]["gap_id"] == "gap-1"


def test_context_scopes_to_one_enclosure(tmp_path: Path) -> None:
    context = build_context(_seeded_store(tmp_path), enclosure_id="ENC-03")

    assert [a["name"] for a in context["animals"]] == ["Juniper"]
    assert context["events"] == []


def test_context_scopes_to_the_exact_selected_video(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    store.upsert_video_chunk(
        chunk_id="chunk-2",
        enclosure_id="ENC-07",
        camera_id="CAM-07B",
        start_ts=START.isoformat(),
        end_ts=(START + timedelta(minutes=15)).isoformat(),
        source_path="fixtures/badger-secondary.mp4",
        source_offset_seconds=0,
        content_sha256="sha-secondary",
        status="ready",
    )
    store.save_observation(
        Observation(
            observation_id="obs-2",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            chunk_id="chunk-2",
            behavior=Behavior.WALKING,
            start_ts=START + timedelta(minutes=2),
            end_ts=START + timedelta(minutes=3),
            confidence=0.88,
            evidence="Nox walked beside the secondary camera.",
            provider="twelvelabs",
            provider_model="test",
            evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            activity_label="Walking beside the fence",
        )
    )
    store.save_event(
        EventRecord(
            event_id="evt-cross-camera",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            behavior=Behavior.WALKING,
            start_ts=START,
            end_ts=START + timedelta(minutes=3),
            severity=Severity.MODERATE,
            rule_fired="R_TEST_CROSS_CAMERA",
            action=None,
            confidence=0.88,
            source_observation_ids=["obs-1", "obs-2"],
            explanation_facts=["The event spans two camera records."],
            rule_version="test.v1",
            shift_mode=ShiftMode.NIGHT,
            created_at=START,
        )
    )

    context = build_context(
        store,
        enclosure_id="ENC-07",
        animal_id="animal-nox",
        camera_id="CAM-07B",
        source_path="fixtures/badger-secondary.mp4",
    )

    assert context["scope"]["camera_id"] == "CAM-07B"
    assert context["scope"]["source_path"] == "fixtures/badger-secondary.mp4"
    assert [moment["observation_id"] for moment in context["moments"]] == ["obs-2"]
    assert [event["event_id"] for event in context["events"]] == ["evt-cross-camera"]
    assert [source["observation_id"] for source in context["events"][0]["sources"]] == ["obs-2"]
    assert context["data_gaps"] == []
    assert context["recording_summary"] == {
        "source_path": "fixtures/badger-secondary.mp4",
        "camera_id": "CAM-07B",
        "observation_count": 1,
        "event_count": 1,
        "coverage_gap_count": 0,
        "indexing_gap_count": 0,
    }


def test_deterministic_answer_quotes_the_rule_and_cites_the_event(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    reply = GroundedChat(store).reply(
        ChatRequest(messages=[ChatMessage(role="user", content="What happened to Nox tonight?")])
    )

    assert reply.mode == "deterministic"
    assert "R005_PACING_10M" in reply.answer
    assert "MODERATE" in reply.answer
    assert "evt-1" in reply.cited_ids
    assert reply.context_record_count > 0


def test_retrieval_does_not_return_unrelated_tags_for_unknown_question(tmp_path: Path) -> None:
    context = retrieve_context(
        build_context(_seeded_store(tmp_path)),
        [ChatMessage(role="user", content="What is tomorrow's weather?")],
    )

    assert context["events"] == []
    assert context["moments"] == []
    assert context["data_gaps"] == []


def test_recording_inventory_keeps_late_animal_types_inside_context_cap() -> None:
    moments: list[dict[str, Any]] = []
    for index in range(24):
        moments.append(
            {
                "observation_id": f"obs-squirrel-{index:02d}",
                "animal_id": "animal-backyard",
                "animal_name": "Backyard wildlife",
                "species": "Eastern gray squirrel and backyard birds",
                "enclosure_id": "ENC-BACKYARD",
                "camera_id": "CAM-BY2",
                "source_path": "uploads/backyard-squirrels-and-birds.mp4",
                "behavior": "foraging",
                "activity_label": "One squirrel foraging",
                "evidence": "One squirrel is visible foraging for seeds.",
                "evidence_kind": "provider_structured",
                "start_seconds": float(index * 60),
                "end_seconds": float(index * 60 + 50),
            }
        )
    moments.append(
        {
            **moments[-1],
            "observation_id": "obs-birds-late",
            "activity_label": "Two birds foraging",
            "evidence": "Two birds are visible foraging in the background.",
            "start_seconds": 2_400.0,
            "end_seconds": 2_480.0,
        }
    )
    full_context = {
        "scope": {
            "enclosure_id": "ENC-BACKYARD",
            "animal_id": "animal-backyard",
            "camera_id": "CAM-BY2",
            "source_path": "uploads/backyard-squirrels-and-birds.mp4",
        },
        "animals": [
            {
                "animal_id": "animal-backyard",
                "name": "Backyard wildlife",
                "species": "Eastern gray squirrel and backyard birds",
                "enclosure_id": "ENC-BACKYARD",
                "baseline_state": "shadow",
                "baseline_day_shifts": 0,
                "event_count": 0,
            }
        ],
        "events": [],
        "moments": moments,
        "data_gaps": [],
        "policy": {},
    }

    context = retrieve_context(
        full_context,
        [
            ChatMessage(
                role="user",
                content="What animals are visible in this recording, and what are they doing?",
            )
        ],
    )

    selected_ids = {moment["observation_id"] for moment in context["moments"]}
    assert context["retrieval"]["recording_inventory"] is True
    assert len(context["moments"]) == 20
    assert "obs-birds-late" in selected_ids
    assert any(record_id.startswith("obs-squirrel-") for record_id in selected_ids)

    activity_context = retrieve_context(
        full_context,
        [
            ChatMessage(
                role="user",
                content="What does this animal usually do across this recording?",
            )
        ],
    )
    activity_ids = {moment["observation_id"] for moment in activity_context["moments"]}
    assert activity_context["retrieval"]["recording_inventory"] is True
    assert "obs-birds-late" in activity_ids


def test_recording_inventory_reply_is_timeline_wide_and_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _StubClient(RuntimeError("recording inventory must not call the model"))
    monkeypatch.setattr(
        chat_module,
        "build_context",
        lambda *_args, **_kwargs: _backyard_bird_timing_context(),
    )

    reply = GroundedChat(
        _seeded_store(tmp_path),
        client=client,
        model="gpt-test",
    ).reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content=(
                        "What animals and activities were documented across this full recording?"
                    ),
                )
            ],
            animal_id="animal-backyard",
            enclosure_id="ENC-BACKYARD",
            camera_id="CAM-BY2",
            source_path="uploads/backyard-squirrels-and-birds.mp4",
        )
    )

    assert reply.mode == "deterministic"
    assert client.responses.calls == []
    assert "Birds: foraging" in reply.answer
    assert "Squirrels: foraging" in reply.answer
    assert "41 structured observations" in reply.answer
    assert "0 deterministic rule events" in reply.answer
    assert "1:11:52" in reply.answer
    assert reply.uncertainty == []
    assert len(reply.cited_ids) == 20
    assert any(moment.observation_id.startswith("obs-bird-") for moment in reply.moments)
    assert any(moment.observation_id == "obs-bird-1h11m52" for moment in reply.moments)


def test_recording_inventory_reserves_rare_cat_from_generic_wildlife_profile() -> None:
    base_moment = {
        "animal_id": "animal-trail",
        "animal_name": "Trail camera wildlife",
        "species": "Unspecified wildlife",
        "enclosure_id": "ENC-03",
        "camera_id": "CAM-03T",
        "source_path": "uploads/trail-camera.mp4",
        "behavior": "foraging",
        "evidence_kind": "provider_structured",
    }
    moments = [
        {
            **base_moment,
            "observation_id": f"obs-bird-{index:02d}",
            "activity_label": "One bird foraging",
            "evidence": "One bird is visible foraging.",
            "start_seconds": float(index * 60),
            "end_seconds": float(index * 60 + 20),
        }
        for index in range(24)
    ]
    moments.append(
        {
            **base_moment,
            "observation_id": "obs-cat-rare",
            "behavior": "walking",
            "activity_label": "One cat walking past the trail camera",
            "evidence": "A cat walks across the frame.",
            "start_seconds": 2_400.0,
            "end_seconds": 2_415.0,
        }
    )
    full_context = {
        "scope": {
            "enclosure_id": "ENC-03",
            "animal_id": "animal-trail",
            "camera_id": "CAM-03T",
            "source_path": "uploads/trail-camera.mp4",
        },
        "animals": [
            {
                "animal_id": "animal-trail",
                "name": "Trail camera wildlife",
                "species": "Unspecified wildlife",
                "enclosure_id": "ENC-03",
                "baseline_state": "shadow",
                "baseline_day_shifts": 0,
                "event_count": 0,
            }
        ],
        "events": [],
        "moments": moments,
        "data_gaps": [],
        "recording_summary": {
            "source_path": "uploads/trail-camera.mp4",
            "camera_id": "CAM-03T",
            "observation_count": len(moments),
            "event_count": 0,
            "coverage_gap_count": 0,
            "indexing_gap_count": 0,
        },
        "policy": {},
    }
    messages = [
        ChatMessage(
            role="user",
            content="What animals are visible in this recording, and what are they doing?",
        )
    ]

    context = retrieve_context(full_context, messages)
    reply = summarize(context, messages)

    assert "obs-cat-rare" in {moment["observation_id"] for moment in context["moments"]}
    assert "Birds: foraging" in reply.answer
    assert "Cats: walking" in reply.answer
    assert "obs-cat-rare" in reply.cited_ids
    assert "obs-cat-rare" in reply.moment_ids


def test_recording_inventory_does_not_turn_no_animal_evidence_into_activity() -> None:
    moment = {
        "observation_id": "obs-empty-frame",
        "animal_id": "animal-trail",
        "animal_name": "Trail camera wildlife",
        "species": "Unspecified wildlife",
        "enclosure_id": "ENC-03",
        "camera_id": "CAM-03T",
        "source_path": "uploads/trail-camera.mp4",
        "behavior": "inactivity",
        "activity_label": "No animal visible",
        "evidence": "No animal is visible in the frame.",
        "evidence_kind": "provider_structured",
        "start_seconds": 0.0,
        "end_seconds": 60.0,
    }
    context = {
        "animals": [
            {
                "animal_id": "animal-trail",
                "name": "Trail camera wildlife",
                "species": "Unspecified wildlife",
                "enclosure_id": "ENC-03",
                "baseline_state": "shadow",
                "baseline_day_shifts": 0,
                "event_count": 0,
            }
        ],
        "events": [],
        "moments": [moment],
        "data_gaps": [],
        "recording_summary": {
            "observation_count": 1,
            "event_count": 0,
        },
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "does not explicitly identify an animal" in reply.answer
    assert "Recorded animal activity" not in reply.answer
    assert "1 structured observation and 0 deterministic rule events" in reply.answer
    assert reply.cited_ids == ["obs-empty-frame"]
    assert reply.uncertainty == ["The available structured text does not identify an animal type."]


@pytest.mark.parametrize(
    ("activity_label", "evidence", "animal_heading"),
    [
        (
            "No animals visible; static brick bird feeder",
            "The empty scene contains a brick bird feeder and scattered seed.",
            "Birds:",
        ),
        (
            "No animals visible beside the cat flap",
            "The doorway and cat flap remain in view, with no animal present.",
            "Cats:",
        ),
    ],
)
def test_recording_inventory_ignores_animal_words_in_environment_labels(
    activity_label: str,
    evidence: str,
    animal_heading: str,
) -> None:
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [
            {
                "observation_id": "obs-empty-environment",
                "behavior": "inactivity",
                "activity_label": activity_label,
                "evidence": evidence,
                "start_seconds": 0.0,
                "end_seconds": 30.0,
            }
        ],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert animal_heading not in reply.answer
    assert "does not explicitly identify an animal" in reply.answer
    assert reply.uncertainty


def test_recording_inventory_keeps_bird_observed_on_feeder() -> None:
    context = {
        "animals": [{"name": "Backyard wildlife", "event_count": 0}],
        "events": [],
        "moments": [
            {
                "observation_id": "obs-bird-on-feeder",
                "behavior": "foraging",
                "activity_label": "One bird foraging on the feeder",
                "evidence": "A bird is visible on the feeder, pecking at seeds.",
                "start_seconds": 30.0,
                "end_seconds": 40.0,
            }
        ],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "Birds: foraging" in reply.answer
    assert reply.uncertainty == []


@pytest.mark.parametrize(
    ("activity_label", "evidence"),
    [
        ("No cat visible", "No cat is visible anywhere in the frame."),
        ("No birds or cats were observed", "No birds or cats were observed in this clip."),
        ("Cat absent", "The cat is absent from the frame."),
        ("No cat in frame", "No cat in frame."),
        ("Cat not in frame", "The cat is not in the frame."),
        ("Neither cat nor bird visible", "Neither a cat nor a bird is visible."),
        (
            "Animal identity uncertain",
            "The animal is not clearly identifiable as a cat.",
        ),
        (
            "Animal identity uncertain",
            "The animal is not clearly identifiable as either a cat or a bird.",
        ),
    ],
)
def test_recording_inventory_ignores_negated_species_mentions(
    activity_label: str,
    evidence: str,
) -> None:
    moment = {
        "observation_id": "obs-negative-animal",
        "behavior": "inactivity",
        "activity_label": activity_label,
        "evidence": evidence,
        "start_seconds": 0.0,
        "end_seconds": 30.0,
    }
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [moment],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "Cats:" not in reply.answer
    assert "Birds:" not in reply.answer
    assert "does not explicitly identify an animal" in reply.answer
    assert reply.uncertainty


@pytest.mark.parametrize(
    ("activity_label", "evidence", "possible_heading"),
    [
        (
            "Possible cat walking",
            "The animal may be a cat, but identity is uncertain.",
            "Possible cats:",
        ),
        (
            "Possible squirrel moving",
            "Possibly a squirrel is moving through the frame.",
            "Possible squirrels:",
        ),
        (
            "Possible bird walking",
            "The reviewer cannot confirm whether this is a bird.",
            "Possible birds:",
        ),
        (
            "Bird-like animal moving",
            "A bird-like animal moves across the grass; species identity is uncertain.",
            "Possible birds:",
        ),
        ("Animal walking", "The animal looks like a cat.", "Possible cats:"),
        ("Animal walking", "The animal seems to be a cat.", "Possible cats:"),
        ("Animal walking", "The animal is probably a cat.", "Possible cats:"),
        ("Animal walking", "The animal resembles a cat.", "Possible cats:"),
    ],
)
def test_recording_inventory_preserves_tentative_species_identity(
    activity_label: str,
    evidence: str,
    possible_heading: str,
) -> None:
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [
            {
                "observation_id": "obs-tentative-animal",
                "behavior": "walking",
                "activity_label": activity_label,
                "evidence": evidence,
                "start_seconds": 10.0,
                "end_seconds": 20.0,
            }
        ],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert possible_heading in reply.answer
    assert "identity is uncertain" in reply.answer
    assert reply.uncertainty == [
        "Some animal identities are tentative in the structured observations."
    ]


def test_recording_inventory_separates_confirmed_and_tentative_species() -> None:
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [
            {
                "observation_id": "obs-confirmed-cat-possible-bird",
                "behavior": "walking",
                "activity_label": "Cat with a possible bird",
                "evidence": "A cat is visible; the second animal may be a bird.",
                "start_seconds": 10.0,
                "end_seconds": 20.0,
            }
        ],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "- Cats: walking" in reply.answer
    assert "- Possible birds: identity is uncertain" in reply.answer
    assert reply.uncertainty


@pytest.mark.parametrize(
    ("evidence", "confirmed_heading", "possible_heading"),
    [
        (
            "A possible bird and a cat are visible.",
            "- Cats: walking",
            "- Possible birds: identity is uncertain",
        ),
        (
            "A possible cat and a confirmed bird are visible.",
            "- Birds: walking",
            "- Possible cats: identity is uncertain",
        ),
    ],
)
def test_recording_inventory_bounds_certainty_to_each_animal_mention(
    evidence: str,
    confirmed_heading: str,
    possible_heading: str,
) -> None:
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [
            {
                "observation_id": "obs-mixed-certainty-animals",
                "behavior": "walking",
                "activity_label": "Two animals visible",
                "evidence": evidence,
                "start_seconds": 10.0,
                "end_seconds": 20.0,
            }
        ],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert confirmed_heading in reply.answer
    assert possible_heading in reply.answer
    assert reply.uncertainty


def test_recording_inventory_keeps_positive_species_after_absence_clause() -> None:
    moment = {
        "observation_id": "obs-cat-after-empty-frame",
        "behavior": "walking",
        "activity_label": "Cat enters after an empty frame",
        "evidence": (
            "No animal is visible at 4 seconds; a black-and-white cat is visible "
            "near the doorway at 8 seconds."
        ),
        "start_seconds": 4.0,
        "end_seconds": 12.0,
    }
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [moment],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "Cats: walking" in reply.answer
    assert reply.cited_ids == ["obs-cat-after-empty-frame"]
    assert reply.uncertainty == []


def test_recording_inventory_tracks_each_species_polarity_per_clause() -> None:
    moment = {
        "observation_id": "obs-cat-present-bird-absent",
        "behavior": "walking",
        "activity_label": "Cat present; bird absent",
        "evidence": "A cat is present; the bird is absent.",
        "start_seconds": 4.0,
        "end_seconds": 12.0,
    }
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [moment],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "Cats: walking" in reply.answer
    assert "Birds:" not in reply.answer
    assert reply.uncertainty == []


@pytest.mark.parametrize(
    ("activity_label", "evidence"),
    [
        ("Cat walking continuously", "The cat walks without stopping."),
        (
            "Cat entering the frame",
            "A cat appears from behind the tree and crosses the frame.",
        ),
        ("Cat resting", "A cat is visible and may be resting."),
        ("Cat grooming", "A cat is visible and appears to be grooming."),
    ],
)
def test_recording_inventory_keeps_confirmed_species_when_behavior_is_uncertain(
    activity_label: str,
    evidence: str,
) -> None:
    moment = {
        "observation_id": "obs-cat-walking-continuously",
        "behavior": "walking",
        "activity_label": activity_label,
        "evidence": evidence,
        "start_seconds": 4.0,
        "end_seconds": 12.0,
    }
    context = {
        "animals": [{"name": "Trail camera wildlife", "event_count": 0}],
        "events": [],
        "moments": [moment],
        "data_gaps": [],
        "recording_summary": {"observation_count": 1, "event_count": 0},
        "retrieval": {"recording_inventory": True},
    }

    reply = summarize(context, "What animals are visible in this recording?")

    assert "Cats: walking" in reply.answer
    assert reply.uncertainty == []


def test_direct_bird_timing_keeps_all_documented_intervals_across_recording(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = retrieve_context(
        _backyard_bird_timing_context(),
        [
            ChatMessage(
                role="user",
                content="When do birds appear in this recording, and what are they doing?",
            )
        ],
    )

    assert [moment["observation_id"] for moment in context["moments"]] == [
        "obs-bird-41m49",
        "obs-bird-42m43",
        "obs-bird-46m23",
        "obs-bird-46m40",
        "obs-bird-1h05m52",
        "obs-bird-1h06m02",
        "obs-bird-1h08m21",
        "obs-bird-1h08m29",
        "obs-bird-1h10m32",
        "obs-bird-1h10m36",
        "obs-bird-1h10m47",
        "obs-bird-1h11m05",
        "obs-bird-1h11m16",
        "obs-bird-1h11m28",
        "obs-bird-1h11m40",
        "obs-bird-1h11m52",
    ]
    assert context["retrieval"]["animal_timing_terms"] == ["bird"]
    assert context["retrieval"]["animal_timing_match_count"] == 16
    assert context["retrieval"]["animal_timing_all_matches_included"] is True
    assert context["retrieval"]["no_match"] is False

    client = _StubClient(RuntimeError("animal timing must not call the model"))
    monkeypatch.setattr(
        chat_module,
        "build_context",
        lambda *_args, **_kwargs: _backyard_bird_timing_context(),
    )
    reply = GroundedChat(
        _seeded_store(tmp_path),
        client=client,
        model="gpt-test",
    ).reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="When do birds appear in this recording, and what are they doing?",
                )
            ],
            animal_id="animal-backyard",
            enclosure_id="ENC-BACKYARD",
            camera_id="CAM-BY2",
            source_path="uploads/backyard-squirrels-and-birds.mp4",
        )
    )

    assert reply.mode == "deterministic"
    assert client.responses.calls == []
    assert reply.uncertainty == []
    assert "All 16 matching structured observations are represented" in reply.answer
    assert "1:06:02" in reply.answer
    assert "1:10:47" in reply.answer
    assert len(reply.answer) < 1800
    assert not reply.answer.endswith("...")
    assert set(reply.cited_ids) == {
        "obs-bird-41m49",
        "obs-bird-42m43",
        "obs-bird-46m23",
        "obs-bird-46m40",
        "obs-bird-1h05m52",
        "obs-bird-1h06m02",
        "obs-bird-1h08m21",
        "obs-bird-1h08m29",
        "obs-bird-1h10m32",
        "obs-bird-1h10m36",
        "obs-bird-1h10m47",
        "obs-bird-1h11m05",
        "obs-bird-1h11m16",
        "obs-bird-1h11m28",
        "obs-bird-1h11m40",
        "obs-bird-1h11m52",
    }
    assert {moment.observation_id for moment in reply.moments} >= {
        "obs-bird-1h06m02",
        "obs-bird-1h10m47",
    }


def test_follow_up_timestamps_resolve_against_authoritative_bird_moments() -> None:
    messages = [
        ChatMessage(role="user", content="When do birds appear in this recording?"),
        ChatMessage(
            role="assistant",
            content="Birds appear around 42:44 and again around 1:10:47.",
        ),
        ChatMessage(
            role="user",
            content="What were they doing then, and was a squirrel with them?",
        ),
    ]
    context = retrieve_context(_backyard_bird_timing_context(), messages)

    assert context["retrieval"]["requested_media_offset_seconds"] is None
    assert context["retrieval"]["referenced_media_offsets_seconds"] == [2564.0, 4247.0]
    assert {moment["observation_id"] for moment in context["moments"]} == {
        "obs-bird-42m43",
        "obs-bird-1h10m36",
    }
    assert context["retrieval"]["no_match"] is False
    assert set(summarize(context, messages).moment_ids) == {
        "obs-bird-42m43",
        "obs-bird-1h10m36",
    }


def test_unknown_question_admits_no_matching_record_instead_of_dumping_events(
    tmp_path: Path,
) -> None:
    reply = GroundedChat(_seeded_store(tmp_path)).reply(
        ChatRequest(messages=[ChatMessage(role="user", content="What is tomorrow's weather?")])
    )

    assert "could not find recorded evidence" in reply.answer
    assert "R005_PACING_10M" not in reply.answer
    assert reply.cited_ids == []


def test_unknown_animal_does_not_turn_summary_language_into_a_record_dump(
    tmp_path: Path,
) -> None:
    reply = GroundedChat(_seeded_store(tmp_path)).reply(
        ChatRequest(messages=[ChatMessage(role="user", content="What happened to the giraffe?")])
    )

    assert "could not find recorded evidence" in reply.answer
    assert "Nox" not in reply.answer
    assert reply.cited_ids == []


def test_scoped_unknown_animal_reports_available_record_without_substitution(
    tmp_path: Path,
) -> None:
    store = _temporal_squirrel_store(tmp_path)
    reply = GroundedChat(store).reply(
        ChatRequest(
            messages=[
                ChatMessage(role="user", content="What does the giraffe do in this recording?")
            ],
            enclosure_id="ENC-BACKYARD",
            animal_id="animal-backyard",
            camera_id="CAM-BY1",
            source_path="uploads/backyard-squirrel-staircase.mp4",
        )
    )

    assert "2 structured observations" in reply.answer
    assert "none match" in reply.answer
    assert reply.cited_ids == []


def test_no_match_bypasses_model_instead_of_inviting_a_hallucination(tmp_path: Path) -> None:
    client = _StubClient(
        _Parsed(
            ChatAnswer(
                answer="A giraffe was visible.",
                cited_ids=[],
                uncertainty=[],
            )
        )
    )
    chat = GroundedChat(_seeded_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(
        ChatRequest(messages=[ChatMessage(role="user", content="What did the giraffe do?")])
    )

    assert reply.mode == "deterministic"
    assert "could not find recorded evidence" in reply.answer
    assert client.responses.calls == []


def test_follow_up_uses_the_previous_animal_subject(tmp_path: Path) -> None:
    context = retrieve_context(
        build_context(_seeded_store(tmp_path)),
        [
            ChatMessage(role="user", content="What happened to Nox?"),
            ChatMessage(
                role="assistant",
                content="Nox had a recorded pacing event.",
            ),
            ChatMessage(role="user", content="What rule supports that?"),
        ],
    )

    assert [event["event_id"] for event in context["events"]] == ["evt-1"]
    assert context["retrieval"]["matched_animal_ids"] == ["animal-nox"]


def test_selected_animal_resolves_this_animal_and_returns_human_labels(
    tmp_path: Path,
) -> None:
    reply = GroundedChat(_seeded_store(tmp_path)).reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="What is this animal usually doing?",
                )
            ],
            enclosure_id="ENC-07",
            animal_id="animal-nox",
        )
    )

    assert "Nox" in reply.answer
    assert "recorded" in reply.answer
    assert "usual behavior pattern" in reply.answer
    assert "R005_PACING_10M" not in reply.answer
    assert "obs-1" not in reply.answer
    assert reply.moments
    assert reply.citations
    assert all(citation.record_id not in citation.label for citation in reply.citations)
    assert any("Nox:" in citation.label for citation in reply.citations)


def test_unscoped_this_animal_does_not_guess_between_animals(tmp_path: Path) -> None:
    reply = GroundedChat(_seeded_store(tmp_path)).reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="What is this animal usually doing?",
                )
            ]
        )
    )

    assert "could not find recorded evidence" in reply.answer
    assert reply.cited_ids == []


def test_retrieval_keeps_synthetic_evidence_only_when_a_selected_event_cites_it(
    tmp_path: Path,
) -> None:
    full_context = build_context(_seeded_store(tmp_path))
    unrelated = dict(full_context["moments"][0])
    unrelated["observation_id"] = "obs-unrelated-demo"
    unrelated["animal_id"] = "animal-quiet"
    unrelated["animal_name"] = "Juniper"
    unrelated["enclosure_id"] = "ENC-03"
    unrelated["behavior"] = "resting"
    unrelated["activity_label"] = "Resting"
    full_context["moments"].append(unrelated)

    context = retrieve_context(
        full_context,
        [ChatMessage(role="user", content="What happened to Nox?")],
    )

    assert [moment["observation_id"] for moment in context["moments"]] == ["obs-1"]


def test_deterministic_answer_names_quiet_animals_and_gaps(tmp_path: Path) -> None:
    reply = GroundedChat(_seeded_store(tmp_path)).reply(
        ChatRequest(messages=[ChatMessage(role="user", content="Give me the shift summary.")])
    )

    assert "Juniper" in reply.answer
    assert "camera signal loss" in reply.answer
    assert reply.uncertainty, "recorded gaps must surface as stated uncertainty"


def test_deterministic_answer_on_an_empty_scope_admits_it(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "empty.db")
    store.initialize()

    reply = GroundedChat(store).reply(
        ChatRequest(messages=[ChatMessage(role="user", content="Anything to report?")])
    )

    assert "nothing to report" in reply.answer.lower()
    assert reply.cited_ids == []


class _StubResponses:
    def __init__(self, outcome: Any):
        self.outcome = outcome
        self.calls: list[dict] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _StubClient:
    def __init__(self, outcome: Any):
        self.responses = _StubResponses(outcome)


class _Parsed:
    def __init__(self, answer: ChatAnswer | None):
        self.output_parsed = answer


def test_model_answer_is_returned_when_citations_are_valid(tmp_path: Path) -> None:
    client = _StubClient(
        _Parsed(
            ChatAnswer(
                answer="Nox paced for 12 minutes; rule R005_PACING_10M recorded MODERATE.",
                cited_ids=["evt-1", "obs-1"],
                uncertainty=[],
                moment_ids=["obs-1"],
            )
        )
    )
    chat = GroundedChat(_seeded_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(ChatRequest(messages=[ChatMessage(role="user", content="What happened?")]))

    assert reply.mode == "openai"
    assert reply.model == "gpt-test"
    assert reply.cited_ids == ["evt-1", "obs-1"]
    assert [citation.label for citation in reply.citations] == [
        "Nox: pacing event at 02:00",
        "Nox: Pacing at 0:00",
    ]
    assert reply.moments[0].observation_id == "obs-1"
    assert reply.moments[0].source_path == "fixtures/badger.mp4"
    assert reply.moments[0].start_seconds == 0
    # The record must never be retained by the provider.
    assert client.responses.calls[0]["store"] is False
    assert client.responses.calls[0]["reasoning"] == {"effort": "medium"}


def test_chat_answer_bounds_verbose_model_output_before_validation() -> None:
    answer = ChatAnswer.model_validate(
        {
            "answer": "recorded evidence " * 200,
            "cited_ids": [],
            "uncertainty": [],
            "moment_ids": [f"obs-{index}" for index in range(8)],
        }
    )

    assert len(answer.answer) <= 1800
    assert answer.answer.endswith("...")
    assert answer.moment_ids == [f"obs-{index}" for index in range(5)]


def test_safety_refusal_does_not_attach_an_unrelated_moment(tmp_path: Path) -> None:
    client = _StubClient(
        _Parsed(
            ChatAnswer(
                answer="I cannot diagnose Nox or recommend medication.",
                cited_ids=["animal-nox"],
                uncertainty=[],
                moment_ids=["obs-1"],
            )
        )
    )
    chat = GroundedChat(_seeded_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(
        ChatRequest(messages=[ChatMessage(role="user", content="What medicine should I give Nox?")])
    )

    assert reply.mode == "deterministic"
    assert "cannot diagnose" in reply.answer
    assert "operate an enclosure" in reply.answer
    assert reply.moments == []
    assert client.responses.calls == []


def test_recording_count_question_uses_authoritative_summary_without_model(
    tmp_path: Path,
) -> None:
    client = _StubClient(RuntimeError("the model should not be called"))
    chat = GroundedChat(_temporal_squirrel_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="How many structured observations are in this recording?",
                )
            ],
            source_path="uploads/backyard-squirrel-staircase.mp4",
            camera_id="CAM-BY1",
        )
    )

    assert reply.mode == "deterministic"
    assert "2 structured observations" in reply.answer
    assert "0 deterministic rule events" in reply.answer
    assert client.responses.calls == []


def test_generic_wildlife_profile_does_not_prove_an_animal_appears(
    tmp_path: Path,
) -> None:
    full_context = build_context(
        _temporal_squirrel_store(tmp_path),
        source_path="uploads/backyard-squirrel-staircase.mp4",
        camera_id="CAM-BY1",
    )
    full_context["animals"][0]["species"] = "Unassigned wildlife"
    for moment in full_context["moments"]:
        moment["activity_label"] = "One squirrel foraging"
        moment["evidence"] = "One squirrel is visible foraging for seeds."

    context = retrieve_context(
        full_context,
        [ChatMessage(role="user", content="When do birds appear in this recording?")],
    )

    assert context["retrieval"]["undocumented_profile_terms"] == ["bird"]
    assert context["retrieval"]["no_match"] is True
    assert context["moments"] == []


def test_documented_sparrows_satisfy_a_bird_query(tmp_path: Path) -> None:
    context = retrieve_context(
        build_context(
            _temporal_squirrel_store(tmp_path),
            source_path="uploads/backyard-squirrel-staircase.mp4",
            camera_id="CAM-BY1",
        ),
        [ChatMessage(role="user", content="When do birds appear in this recording?")],
    )

    assert context["retrieval"]["undocumented_profile_terms"] == []
    assert context["retrieval"]["no_match"] is False
    assert {moment["observation_id"] for moment in context["moments"]} == {
        "obs-near-33m",
        "obs-after-33m",
    }


def test_chat_reply_humanizes_raw_video_second_references() -> None:
    reply = ChatReply(
        answer=(
            "Seen at 0.0s, from 125.1s-2160.6s, from 0.0 to 3.0 seconds, "
            "at 1443.2 seconds, and again at 3661.2 s."
        ),
        cited_ids=[],
        uncertainty=[],
        mode="openai",
        context_record_count=0,
    )

    assert reply.answer == (
        "Seen at 0:00, from 2:05-36:01, from 0:00 to 0:03, at 24:03, and again at 1:01:01."
    )


def test_chat_reply_leaves_non_video_numbers_unchanged() -> None:
    answer = (
        "Confidence 0.83, coverage 50%, latency 125ms, record obs_125.1s, "
        "date 2026-07-31, a three-second pause for 3 seconds, and existing time 36:01."
    )

    reply = ChatReply(
        answer=answer,
        cited_ids=[],
        uncertainty=[],
        mode="openai",
        context_record_count=0,
    )

    assert reply.answer == answer


def test_model_answer_citing_an_unknown_record_falls_back_to_the_record(tmp_path: Path) -> None:
    client = _StubClient(
        _Parsed(
            ChatAnswer(
                answer="An event that does not exist occurred.",
                cited_ids=["evt-does-not-exist"],
                uncertainty=[],
            )
        )
    )
    chat = GroundedChat(_seeded_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(ChatRequest(messages=[ChatMessage(role="user", content="What happened?")]))

    assert reply.mode == "deterministic_fallback"
    assert "does not exist" not in reply.answer
    assert "evt-1" in reply.cited_ids


def test_model_answer_exposing_a_raw_record_id_is_humanized(
    tmp_path: Path,
) -> None:
    client = _StubClient(
        _Parsed(
            ChatAnswer(
                answer="Nox is shown in obs-1.",
                cited_ids=["obs-1"],
                uncertainty=[],
                moment_ids=["obs-1"],
            )
        )
    )
    chat = GroundedChat(_seeded_store(tmp_path), client=client, model="gpt-test")

    reply = chat.reply(
        ChatRequest(
            messages=[ChatMessage(role="user", content="What is this animal doing?")],
            enclosure_id="ENC-07",
            animal_id="animal-nox",
        )
    )

    assert reply.mode == "openai"
    assert "obs-1" not in reply.answer
    assert "Nox: Pacing at 0:00" in reply.answer
    assert reply.citations
    assert all(citation.record_id not in citation.label for citation in reply.citations)


def test_model_failure_still_answers_from_the_record(tmp_path: Path) -> None:
    chat = GroundedChat(
        _seeded_store(tmp_path),
        client=_StubClient(RuntimeError("provider offline")),
        model="gpt-test",
    )

    reply = chat.reply(ChatRequest(messages=[ChatMessage(role="user", content="What happened?")]))

    assert reply.mode == "deterministic_fallback"
    assert "R005_PACING_10M" in reply.answer
    assert any("verified shift record" in item for item in reply.uncertainty)
    assert all("RuntimeError" not in item for item in reply.uncertainty)


def test_strict_chat_does_not_fall_back_locally(tmp_path: Path) -> None:
    chat = GroundedChat(
        _seeded_store(tmp_path),
        client=_StubClient(RuntimeError("provider offline")),
        model="gpt-test",
        allow_fallback=False,
    )

    with pytest.raises(RuntimeError, match="live OpenAI chat is unavailable"):
        chat.reply(ChatRequest(messages=[ChatMessage(role="user", content="What happened?")]))


def test_model_failure_fallback_keeps_exact_video_scope(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    store.upsert_animal(
        animal_id="animal-nox",
        name="Backyard squirrels",
        species="Eastern gray squirrel",
        enclosure_id="ENC-07",
        baseline_state="shadow",
    )
    store.upsert_video_chunk(
        chunk_id="chunk-2",
        enclosure_id="ENC-07",
        camera_id="CAM-07B",
        start_ts=START.isoformat(),
        end_ts=(START + timedelta(minutes=15)).isoformat(),
        source_path="fixtures/badger-secondary.mp4",
        source_offset_seconds=0,
        content_sha256="sha-secondary",
        status="ready",
    )
    store.save_observation(
        Observation(
            observation_id="obs-2",
            animal_id="animal-nox",
            enclosure_id="ENC-07",
            chunk_id="chunk-2",
            behavior=Behavior.WALKING,
            start_ts=START + timedelta(minutes=2),
            end_ts=START + timedelta(minutes=3),
            confidence=0.88,
            evidence="The squirrels walked beside the secondary camera.",
            provider="twelvelabs",
            provider_model="test",
            evidence_kind=EvidenceKind.PROVIDER_STRUCTURED,
            activity_label="Walking beside the fence",
        )
    )
    chat = GroundedChat(
        store,
        client=_StubClient(RuntimeError("provider offline")),
        model="gpt-test",
    )

    reply = chat.reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="What did the squirrels do during the first ten minutes?",
                )
            ],
            enclosure_id="ENC-07",
            animal_id="animal-nox",
            camera_id="CAM-07B",
            source_path="fixtures/badger-secondary.mp4",
        )
    )

    assert reply.mode == "deterministic_fallback"
    assert reply.cited_ids == ["obs-2"]
    assert [citation.label for citation in reply.citations] == [
        "Backyard squirrels: Walking beside the fence at 2:00"
    ]
    assert [moment.source_path for moment in reply.moments] == ["fixtures/badger-secondary.mp4"]
    assert "obs-2" not in reply.answer
    assert "CAM-07A" not in reply.answer
    assert any("verified shift record" in item for item in reply.uncertainty)
    assert all("RuntimeError" not in item for item in reply.uncertainty)


def test_time_query_prioritizes_structured_moment_over_embedding_gap(
    tmp_path: Path,
) -> None:
    full_context = build_context(
        _temporal_squirrel_store(tmp_path),
        enclosure_id="ENC-BACKYARD",
        animal_id="animal-backyard",
        camera_id="CAM-BY1",
        source_path="uploads/backyard-squirrel-staircase.mp4",
    )
    context = retrieve_context(
        full_context,
        [
            ChatMessage(
                role="user",
                content="What is the squirrel doing around 33 minutes?",
            )
        ],
    )

    assert context["retrieval"]["requested_media_offset_seconds"] == 33 * 60
    assert [moment["observation_id"] for moment in context["moments"]] == ["obs-near-33m"]
    assert context["data_gaps"] == []
    assert all(
        moment["source_path"] == "uploads/backyard-squirrel-staircase.mp4"
        for moment in context["moments"]
    )


def test_time_query_model_failure_answers_from_observation_not_embedding_gap(
    tmp_path: Path,
) -> None:
    chat = GroundedChat(
        _temporal_squirrel_store(tmp_path),
        client=_StubClient(RuntimeError("provider offline")),
        model="gpt-test",
    )

    reply = chat.reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="What is the squirrel doing around 33 minutes?",
                )
            ],
            enclosure_id="ENC-BACKYARD",
            animal_id="animal-backyard",
            camera_id="CAM-BY1",
            source_path="uploads/backyard-squirrel-staircase.mp4",
        )
    )

    assert reply.mode == "deterministic_fallback"
    assert "33:00" in reply.answer
    assert "sparrow" in reply.answer.lower()
    assert "eating seeds" in reply.answer.lower()
    assert "embedding" not in reply.answer.lower()
    assert "could not find" not in reply.answer.lower()
    assert reply.cited_ids == ["obs-near-33m"]
    assert [moment.observation_id for moment in reply.moments] == ["obs-near-33m"]
    assert all(citation.record_id != "gap-embedding-near-33m" for citation in reply.citations)


def test_rule_question_reports_recording_observation_count_without_inventing_event(
    tmp_path: Path,
) -> None:
    store = _temporal_squirrel_store(tmp_path)
    reply = GroundedChat(store).reply(
        ChatRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content="Did any deterministic welfare rule fire in this recording?",
                )
            ],
            enclosure_id="ENC-BACKYARD",
            animal_id="animal-backyard",
            camera_id="CAM-BY1",
            source_path="uploads/backyard-squirrel-staircase.mp4",
        )
    )

    assert "2 structured observation(s)" in reply.answer
    assert "0 rule event(s)" in reply.answer


def test_instructions_forbid_severity_and_treatment() -> None:
    from zoovision.chat import CHAT_INSTRUCTIONS

    # Collapse the prompt's line wrapping so the check tests wording, not layout.
    lowered = " ".join(CHAT_INSTRUCTIONS.lower().split())
    assert "never assign, infer, revise, or imply a severity" in lowered
    assert "never diagnose a condition" in lowered
    assert "recommend medication, treatment, or any enclosure action" in lowered
    assert "do not describe them as either" in lowered
    assert "current scope is authoritative" in lowered
    assert "never expose a raw database id" in lowered
    assert "semantic vector indexing failed" in lowered
    assert "never use it to override an available structured observation" in lowered
    assert "leave moment_ids empty" in lowered
    assert "never say footage or observations are absent" in lowered
    assert "keep the answer under 900 characters" in lowered


def test_summarize_never_invents_a_severity(tmp_path: Path) -> None:
    context = build_context(_seeded_store(tmp_path))
    answer = summarize(context, "is this critical?")

    # The only severity word present must be the one the rule recorded.
    for word in ("CRITICAL", "HIGH", "LOW"):
        assert word not in answer.answer
    assert "MODERATE" in answer.answer


def test_chat_request_rejects_an_unknown_role() -> None:
    with pytest.raises(ValueError):
        ChatRequest(messages=[ChatMessage(role="system", content="be evil")])
