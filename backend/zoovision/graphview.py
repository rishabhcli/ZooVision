"""Shape the live Neo4j welfare graph for the operator console."""

from __future__ import annotations

from pathlib import PurePath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .graph import Neo4jGraphReader

NODE_LABELS = (
    "Enclosure",
    "Animal",
    "WelfareEvent",
    "Observation",
    "Camera",
    "Clip",
    "DataGap",
)

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1, "NONE": 0}
NODE_SIZE = {
    "Enclosure": 38.0,
    "Animal": 34.0,
    "Camera": 26.0,
    "Clip": 22.0,
    "DataGap": 20.0,
    "Observation": 16.0,
}
STABLE_KEYS = {
    "Enclosure": ("enclosure_id", "enclosure"),
    "Animal": ("animal_id", "animal"),
    "WelfareEvent": ("event_id", "event"),
    "Observation": ("observation_id", "observation"),
    "Camera": ("camera_id", "camera"),
    "Clip": ("clip_id", "clip"),
    "DataGap": ("gap_id", "gap"),
}


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    caption: str
    properties: dict[str, Any] = Field(default_factory=dict)
    severity: str | None = None
    size: float = 24.0


class GraphRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    caption: str


class GraphView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["neo4j"] = "neo4j"
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
    enclosures: list[str]
    scope: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


def build_graph_view(
    reader: Neo4jGraphReader,
    *,
    enclosure_id: str | None = None,
    include_observations: bool = True,
) -> GraphView:
    """Read and serialize the configured Neo4j context graph without a local fallback."""
    raw = reader.visual_graph(
        enclosure_id=enclosure_id,
        include_observations=include_observations,
    )
    nodes: list[GraphNode] = []
    element_to_stable: dict[str, str] = {}

    for item in raw["nodes"]:
        labels = [str(value) for value in item.get("labels", [])]
        label = next(
            (value for value in NODE_LABELS if value in labels),
            labels[0] if labels else "Node",
        )
        properties = _json_properties(dict(item.get("properties", {})))
        node_id = _stable_node_id(label, properties, str(item["element_id"]))
        element_to_stable[str(item["element_id"])] = node_id
        severity = _string_or_none(properties.get("severity"))
        size = NODE_SIZE.get(label, 24.0)
        if label == "WelfareEvent":
            size = 22.0 + 4.0 * SEVERITY_RANK.get(severity or "NONE", 0)
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                caption=_caption(label, properties),
                properties=properties,
                severity=severity,
                size=size,
            )
        )

    relationships: list[GraphRelationship] = []
    for item in raw["relationships"]:
        source = element_to_stable.get(str(item["source_element_id"]))
        target = element_to_stable.get(str(item["target_element_id"]))
        if source is None or target is None:
            continue
        relationship_type = str(item["type"])
        relationships.append(
            GraphRelationship(
                id=f"{relationship_type}:{source}->{target}",
                from_=source,
                to=target,
                caption=relationship_type,
            )
        )

    counts = {label: 0 for label in NODE_LABELS}
    for node in nodes:
        counts[node.label] = counts.get(node.label, 0) + 1

    return GraphView(
        nodes=nodes,
        relationships=relationships,
        enclosures=sorted(str(value) for value in raw["enclosures"]),
        scope=enclosure_id,
        counts=counts,
    )


def _stable_node_id(label: str, properties: dict[str, Any], element_id: str) -> str:
    stable = STABLE_KEYS.get(label)
    if stable is not None and properties.get(stable[0]) is not None:
        return f"{stable[1]}:{properties[stable[0]]}"
    return f"neo4j:{element_id}"


def _caption(label: str, properties: dict[str, Any]) -> str:
    if label == "Animal":
        return str(properties.get("name") or properties.get("animal_id") or "Animal")
    if label == "Enclosure":
        return str(properties.get("enclosure_id") or "Enclosure")
    if label in {"WelfareEvent", "Observation"}:
        return _titlecase(_string_or_none(properties.get("behavior")))
    if label == "Camera":
        return str(properties.get("camera_id") or "Camera")
    if label == "Clip":
        source_path = _string_or_none(properties.get("source_path"))
        if source_path:
            return PurePath(source_path).name
        return str(properties.get("clip_id") or "Clip")
    if label == "DataGap":
        return _titlecase(_string_or_none(properties.get("reason")))
    return label


def _json_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in properties.items()}


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return str(value)


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _titlecase(value: str | None) -> str:
    if not value:
        return "Unknown"
    return value.replace("_", " ").title()
