from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from zoovision.domain import (
    Behavior,
    EventRecord,
    EvidenceKind,
    Observation,
    Severity,
    ShiftMode,
)
from zoovision.graphview import build_graph_view
from zoovision.store import SQLiteStore

START = datetime(2026, 7, 30, 2, 0, tzinfo=UTC)


def _seeded_store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path / "graph.db")
    store.initialize()
    for animal_id, name, enclosure in (
        ("animal-a", "Nox", "ENC-07"),
        ("animal-b", "Mara", "ENC-05"),
    ):
        store.upsert_animal(
            animal_id=animal_id,
            name=name,
            species="Test species",
            enclosure_id=enclosure,
            baseline_state="shadow",
        )
        store.upsert_video_chunk(
            chunk_id=f"chunk-{animal_id}",
            enclosure_id=enclosure,
            camera_id=f"CAM-{enclosure}",
            start_ts=START.isoformat(),
            end_ts=(START + timedelta(minutes=15)).isoformat(),
            source_path=f"fixtures/{animal_id}.mp4",
            source_offset_seconds=0,
            content_sha256="sha",
            status="ready",
        )
        store.save_observation(
            Observation(
                observation_id=f"obs-{animal_id}",
                animal_id=animal_id,
                enclosure_id=enclosure,
                chunk_id=f"chunk-{animal_id}",
                behavior=Behavior.PACING,
                start_ts=START,
                end_ts=START + timedelta(minutes=12),
                confidence=0.9,
                evidence="Synthetic scenario evidence.",
                provider="fixture",
                provider_model="scenario-v1",
                evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
            )
        )
        store.save_event(
            EventRecord(
                event_id=f"evt-{animal_id}",
                animal_id=animal_id,
                enclosure_id=enclosure,
                behavior=Behavior.PACING,
                start_ts=START,
                end_ts=START + timedelta(minutes=12),
                severity=Severity.MODERATE,
                rule_fired="R005_PACING_10M",
                action=None,
                confidence=0.9,
                source_observation_ids=[f"obs-{animal_id}"],
                explanation_facts=["Continuous pacing lasted 12.0 minutes."],
                rule_version="test.v1",
                shift_mode=ShiftMode.NIGHT,
                created_at=START,
            )
        )
    return store


def test_graph_view_links_animal_to_event_to_observation(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path))

    node_ids = {node.id for node in view.nodes}
    assert "animal:animal-a" in node_ids
    assert "event:evt-animal-a" in node_ids
    assert "observation:obs-animal-a" in node_ids

    edges = {(rel.from_, rel.to, rel.caption) for rel in view.relationships}
    assert ("animal:animal-a", "event:evt-animal-a", "HAS_EVENT") in edges
    assert ("observation:obs-animal-a", "event:evt-animal-a", "SOURCE_FOR") in edges
    assert ("animal:animal-a", "enclosure:ENC-07", "HOUSED_IN") in edges


def test_graph_view_scopes_to_one_enclosure(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path), enclosure_id="ENC-07")

    node_ids = {node.id for node in view.nodes}
    assert "animal:animal-a" in node_ids
    assert "animal:animal-b" not in node_ids
    assert view.scope == "ENC-07"
    # Every enclosure is still advertised so the console can offer the switch.
    assert view.enclosures == ["ENC-05", "ENC-07"]


def test_graph_relationships_only_reference_present_nodes(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path), enclosure_id="ENC-07")

    node_ids = {node.id for node in view.nodes}
    for relationship in view.relationships:
        assert relationship.from_ in node_ids
        assert relationship.to in node_ids


def test_graph_view_can_omit_observations(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path), include_observations=False)

    assert not [node for node in view.nodes if node.label == "Observation"]
    assert [node for node in view.nodes if node.label == "WelfareEvent"]


def test_event_nodes_carry_the_rule_that_fired(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path))

    event = next(node for node in view.nodes if node.label == "WelfareEvent")
    assert event.properties["rule_fired"] == "R005_PACING_10M"
    assert event.severity == "MODERATE"


def test_graph_view_serializes_from_as_the_nvl_key(tmp_path: Path) -> None:
    view = build_graph_view(_seeded_store(tmp_path))

    payload = view.model_dump(mode="json", by_alias=True)
    assert "from" in payload["relationships"][0]
    assert "from_" not in payload["relationships"][0]


def test_graph_view_of_an_empty_store_is_empty(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "empty.db")
    store.initialize()

    view = build_graph_view(store)

    assert view.nodes == []
    assert view.relationships == []
    assert view.enclosures == []
