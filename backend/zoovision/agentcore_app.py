from __future__ import annotations

from functools import lru_cache
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.models import PingStatus

from .api import (
    build_archive,
    build_embedder,
    build_escalation_scheduler,
    build_evidence_enricher,
    build_graph_writer,
)
from .providers import TwelveLabsAnalyzer
from .settings import Settings
from .store import SQLiteStore
from .workflow import SegmentWorkflow, SegmentWorkflowInput

app = BedrockAgentCoreApp()


@app.ping
def health() -> PingStatus:
    return PingStatus.HEALTHY


@lru_cache
def _runtime() -> tuple[Settings, SQLiteStore, SegmentWorkflow]:
    settings = Settings()
    store = SQLiteStore(settings.database_path)
    store.initialize()
    workflow = SegmentWorkflow(
        analyzer=TwelveLabsAnalyzer(
            settings.twelvelabs_api_key,
            model=settings.twelvelabs_model,
        ),
        store=store,
        graph_writer=build_graph_writer(settings),
        archive=build_archive(settings),
        embedder=build_embedder(settings),
        evidence_enricher=build_evidence_enricher(settings),
        escalation_scheduler=build_escalation_scheduler(settings),
        alert_ack_minutes=settings.alert_ack_minutes,
    )
    return settings, store, workflow


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    operation = payload.get("operation", "process_segment")
    _, store, workflow = _runtime()

    if operation == "health":
        return {"status": "healthy", "service": "zoovision-orchestrator"}

    if operation == "escalate_unacknowledged":
        alert_id = str(payload.get("alert_id", ""))
        if not alert_id:
            raise ValueError("alert_id is required")
        previous_state = store.alert_state(alert_id)
        escalated = store.escalate_pending_alert(alert_id)
        return {
            "alert_id": alert_id,
            "previous_state": previous_state,
            "status": "escalated" if escalated else "no_action",
        }

    if operation != "process_segment":
        raise ValueError(f"unsupported operation: {operation}")
    request = SegmentWorkflowInput.model_validate(payload.get("segment"))
    if request.video_url is None:
        raise ValueError("AgentCore segment processing requires a public or signed video_url")
    result = workflow.run(request)
    return result.model_dump(mode="json")


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
