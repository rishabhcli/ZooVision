from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from strands.agent.agent_result import AgentResult
from strands.multiagent import GraphBuilder, MultiAgentBase, MultiAgentResult, Status
from strands.multiagent.base import NodeResult
from strands.multiagent.graph import GraphState
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.event_loop import Metrics, Usage

from .alerts import AlertDeliveryContext, delivery_gate
from .aws_storage import AssetKind, S3Archive
from .domain import (
    AckState,
    BaselineState,
    EventRecord,
    Severity,
    ShiftMode,
    TriageInput,
)
from .graph import GraphEventBundle, GraphObservationBundle, Neo4jGraphWriter
from .ids import event_id, stable_id
from .providers import ProviderAnalysis, VideoChunkContext
from .stitching import stitch_observations
from .store import SQLiteStore
from .triage import classify


class Analyzer(Protocol):
    def safe_analyze_url(
        self,
        video_url: str,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis: ...

    def safe_analyze_file(
        self,
        path: str | Path,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis: ...


class SegmentWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk: VideoChunkContext
    animal_name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=160)
    camera_id: str = Field(min_length=1, max_length=120)
    source_path: str = Field(min_length=1)
    content_sha256: str = Field(min_length=1)
    source_offset_seconds: float = Field(default=0, ge=0)
    video_url: str | None = None
    local_video_path: Path | None = None
    shift_mode: ShiftMode
    baseline_state: BaselineState
    fixture_mode: bool = True
    delivery_enabled: bool = False
    webhook_configured: bool = False
    hours_since_water_contact: float | None = Field(default=None, ge=0)
    inactivity_z: float | None = None
    baseline_delta_z: float | None = None

    @model_validator(mode="after")
    def validate_video_source(self) -> SegmentWorkflowInput:
        if (self.video_url is None) == (self.local_video_path is None):
            raise ValueError("exactly one video source is required")
        return self


class WorkflowAuditEntry(BaseModel):
    node_id: str
    status: str
    elapsed_ms: int = Field(ge=0)
    event_ids: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)


class SegmentWorkflowResult(BaseModel):
    route: str
    observation_count: int
    event_ids: list[str]
    rules_fired: list[str]
    data_gap_id: str | None = None
    raw_archive_uri: str | None = None
    analysis_archive_uri: str | None = None
    baseline_candidate_observation_ids: list[str] = Field(default_factory=list)
    audit: list[WorkflowAuditEntry]


class _FunctionNode(MultiAgentBase):
    def __init__(
        self,
        function: Callable[[dict[str, Any]], dict[str, Any]],
        node_id: str,
    ):
        super().__init__()
        self.id = node_id
        self.function = function

    async def invoke_async(
        self,
        task: Any,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        del task, kwargs
        state = invocation_state if invocation_state is not None else {}
        started = time.perf_counter()
        payload = self.function(state)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        audit = state.setdefault("audit", [])
        audit.append(
            WorkflowAuditEntry(
                node_id=self.id,
                status="completed",
                elapsed_ms=elapsed_ms,
                event_ids=list(state.get("event_ids", [])),
                rules_fired=list(state.get("rules_fired", [])),
            )
        )
        result = AgentResult(
            stop_reason="end_turn",
            message={
                "role": "assistant",
                "content": [{"text": json.dumps(payload, sort_keys=True)}],
            },
            metrics=EventLoopMetrics(),
            state={},
        )
        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                self.id: NodeResult(
                    result=result,
                    status=Status.COMPLETED,
                    execution_time=elapsed_ms,
                    accumulated_usage=Usage(
                        inputTokens=0,
                        outputTokens=0,
                        totalTokens=0,
                    ),
                    accumulated_metrics=Metrics(latencyMs=elapsed_ms),
                    execution_count=1,
                )
            },
            execution_count=1,
            execution_time=elapsed_ms,
        )


class SegmentWorkflow:
    def __init__(
        self,
        *,
        analyzer: Analyzer,
        store: SQLiteStore,
        graph_writer: Neo4jGraphWriter | None = None,
        archive: S3Archive | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.analyzer = analyzer
        self.store = store
        self.graph_writer = graph_writer
        self.archive = archive
        self.now = now or (lambda: datetime.now(UTC))

    def run(self, request: SegmentWorkflowInput) -> SegmentWorkflowResult:
        state: dict[str, Any] = {
            "request": request,
            "audit": [],
            "event_ids": [],
            "rules_fired": [],
        }
        graph = self._build_graph()
        result = graph("process one camera segment", invocation_state=state)
        if result.status is not Status.COMPLETED:
            raise RuntimeError(f"segment workflow ended with {result.status.value}")
        return SegmentWorkflowResult(
            route=state["route"],
            observation_count=len(state["analysis"].observations),
            event_ids=state["event_ids"],
            rules_fired=state["rules_fired"],
            data_gap_id=(state["analysis"].data_gap.gap_id if state["analysis"].data_gap else None),
            raw_archive_uri=state.get("raw_archive_uri"),
            analysis_archive_uri=state.get("analysis_archive_uri"),
            baseline_candidate_observation_ids=state.get(
                "baseline_candidate_observation_ids",
                [],
            ),
            audit=state["audit"],
        )

    def _build_graph(self):
        builder = GraphBuilder()
        builder.add_node(_FunctionNode(self._ingest, "ingest"), "ingest")
        builder.add_node(_FunctionNode(self._record_gap, "data_gap"), "data_gap")
        builder.add_node(_FunctionNode(self._record_day, "day_observation"), "day_observation")
        builder.add_node(_FunctionNode(self._triage_night, "triage"), "triage")
        builder.add_node(_FunctionNode(self._index_night, "index"), "index")
        builder.add_edge("ingest", "data_gap", condition=_has_data_gap)
        builder.add_edge("ingest", "day_observation", condition=_is_complete_day)
        builder.add_edge("ingest", "triage", condition=_is_complete_night)
        builder.add_edge("triage", "index")
        builder.set_entry_point("ingest")
        builder.set_execution_timeout(900)
        builder.set_node_timeout(300)
        builder.set_max_node_executions(5)
        return builder.build()

    def _ingest(self, state: dict[str, Any]) -> dict[str, Any]:
        request: SegmentWorkflowInput = state["request"]
        chunk = request.chunk
        self.store.upsert_animal(
            animal_id=chunk.animal_id,
            name=request.animal_name,
            species=request.species,
            enclosure_id=chunk.enclosure_id,
            baseline_state=request.baseline_state.value,
        )
        self.store.upsert_video_chunk(
            chunk_id=chunk.chunk_id,
            enclosure_id=chunk.enclosure_id,
            camera_id=request.camera_id,
            start_ts=chunk.start_ts.isoformat(),
            end_ts=chunk.end_ts.isoformat(),
            source_path=request.source_path,
            source_offset_seconds=request.source_offset_seconds,
            content_sha256=request.content_sha256,
            status="analyzing",
        )
        if self.archive is not None and request.local_video_path is not None:
            state["raw_archive_uri"] = self.archive.upload_file(
                AssetKind.RAW,
                request.local_video_path,
                object_key=(
                    f"{chunk.animal_id}/{chunk.chunk_id}{request.local_video_path.suffix.lower()}"
                ),
                content_type="video/mp4",
                metadata={
                    "animal-id": chunk.animal_id,
                    "chunk-id": chunk.chunk_id,
                    "enclosure-id": chunk.enclosure_id,
                },
            )
        if request.video_url:
            analysis = self.analyzer.safe_analyze_url(request.video_url, chunk)
        else:
            analysis = self.analyzer.safe_analyze_file(request.local_video_path, chunk)
        state["analysis"] = analysis
        if self.archive is not None:
            state["analysis_archive_uri"] = self.archive.upload_json(
                AssetKind.ANALYSIS,
                analysis.model_dump(mode="json"),
                object_key=f"{chunk.animal_id}/{chunk.chunk_id}.json",
                metadata={
                    "animal-id": chunk.animal_id,
                    "chunk-id": chunk.chunk_id,
                    "enclosure-id": chunk.enclosure_id,
                },
            )
        if self.graph_writer is not None and analysis.observations:
            self.graph_writer.write_observations(
                GraphObservationBundle(
                    animal_name=request.animal_name,
                    species=request.species,
                    camera_id=request.camera_id,
                    source_path=request.source_path,
                    observations=analysis.observations,
                )
            )
        for observation in analysis.observations:
            self.store.save_observation(observation)
        self.store.upsert_video_chunk(
            chunk_id=chunk.chunk_id,
            enclosure_id=chunk.enclosure_id,
            camera_id=request.camera_id,
            start_ts=chunk.start_ts.isoformat(),
            end_ts=chunk.end_ts.isoformat(),
            source_path=request.source_path,
            source_offset_seconds=request.source_offset_seconds,
            content_sha256=request.content_sha256,
            status="coverage_gap" if analysis.data_gap else "analyzed",
        )
        return {
            "observation_count": len(analysis.observations),
            "has_data_gap": analysis.data_gap is not None,
        }

    def _record_gap(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis: ProviderAnalysis = state["analysis"]
        if analysis.data_gap is None:
            raise RuntimeError("data-gap route requires a DataGap")
        self.store.save_data_gap(analysis.data_gap)
        state["route"] = "data_gap"
        return {"data_gap_id": analysis.data_gap.gap_id}

    def _record_day(self, state: dict[str, Any]) -> dict[str, Any]:
        analysis: ProviderAnalysis = state["analysis"]
        state["route"] = "day_observation"
        state["baseline_candidate_observation_ids"] = [
            observation.observation_id for observation in analysis.observations
        ]
        return {"baseline_candidate_observation_ids": state["baseline_candidate_observation_ids"]}

    def _triage_night(self, state: dict[str, Any]) -> dict[str, Any]:
        request: SegmentWorkflowInput = state["request"]
        analysis: ProviderAnalysis = state["analysis"]
        events: list[EventRecord] = []
        for stitched in stitch_observations(analysis.observations):
            decision = classify(
                TriageInput(
                    animal_id=stitched.animal_id,
                    behavior=stitched.behavior,
                    continuous_duration_minutes=stitched.duration_minutes,
                    hours_since_water_contact=request.hours_since_water_contact,
                    inactivity_z=request.inactivity_z,
                    baseline_delta_z=request.baseline_delta_z,
                    source_observation_ids=stitched.source_observation_ids,
                )
            )
            if decision.severity is Severity.NONE:
                continue
            record = EventRecord(
                event_id=event_id(
                    stitched.animal_id,
                    stitched.behavior,
                    stitched.source_observation_ids,
                    decision.rule_version,
                ),
                animal_id=stitched.animal_id,
                enclosure_id=stitched.enclosure_id,
                behavior=stitched.behavior,
                start_ts=stitched.start_ts,
                end_ts=stitched.end_ts,
                severity=decision.severity,
                rule_fired=decision.rule_fired,
                action=decision.action,
                confidence=stitched.confidence,
                baseline_delta_z=request.baseline_delta_z,
                source_observation_ids=stitched.source_observation_ids,
                explanation_facts=decision.explanation_facts,
                rule_version=decision.rule_version,
                shift_mode=ShiftMode.NIGHT,
                created_at=self.now(),
            )
            self.store.save_event(record)
            gate = delivery_gate(
                record,
                AlertDeliveryContext(
                    fixture_mode=request.fixture_mode,
                    delivery_enabled=request.delivery_enabled,
                    webhook_configured=request.webhook_configured,
                    baseline_state=request.baseline_state,
                ),
            )
            self.store.save_alert(
                alert_id=stable_id("alt", record.event_id, "keeper-console"),
                event_id=record.event_id,
                channel="keeper_console",
                delivery_status="queued" if gate.allowed else "shadowed",
                ack_state=AckState.PENDING.value,
            )
            events.append(record)
        state["events"] = events
        state["event_ids"] = [event.event_id for event in events]
        state["rules_fired"] = [
            event.rule_fired for event in events if event.rule_fired is not None
        ]
        state["route"] = "night_triage"
        return {
            "event_ids": state["event_ids"],
            "rules_fired": state["rules_fired"],
        }

    def _index_night(self, state: dict[str, Any]) -> dict[str, Any]:
        if self.graph_writer is None:
            return {"graph_write": "not_configured"}
        request: SegmentWorkflowInput = state["request"]
        analysis: ProviderAnalysis = state["analysis"]
        sources = {item.observation_id: item for item in analysis.observations}
        for event in state["events"]:
            self.graph_writer.write_event(
                GraphEventBundle(
                    animal_name=request.animal_name,
                    species=request.species,
                    camera_id=request.camera_id,
                    source_path=request.source_path,
                    event=event,
                    sources=[sources[source_id] for source_id in event.source_observation_ids],
                )
            )
        return {"graph_write": "complete", "events": len(state["events"])}


def _has_data_gap(
    state: GraphState,
    *,
    invocation_state: dict[str, Any],
    **kwargs: Any,
) -> bool:
    del state, kwargs
    analysis: ProviderAnalysis = invocation_state["analysis"]
    return analysis.data_gap is not None


def _is_complete_day(
    state: GraphState,
    *,
    invocation_state: dict[str, Any],
    **kwargs: Any,
) -> bool:
    del state, kwargs
    request: SegmentWorkflowInput = invocation_state["request"]
    analysis: ProviderAnalysis = invocation_state["analysis"]
    return analysis.data_gap is None and request.shift_mode is ShiftMode.DAY


def _is_complete_night(
    state: GraphState,
    *,
    invocation_state: dict[str, Any],
    **kwargs: Any,
) -> bool:
    del state, kwargs
    request: SegmentWorkflowInput = invocation_state["request"]
    analysis: ProviderAnalysis = invocation_state["analysis"]
    return analysis.data_gap is None and request.shift_mode is ShiftMode.NIGHT
