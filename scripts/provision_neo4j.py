from __future__ import annotations

import argparse
import json

from zoovision.domain import EventRecord, Observation
from zoovision.graph import GraphEventBundle, Neo4jGraphWriter
from zoovision.settings import get_settings
from zoovision.store import SQLiteStore


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vector-dimension",
        type=int,
        required=True,
        help="dimension measured from the configured embedding provider response",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    settings = get_settings()
    if not all((settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password)):
        raise SystemExit("Neo4j application credentials are not configured")

    store = SQLiteStore(settings.database_path)
    store.initialize()
    animals = {row["animal_id"]: row for row in store.dump_table("animals")}
    observations = {row["observation_id"]: row for row in store.dump_table("observations")}
    sources_by_event: dict[str, list[str]] = {}
    for row in store.dump_table("event_sources"):
        sources_by_event.setdefault(row["event_id"], []).append(row["observation_id"])

    writer = Neo4jGraphWriter(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
    )
    try:
        writer.verify_connectivity()
        writer.initialize_schema(vector_dimension=arguments.vector_dimension)
        proof = []
        for row in store.dump_table("events"):
            source_ids = sorted(sources_by_event.get(row["event_id"], []))
            event = EventRecord.model_validate(
                {
                    **row,
                    "source_observation_ids": source_ids,
                    "explanation_facts": json.loads(row["explanation_facts_json"]),
                }
            )
            source_models = [
                Observation.model_validate(
                    {
                        **observations[source_id],
                        "enclosure_id": event.enclosure_id,
                    }
                )
                for source_id in source_ids
            ]
            animal = animals[event.animal_id]
            bundle = GraphEventBundle(
                animal_name=animal["name"],
                species=animal["species"],
                event=event,
                sources=source_models,
            )
            writer.write_event(bundle)
            writer.write_event(bundle)
            proof.append(
                {
                    "event_id": event.event_id,
                    **writer.event_cardinality(event.event_id),
                }
            )
        print(
            {
                "connected": True,
                "schema_initialized": True,
                "vector_dimension": arguments.vector_dimension,
                "idempotency": proof,
            }
        )
    finally:
        writer.close()


if __name__ == "__main__":
    main()
