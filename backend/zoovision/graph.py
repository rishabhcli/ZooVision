from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from pydantic import BaseModel, ConfigDict, model_validator

from .domain import EventRecord, Observation

SCHEMA_QUERIES = (
    "CREATE CONSTRAINT animal_id_unique IF NOT EXISTS "
    "FOR (animal:Animal) REQUIRE animal.animal_id IS UNIQUE",
    "CREATE CONSTRAINT enclosure_id_unique IF NOT EXISTS "
    "FOR (enclosure:Enclosure) REQUIRE enclosure.enclosure_id IS UNIQUE",
    "CREATE CONSTRAINT welfare_event_id_unique IF NOT EXISTS "
    "FOR (event:WelfareEvent) REQUIRE event.event_id IS UNIQUE",
    "CREATE CONSTRAINT observation_id_unique IF NOT EXISTS "
    "FOR (observation:Observation) REQUIRE observation.observation_id IS UNIQUE",
    "CREATE CONSTRAINT camera_id_unique IF NOT EXISTS "
    "FOR (camera:Camera) REQUIRE camera.camera_id IS UNIQUE",
    "CREATE CONSTRAINT clip_id_unique IF NOT EXISTS FOR (clip:Clip) REQUIRE clip.clip_id IS UNIQUE",
)

WRITE_EVENT_CYPHER = """
MERGE (enclosure:Enclosure {enclosure_id: $enclosure_id})
MERGE (animal:Animal {animal_id: $animal_id})
SET animal.name = $animal_name,
    animal.species = $species
MERGE (animal)-[:HOUSED_IN]->(enclosure)
MERGE (camera:Camera {camera_id: $camera_id})
MERGE (camera)-[:MONITORS]->(enclosure)
MERGE (event:WelfareEvent {event_id: $event_id})
SET event.behavior = $behavior,
    event.severity = $severity,
    event.rule_fired = $rule_fired,
    event.rule_version = $rule_version,
    event.action = $action,
    event.start_ts = datetime($start_ts),
    event.end_ts = datetime($end_ts),
    event.confidence = $confidence,
    event.shift_mode = $shift_mode,
    event.review_state = $review_state
MERGE (animal)-[:HAS_EVENT]->(event)
WITH animal, enclosure, event
UNWIND $sources AS source
MERGE (observation:Observation {observation_id: source.observation_id})
SET observation.chunk_id = source.chunk_id,
    observation.behavior = source.behavior,
    observation.start_ts = datetime(source.start_ts),
    observation.end_ts = datetime(source.end_ts),
    observation.confidence = source.confidence,
    observation.evidence = source.evidence,
    observation.evidence_kind = source.evidence_kind,
    observation.provider = source.provider,
    observation.provider_model = source.provider_model
MERGE (clip:Clip {clip_id: source.chunk_id})
SET clip.source_path = $source_path,
    clip.start_ts = datetime(source.start_ts),
    clip.end_ts = datetime(source.end_ts)
MERGE (camera)-[:CAPTURED]->(clip)
MERGE (clip)-[:RECORDED_IN]->(enclosure)
MERGE (observation)-[:EVIDENCE_FROM]->(clip)
MERGE (observation)-[:SOURCE_FOR]->(event)
MERGE (observation)-[:OBSERVED_IN]->(enclosure)
"""

WRITE_OBSERVATIONS_CYPHER = """
MERGE (enclosure:Enclosure {enclosure_id: $enclosure_id})
MERGE (animal:Animal {animal_id: $animal_id})
SET animal.name = $animal_name,
    animal.species = $species
MERGE (animal)-[:HOUSED_IN]->(enclosure)
MERGE (camera:Camera {camera_id: $camera_id})
MERGE (camera)-[:MONITORS]->(enclosure)
WITH animal, enclosure, camera
UNWIND $observations AS observation_data
MERGE (observation:Observation {observation_id: observation_data.observation_id})
SET observation.chunk_id = observation_data.chunk_id,
    observation.behavior = observation_data.behavior,
    observation.start_ts = datetime(observation_data.start_ts),
    observation.end_ts = datetime(observation_data.end_ts),
    observation.confidence = observation_data.confidence,
    observation.evidence = observation_data.evidence,
    observation.evidence_kind = observation_data.evidence_kind,
    observation.provider = observation_data.provider,
    observation.provider_model = observation_data.provider_model
MERGE (clip:Clip {clip_id: observation_data.chunk_id})
SET clip.source_path = $source_path,
    clip.start_ts = datetime(observation_data.start_ts),
    clip.end_ts = datetime(observation_data.end_ts)
MERGE (camera)-[:CAPTURED]->(clip)
MERGE (clip)-[:RECORDED_IN]->(enclosure)
MERGE (observation)-[:EVIDENCE_FROM]->(clip)
MERGE (observation)-[:OBSERVED_IN]->(enclosure)
MERGE (animal)-[:HAS_OBSERVATION]->(observation)
"""

WRITE_CLIP_EMBEDDING_CYPHER = """
MATCH (clip:Clip {clip_id: $clip_id})
SET clip.embedding = $embedding,
    clip.embedding_model = $embedding_model,
    clip.embedding_dimension = size($embedding)
"""

EVENT_CARDINALITY_CYPHER = """
OPTIONAL MATCH (event:WelfareEvent {event_id: $event_id})
OPTIONAL MATCH (observation:Observation)-[:SOURCE_FOR]->(event)
RETURN count(DISTINCT event) AS events,
       count(DISTINCT observation) AS observations
"""

READ_TIMELINE_CYPHER = """
MATCH (animal:Animal {animal_id: $animal_id})-[:HAS_EVENT]->(event:WelfareEvent)
RETURN event {
  .event_id, .behavior, .severity, .rule_fired, .rule_version,
  .action, .start_ts, .end_ts, .confidence, .review_state
} AS event
ORDER BY event.start_ts DESC
LIMIT $limit
"""

READ_ENCLOSURES_CYPHER = """
MATCH (enclosure:Enclosure)
WHERE enclosure.enclosure_id IS NOT NULL
RETURN DISTINCT enclosure.enclosure_id AS enclosure_id
ORDER BY enclosure_id
"""

READ_GRAPH_CYPHER = """
MATCH (enclosure:Enclosure)
WHERE $enclosure_id IS NULL OR enclosure.enclosure_id = $enclosure_id
OPTIONAL MATCH (animal:Animal)-[:HOUSED_IN]->(enclosure)
OPTIONAL MATCH (animal)-[:HAS_EVENT]->(event:WelfareEvent)
OPTIONAL MATCH (observation:Observation)-[:SOURCE_FOR]->(event)
OPTIONAL MATCH (direct_observation:Observation)-[:OBSERVED_IN]->(enclosure)
OPTIONAL MATCH (camera:Camera)-[:MONITORS]->(enclosure)
OPTIONAL MATCH (clip:Clip)-[:RECORDED_IN]->(enclosure)
WITH collect(DISTINCT enclosure)
   + collect(DISTINCT animal)
   + collect(DISTINCT event)
   + collect(DISTINCT observation)
   + collect(DISTINCT direct_observation)
   + collect(DISTINCT camera)
   + collect(DISTINCT clip) AS candidates
UNWIND candidates AS candidate
WITH collect(DISTINCT candidate) AS all_nodes
WITH [
  node IN all_nodes
  WHERE node IS NOT NULL
    AND ($include_observations OR NOT 'Observation' IN labels(node))
] AS nodes
CALL (nodes) {
  UNWIND nodes AS source
  OPTIONAL MATCH (source)-[relationship]->(target)
  WHERE target IN nodes
  RETURN collect(DISTINCT relationship) AS relationships
}
RETURN [
  node IN nodes | {
    element_id: elementId(node),
    labels: labels(node),
    properties: properties(node)
  }
] AS nodes,
[
  relationship IN relationships | {
    element_id: elementId(relationship),
    type: type(relationship),
    source_element_id: elementId(startNode(relationship)),
    target_element_id: elementId(endNode(relationship))
  }
] AS relationships
"""


class GraphEventBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animal_name: str
    species: str
    camera_id: str
    source_path: str
    event: EventRecord
    sources: list[Observation]

    @model_validator(mode="after")
    def validate_sources(self) -> GraphEventBundle:
        expected = set(self.event.source_observation_ids)
        actual = {source.observation_id for source in self.sources}
        if expected != actual:
            raise ValueError("graph bundle sources must exactly match the event provenance")
        return self

    def parameters(self) -> dict[str, Any]:
        event = self.event
        return {
            "animal_id": event.animal_id,
            "animal_name": self.animal_name,
            "species": self.species,
            "camera_id": self.camera_id,
            "source_path": self.source_path,
            "enclosure_id": event.enclosure_id,
            "event_id": event.event_id,
            "behavior": event.behavior.value,
            "severity": event.severity.value,
            "rule_fired": event.rule_fired,
            "rule_version": event.rule_version,
            "action": event.action.value if event.action else None,
            "start_ts": event.start_ts.isoformat(),
            "end_ts": event.end_ts.isoformat(),
            "confidence": event.confidence,
            "shift_mode": event.shift_mode.value,
            "review_state": event.review_state.value,
            "sources": [
                {
                    **source.model_dump(mode="json"),
                    "behavior": source.behavior.value,
                    "evidence_kind": source.evidence_kind.value,
                }
                for source in self.sources
            ],
        }


class GraphObservationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animal_name: str
    species: str
    camera_id: str
    source_path: str
    observations: list[Observation]

    @model_validator(mode="after")
    def validate_observations(self) -> GraphObservationBundle:
        if not self.observations:
            raise ValueError("graph observation bundle cannot be empty")
        expected = {
            (
                observation.animal_id,
                observation.enclosure_id,
                observation.chunk_id,
            )
            for observation in self.observations
        }
        if len(expected) != 1:
            raise ValueError("graph observations must belong to one animal and chunk")
        return self

    def parameters(self) -> dict[str, Any]:
        first = self.observations[0]
        return {
            "animal_id": first.animal_id,
            "animal_name": self.animal_name,
            "species": self.species,
            "camera_id": self.camera_id,
            "source_path": self.source_path,
            "enclosure_id": first.enclosure_id,
            "observations": [
                {
                    **observation.model_dump(mode="json"),
                    "behavior": observation.behavior.value,
                    "evidence_kind": observation.evidence_kind.value,
                }
                for observation in self.observations
            ],
        }


class Neo4jGraphWriter:
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        *,
        driver: Any | None = None,
    ):
        self.driver = driver or GraphDatabase.driver(uri, auth=(username, password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def initialize_schema(self, *, vector_dimension: int | None = None) -> None:
        if vector_dimension is not None and not 1 <= vector_dimension <= 4096:
            raise ValueError("vector dimension must be between 1 and 4096")

        def write(tx: Any) -> None:
            for query in SCHEMA_QUERIES:
                tx.run(query).consume()
            if vector_dimension is not None:
                tx.run(_clip_vector_index_cypher(vector_dimension)).consume()

        with self.driver.session() as session:
            session.execute_write(write)

    def write_event(self, bundle: GraphEventBundle) -> None:
        def write(tx: Any) -> None:
            tx.run(WRITE_EVENT_CYPHER, **bundle.parameters()).consume()

        with self.driver.session() as session:
            session.execute_write(write)

    def write_observations(self, bundle: GraphObservationBundle) -> None:
        def write(tx: Any) -> None:
            tx.run(WRITE_OBSERVATIONS_CYPHER, **bundle.parameters()).consume()

        with self.driver.session() as session:
            session.execute_write(write)

    def write_clip_embedding(
        self,
        *,
        clip_id: str,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        if not embedding:
            raise ValueError("clip embedding must not be empty")

        def write(tx: Any) -> None:
            tx.run(
                WRITE_CLIP_EMBEDDING_CYPHER,
                clip_id=clip_id,
                embedding=embedding,
                embedding_model=embedding_model,
            ).consume()

        with self.driver.session() as session:
            session.execute_write(write)

    def event_cardinality(self, event_id: str) -> dict[str, int]:
        def read(tx: Any) -> dict[str, int]:
            record = tx.run(EVENT_CARDINALITY_CYPHER, event_id=event_id).single(strict=True)
            return {
                "events": int(record["events"]),
                "observations": int(record["observations"]),
            }

        with self.driver.session() as session:
            return session.execute_read(read)

    def close(self) -> None:
        self.driver.close()


class Neo4jGraphReader:
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        *,
        driver: Any | None = None,
    ):
        self.driver = driver or GraphDatabase.driver(uri, auth=(username, password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def visual_graph(
        self,
        *,
        enclosure_id: str | None = None,
        include_observations: bool = True,
    ) -> dict[str, list[dict]]:
        def read(tx: Any) -> dict[str, list[dict]]:
            enclosures = [str(record["enclosure_id"]) for record in tx.run(READ_ENCLOSURES_CYPHER)]
            graph_record = tx.run(
                READ_GRAPH_CYPHER,
                enclosure_id=enclosure_id,
                include_observations=include_observations,
            ).single(strict=False)
            return {
                "nodes": list(graph_record["nodes"]) if graph_record else [],
                "relationships": list(graph_record["relationships"]) if graph_record else [],
                "enclosures": enclosures,
            }

        with self.driver.session() as session:
            return session.execute_read(read)

    def animal_timeline(self, animal_id: str, *, limit: int = 50) -> list[dict]:
        bounded_limit = max(1, min(limit, 200))

        def read(tx: Any) -> list[dict]:
            return [
                record["event"]
                for record in tx.run(
                    READ_TIMELINE_CYPHER,
                    animal_id=animal_id,
                    limit=bounded_limit,
                )
            ]

        with self.driver.session() as session:
            return session.execute_read(read)

    def close(self) -> None:
        self.driver.close()


def _clip_vector_index_cypher(dimension: int) -> str:
    return f"""
CREATE VECTOR INDEX clip_embedding IF NOT EXISTS
FOR (clip:Clip) ON (clip.embedding)
OPTIONS {{indexConfig: {{
  `vector.dimensions`: {dimension},
  `vector.similarity_function`: 'cosine'
}}}}
""".strip()
