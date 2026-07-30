"""Read model that shapes stored welfare evidence as a visual graph.

The console renders this with the Neo4j Visualization Library, so nodes and
relationships are emitted in NVL's shape: flat records with stable ids, a
caption, and a Neo4j-style label used for colour and legend grouping.

The graph is built from SQLite rather than Neo4j so it renders whether or not an
Aura instance is reachable. Neo4j remains the system of record for the
application-owned graph writes; this is a projection of the same facts, and both
are keyed by the same stable identifiers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .store import SQLiteStore

#: Node labels the console knows how to colour and filter.
NODE_LABELS = (
    "Enclosure",
    "Animal",
    "WelfareEvent",
    "Observation",
    "Camera",
    "DataGap",
)

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1, "NONE": 0}


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    caption: str
    #: Free-form detail rendered in the inspector when a node is selected.
    properties: dict[str, Any] = Field(default_factory=dict)
    severity: str | None = None
    size: float = 24.0


class GraphRelationship(BaseModel):
    # ``from`` is a Python keyword, so the field is aliased for the wire format
    # NVL expects while staying constructible by name in Python.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    caption: str


class GraphView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
    enclosures: list[str]
    scope: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


def build_graph_view(
    store: SQLiteStore,
    *,
    enclosure_id: str | None = None,
    include_observations: bool = True,
) -> GraphView:
    """Project the store into an NVL-ready graph, optionally scoped to one enclosure."""
    animals = store.dump_table("animals")
    events = store.dump_table("events")
    observations = store.dump_table("observations")
    chunks = store.dump_table("video_chunks")
    gaps = store.dump_table("data_gaps")
    event_sources = store.dump_table("event_sources")

    enclosures = sorted({animal["enclosure_id"] for animal in animals})
    if enclosure_id is not None:
        animals = [a for a in animals if a["enclosure_id"] == enclosure_id]
        events = [e for e in events if e["enclosure_id"] == enclosure_id]
        gaps = [g for g in gaps if g["enclosure_id"] == enclosure_id]
        chunks = [c for c in chunks if c["enclosure_id"] == enclosure_id]

    event_ids = {event["event_id"] for event in events}
    chunk_ids = {chunk["chunk_id"] for chunk in chunks}
    sourced_observation_ids = {
        link["observation_id"] for link in event_sources if link["event_id"] in event_ids
    }
    observations = [
        observation
        for observation in observations
        if observation["observation_id"] in sourced_observation_ids
        or observation["chunk_id"] in chunk_ids
    ]

    nodes: list[GraphNode] = []
    relationships: list[GraphRelationship] = []
    seen_nodes: set[str] = set()

    def add_node(node: GraphNode) -> None:
        if node.id not in seen_nodes:
            seen_nodes.add(node.id)
            nodes.append(node)

    def add_relationship(source: str, target: str, caption: str) -> None:
        if source in seen_nodes and target in seen_nodes:
            relationships.append(
                GraphRelationship(
                    id=f"{caption}:{source}->{target}",
                    from_=source,
                    to=target,
                    caption=caption,
                )
            )

    for enclosure in sorted({animal["enclosure_id"] for animal in animals}):
        add_node(
            GraphNode(
                id=f"enclosure:{enclosure}",
                label="Enclosure",
                caption=enclosure,
                size=38.0,
                properties={"enclosure_id": enclosure},
            )
        )

    for animal in animals:
        node_id = f"animal:{animal['animal_id']}"
        add_node(
            GraphNode(
                id=node_id,
                label="Animal",
                caption=animal["name"],
                size=34.0,
                properties={
                    "animal_id": animal["animal_id"],
                    "species": animal["species"],
                    "baseline_state": animal["baseline_state"],
                    "enclosure_id": animal["enclosure_id"],
                },
            )
        )
        add_relationship(node_id, f"enclosure:{animal['enclosure_id']}", "HOUSED_IN")

    for chunk in chunks:
        camera_id = f"camera:{chunk['camera_id']}"
        add_node(
            GraphNode(
                id=camera_id,
                label="Camera",
                caption=chunk["camera_id"],
                size=26.0,
                properties={
                    "camera_id": chunk["camera_id"],
                    "enclosure_id": chunk["enclosure_id"],
                },
            )
        )
        add_relationship(camera_id, f"enclosure:{chunk['enclosure_id']}", "MONITORS")

    for event in events:
        node_id = f"event:{event['event_id']}"
        add_node(
            GraphNode(
                id=node_id,
                label="WelfareEvent",
                caption=_titlecase(event["behavior"]),
                severity=event["severity"],
                size=22.0 + 4.0 * SEVERITY_RANK.get(event["severity"], 0),
                properties={
                    "event_id": event["event_id"],
                    "behavior": event["behavior"],
                    "severity": event["severity"],
                    "rule_fired": event["rule_fired"],
                    "rule_version": event["rule_version"],
                    "action": event["action"],
                    "shift_mode": event["shift_mode"],
                    "review_state": event["review_state"],
                    "start_ts": event["start_ts"],
                    "end_ts": event["end_ts"],
                    "confidence": event["confidence"],
                },
            )
        )
        add_relationship(f"animal:{event['animal_id']}", node_id, "HAS_EVENT")

    if include_observations:
        chunk_by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
        for observation in observations:
            node_id = f"observation:{observation['observation_id']}"
            add_node(
                GraphNode(
                    id=node_id,
                    label="Observation",
                    caption=_titlecase(observation["behavior"]),
                    size=16.0,
                    properties={
                        "observation_id": observation["observation_id"],
                        "behavior": observation["behavior"],
                        "evidence": observation["evidence"],
                        "evidence_kind": observation["evidence_kind"],
                        "provider": observation["provider"],
                        "provider_model": observation["provider_model"],
                        "confidence": observation["confidence"],
                        "start_ts": observation["start_ts"],
                        "end_ts": observation["end_ts"],
                        "chunk_id": observation["chunk_id"],
                    },
                )
            )
            chunk = chunk_by_id.get(observation["chunk_id"])
            if chunk is not None:
                add_relationship(f"camera:{chunk['camera_id']}", node_id, "CAPTURED")
        for link in event_sources:
            if link["event_id"] in event_ids:
                add_relationship(
                    f"observation:{link['observation_id']}",
                    f"event:{link['event_id']}",
                    "SOURCE_FOR",
                )

    for gap in gaps:
        node_id = f"gap:{gap['gap_id']}"
        add_node(
            GraphNode(
                id=node_id,
                label="DataGap",
                caption=_titlecase(gap["reason"]),
                size=20.0,
                properties={
                    "gap_id": gap["gap_id"],
                    "reason": gap["reason"],
                    "detail": gap["detail"],
                    "start_ts": gap["start_ts"],
                    "end_ts": gap["end_ts"],
                    "enclosure_id": gap["enclosure_id"],
                },
            )
        )
        add_relationship(node_id, f"enclosure:{gap['enclosure_id']}", "COVERAGE_GAP")

    counts: dict[str, int] = {label: 0 for label in NODE_LABELS}
    for node in nodes:
        counts[node.label] = counts.get(node.label, 0) + 1

    return GraphView(
        nodes=nodes,
        relationships=relationships,
        enclosures=enclosures,
        scope=enclosure_id,
        counts=counts,
    )


def _titlecase(value: str | None) -> str:
    if not value:
        return "Unknown"
    return value.replace("_", " ").title()
