from datetime import UTC, datetime, timedelta

import pytest
from zoovision.domain import (
    AlertAction,
    Behavior,
    EventRecord,
    EvidenceKind,
    Observation,
    Severity,
    ShiftMode,
)
from zoovision.graph import WRITE_EVENT_CYPHER, GraphEventBundle, Neo4jGraphWriter


class FakeResult:
    def consume(self):
        return None


class FakeTransaction:
    def __init__(self):
        self.query = None
        self.parameters = None

    def run(self, query, **parameters):
        self.query = query
        self.parameters = parameters
        return FakeResult()


class FakeSession:
    def __init__(self, transaction):
        self.transaction = transaction

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute_write(self, function):
        return function(self.transaction)


class FakeDriver:
    def __init__(self):
        self.transaction = FakeTransaction()

    def session(self):
        return FakeSession(self.transaction)

    def close(self):
        return None


def bundle():
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    observation = Observation(
        observation_id="obs-1",
        animal_id="animal-1",
        enclosure_id="ENC-01",
        chunk_id="chunk-1",
        behavior=Behavior.PACING,
        start_ts=start,
        end_ts=start + timedelta(minutes=21),
        confidence=0.9,
        evidence="Repeated route.",
        provider="fixture",
        provider_model="scenario-v1",
        evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
    )
    event = EventRecord(
        event_id="evt-1",
        animal_id="animal-1",
        enclosure_id="ENC-01",
        behavior=Behavior.PACING,
        start_ts=start,
        end_ts=start + timedelta(minutes=21),
        severity=Severity.HIGH,
        rule_fired="R004_PACING_20M_NO_WATER_6H",
        action=AlertAction.VERIFY_WATER,
        confidence=0.9,
        source_observation_ids=["obs-1"],
        explanation_facts=["Continuous pacing lasted 21.0 minutes."],
        rule_version="2026-07-30.v1",
        shift_mode=ShiftMode.NIGHT,
        created_at=start,
    )
    return GraphEventBundle(
        animal_name="Nox",
        species="European badger",
        event=event,
        sources=[observation],
    )


def test_graph_writer_uses_static_idempotent_merge_query():
    driver = FakeDriver()
    Neo4jGraphWriter("unused", "unused", "unused", driver=driver).write_event(bundle())
    assert driver.transaction.query == WRITE_EVENT_CYPHER
    assert "MERGE (event:WelfareEvent {event_id: $event_id})" in WRITE_EVENT_CYPHER
    assert driver.transaction.parameters["event_id"] == "evt-1"
    assert driver.transaction.parameters["sources"][0]["observation_id"] == "obs-1"


def test_graph_bundle_requires_exact_event_sources():
    value = bundle()
    value.event.source_observation_ids = ["obs-other"]
    with pytest.raises(ValueError, match="exactly"):
        GraphEventBundle.model_validate(value.model_dump())
