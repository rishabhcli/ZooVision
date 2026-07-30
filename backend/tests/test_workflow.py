from datetime import UTC, datetime, timedelta

from zoovision.domain import (
    BaselineState,
    Behavior,
    DataGap,
    EvidenceKind,
    Observation,
    ShiftMode,
)
from zoovision.providers import ProviderAnalysis, VideoChunkContext
from zoovision.store import SQLiteStore
from zoovision.workflow import SegmentWorkflow, SegmentWorkflowInput


class FakeAnalyzer:
    def __init__(self, analysis):
        self.analysis = analysis

    def safe_analyze_url(self, video_url, chunk):
        return self.analysis

    def safe_analyze_file(self, path, chunk):
        return self.analysis


class FakeGraphWriter:
    def __init__(self):
        self.bundles = []
        self.observation_bundles = []

    def write_event(self, bundle):
        self.bundles.append(bundle)

    def write_observations(self, bundle):
        self.observation_bundles.append(bundle)


def request(*, mode=ShiftMode.NIGHT):
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    return SegmentWorkflowInput(
        chunk=VideoChunkContext(
            chunk_id="chunk-workflow-1",
            animal_id="animal-1",
            enclosure_id="ENC-01",
            start_ts=start,
            end_ts=start + timedelta(minutes=15),
        ),
        animal_name="Nox",
        species="European badger",
        camera_id="CAM-01",
        source_path="fixtures/sample.mp4",
        content_sha256="a" * 64,
        video_url="https://media.example/sample.mp4",
        shift_mode=mode,
        baseline_state=BaselineState.SHADOW,
        fixture_mode=True,
        hours_since_water_contact=7,
    )


def observation_analysis():
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    return ProviderAnalysis(
        observations=[
            Observation(
                observation_id="obs-workflow-1",
                animal_id="animal-1",
                enclosure_id="ENC-01",
                chunk_id="chunk-workflow-1",
                behavior=Behavior.PACING,
                start_ts=start,
                end_ts=start + timedelta(minutes=12),
                confidence=0.9,
                evidence="Repeated route along the boundary.",
                provider="fixture",
                provider_model="scenario-v1",
                evidence_kind=EvidenceKind.SYNTHETIC_SCENARIO,
            )
        ]
    )


def initialized_store(tmp_path):
    store = SQLiteStore(tmp_path / "workflow.db")
    store.initialize()
    store.upsert_animal(
        animal_id="animal-1",
        name="Nox",
        species="European badger",
        enclosure_id="ENC-01",
        baseline_state="shadow",
    )
    return store


def test_night_workflow_uses_deterministic_triage_and_graph_write(tmp_path):
    store = initialized_store(tmp_path)
    graph_writer = FakeGraphWriter()
    workflow = SegmentWorkflow(
        analyzer=FakeAnalyzer(observation_analysis()),
        store=store,
        graph_writer=graph_writer,
        now=lambda: datetime(2026, 7, 30, 3, tzinfo=UTC),
    )

    result = workflow.run(request())

    assert result.route == "night_triage"
    assert result.rules_fired == ["R005_PACING_10M"]
    assert len(result.event_ids) == 1
    assert [entry.node_id for entry in result.audit] == ["ingest", "triage", "index"]
    assert store.dump_table("events")[0]["rule_fired"] == "R005_PACING_10M"
    assert store.dump_table("alerts")[0]["delivery_status"] == "shadowed"
    assert store.dump_table("video_chunks")[0]["status"] == "analyzed"
    assert len(graph_writer.bundles) == 1
    assert len(graph_writer.observation_bundles) == 1


def test_day_workflow_never_triages_or_creates_alert(tmp_path):
    store = initialized_store(tmp_path)
    workflow = SegmentWorkflow(
        analyzer=FakeAnalyzer(observation_analysis()),
        store=store,
    )

    result = workflow.run(request(mode=ShiftMode.DAY))

    assert result.route == "day_observation"
    assert result.event_ids == []
    assert result.baseline_candidate_observation_ids == ["obs-workflow-1"]
    assert [entry.node_id for entry in result.audit] == ["ingest", "day_observation"]
    assert store.dump_table("events") == []
    assert store.dump_table("alerts") == []


def test_provider_gap_routes_away_from_triage(tmp_path):
    store = initialized_store(tmp_path)
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    analysis = ProviderAnalysis(
        observations=[],
        data_gap=DataGap(
            gap_id="gap-1",
            enclosure_id="ENC-01",
            chunk_id="chunk-workflow-1",
            start_ts=start,
            end_ts=start + timedelta(minutes=15),
            reason="provider_analysis_failed",
        ),
    )
    workflow = SegmentWorkflow(analyzer=FakeAnalyzer(analysis), store=store)

    result = workflow.run(request())

    assert result.route == "data_gap"
    assert result.data_gap_id == "gap-1"
    assert result.event_ids == []
    assert [entry.node_id for entry in result.audit] == ["ingest", "data_gap"]
    assert store.dump_table("events") == []
    assert store.dump_table("video_chunks")[0]["status"] == "coverage_gap"
