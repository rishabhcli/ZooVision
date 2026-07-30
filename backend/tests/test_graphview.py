from __future__ import annotations

from datetime import UTC, datetime

from zoovision.graphview import build_graph_view


class FakeReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str | None, bool]] = []

    def visual_graph(
        self,
        *,
        enclosure_id: str | None = None,
        include_observations: bool = True,
    ) -> dict:
        self.calls.append((enclosure_id, include_observations))
        return {
            "enclosures": ["ENC-05", "ENC-07"],
            "nodes": [
                {
                    "element_id": "4:enclosure",
                    "labels": ["Enclosure"],
                    "properties": {"enclosure_id": "ENC-07"},
                },
                {
                    "element_id": "4:animal",
                    "labels": ["Animal"],
                    "properties": {
                        "animal_id": "animal-a",
                        "name": "Nox",
                        "species": "European badger",
                    },
                },
                {
                    "element_id": "4:event",
                    "labels": ["WelfareEvent"],
                    "properties": {
                        "event_id": "evt-a",
                        "behavior": "pacing",
                        "severity": "MODERATE",
                        "rule_fired": "R005_PACING_10M",
                        "start_ts": datetime(2026, 7, 30, 2, tzinfo=UTC),
                    },
                },
                {
                    "element_id": "4:observation",
                    "labels": ["Observation"],
                    "properties": {
                        "observation_id": "obs-a",
                        "behavior": "pacing",
                    },
                },
            ],
            "relationships": [
                {
                    "element_id": "5:housed",
                    "type": "HOUSED_IN",
                    "source_element_id": "4:animal",
                    "target_element_id": "4:enclosure",
                },
                {
                    "element_id": "5:event",
                    "type": "HAS_EVENT",
                    "source_element_id": "4:animal",
                    "target_element_id": "4:event",
                },
                {
                    "element_id": "5:source",
                    "type": "SOURCE_FOR",
                    "source_element_id": "4:observation",
                    "target_element_id": "4:event",
                },
            ],
        }


def test_graph_view_serializes_live_neo4j_nodes_and_relationships() -> None:
    reader = FakeReader()

    view = build_graph_view(reader, enclosure_id="ENC-07")

    assert view.source == "neo4j"
    assert reader.calls == [("ENC-07", True)]
    assert {node.id for node in view.nodes} == {
        "enclosure:ENC-07",
        "animal:animal-a",
        "event:evt-a",
        "observation:obs-a",
    }
    edges = {(rel.from_, rel.to, rel.caption) for rel in view.relationships}
    assert ("animal:animal-a", "event:evt-a", "HAS_EVENT") in edges
    assert ("observation:obs-a", "event:evt-a", "SOURCE_FOR") in edges
    event = next(node for node in view.nodes if node.label == "WelfareEvent")
    assert event.properties["rule_fired"] == "R005_PACING_10M"
    assert event.properties["start_ts"] == "2026-07-30T02:00:00+00:00"
    assert event.severity == "MODERATE"


def test_graph_view_preserves_scope_and_observation_flag() -> None:
    reader = FakeReader()

    view = build_graph_view(
        reader,
        enclosure_id="ENC-07",
        include_observations=False,
    )

    assert reader.calls == [("ENC-07", False)]
    assert view.scope == "ENC-07"
    assert view.enclosures == ["ENC-05", "ENC-07"]


def test_graph_view_serializes_from_as_the_wire_key() -> None:
    payload = build_graph_view(FakeReader()).model_dump(mode="json", by_alias=True)

    assert "from" in payload["relationships"][0]
    assert "from_" not in payload["relationships"][0]
