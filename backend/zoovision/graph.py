from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from pydantic import BaseModel, ConfigDict, model_validator

from .domain import EventRecord, Observation

WRITE_EVENT_CYPHER = """
MERGE (enclosure:Enclosure {enclosure_id: $enclosure_id})
MERGE (animal:Animal {animal_id: $animal_id})
SET animal.name = $animal_name,
    animal.species = $species
MERGE (animal)-[:HOUSED_IN]->(enclosure)
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
MERGE (observation)-[:SOURCE_FOR]->(event)
MERGE (observation)-[:OBSERVED_IN]->(enclosure)
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


class GraphEventBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animal_name: str
    species: str
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

    def write_event(self, bundle: GraphEventBundle) -> None:
        def write(tx: Any) -> None:
            tx.run(WRITE_EVENT_CYPHER, **bundle.parameters()).consume()

        with self.driver.session() as session:
            session.execute_write(write)

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
