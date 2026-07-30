"""Turn an arbitrary video file into reviewed welfare evidence.

The console ships with pinned fixtures, but the product has to accept whatever
footage a facility actually has. This module owns that path: probe a real
container, split it into analyzable segments, measure motion regions, ask the
video provider for behavior semantics, and hand each segment to the existing
deterministic :class:`~zoovision.workflow.SegmentWorkflow`.

Nothing here assigns severity. Segments route through the same triage rules and
the same idempotent writes as fixture footage, so an uploaded video and a pinned
fixture produce evidence of identical shape and provenance.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .detection import (
    DetectorConfig,
    VideoProbe,
    detections_for_chunk,
    probe_video,
    run_media_tool,
)
from .domain import (
    BaselineState,
    Behavior,
    Detection,
    DetectionSource,
    EvidenceKind,
    Observation,
    ShiftMode,
)
from .ids import stable_id
from .providers import ProviderAnalysis, VideoChunkContext
from .store import SQLiteStore
from .workflow import SegmentWorkflow, SegmentWorkflowInput

#: TwelveLabs rejects base64 payloads above roughly 22 MB, so segments larger
#: than this are transcoded down before they are offered to the provider.
PROVIDER_PAYLOAD_LIMIT_BYTES = 20 * 1024 * 1024


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str = Field(min_length=1, max_length=255)
    animal_id: str = Field(min_length=1, max_length=120)
    animal_name: str = Field(min_length=1, max_length=120)
    species: str = Field(min_length=1, max_length=160)
    enclosure_id: str = Field(min_length=1, max_length=120)
    camera_id: str = Field(min_length=1, max_length=120)
    start_ts: datetime
    shift_mode: ShiftMode = ShiftMode.NIGHT
    segment_seconds: int = Field(default=120, ge=10, le=900)
    max_segments: int = Field(default=12, ge=1, le=240)
    use_provider: bool = True

    @model_validator(mode="after")
    def validate_start(self) -> IngestRequest:
        if self.start_ts.tzinfo is None:
            raise ValueError("start_ts must be timezone-aware")
        if "/" in self.source_name or "\\" in self.source_name:
            raise ValueError("source_name must be a bare file name")
        return self


class IngestSegmentResult(BaseModel):
    index: int
    chunk_id: str
    start_ts: datetime
    duration_seconds: float
    route: str
    observation_count: int
    detection_count: int
    event_ids: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)
    data_gap_id: str | None = None


class IngestJob(BaseModel):
    job_id: str
    status: str
    source_name: str
    animal_id: str
    enclosure_id: str
    created_at: datetime
    updated_at: datetime
    analyzer: str
    total_segments: int = 0
    completed_segments: int = 0
    detection_count: int = 0
    event_ids: list[str] = Field(default_factory=list)
    rules_fired: list[str] = Field(default_factory=list)
    data_gap_ids: list[str] = Field(default_factory=list)
    segments: list[IngestSegmentResult] = Field(default_factory=list)
    probe: VideoProbe | None = None
    error: str | None = None


class MotionEvidenceAnalyzer:
    """Derives observations from measured motion, with no model in the loop.

    This is the analyzer of record when no video provider is configured, and it
    runs alongside the provider when one is. It can only state what the pixels
    support: that motion regions were present, or that none were measured for a
    sustained stretch. Behavior naming stops at ``OTHER`` and ``INACTIVITY``
    because motion alone cannot distinguish pacing from foraging.
    """

    provider = "zoovision-motion"
    provider_model = "mog2-v1"

    def __init__(
        self,
        detections: list[Detection],
        *,
        sample_fps: float = 2.0,
        min_inactivity_minutes: float = 2.0,
        min_activity_seconds: float = 4.0,
        merge_gap_seconds: float = 2.0,
    ):
        self.detections = detections
        self.sample_fps = sample_fps
        self.min_inactivity_minutes = min_inactivity_minutes
        self.min_activity_seconds = min_activity_seconds
        self.merge_gap_seconds = merge_gap_seconds

    def safe_analyze_file(self, path: str | Path, chunk: VideoChunkContext) -> ProviderAnalysis:
        del path
        return self.analyze(chunk)

    def safe_analyze_url(self, video_url: str, chunk: VideoChunkContext) -> ProviderAnalysis:
        del video_url
        return self.analyze(chunk)

    def analyze(self, chunk: VideoChunkContext) -> ProviderAnalysis:
        spans = self._motion_spans(chunk.duration_seconds)
        observations: list[Observation] = []
        for kind, start, end in spans:
            if end <= start:
                continue
            behavior = Behavior.INACTIVITY if kind == "still" else Behavior.OTHER
            tracks = {d.track_id for d in self.detections if start <= d.relative_seconds <= end}
            if kind == "still":
                evidence = (
                    f"No motion region was measured for {(end - start) / 60:.1f} minutes "
                    "of this segment."
                )
            else:
                evidence = (
                    f"Motion regions were measured for {end - start:.0f} seconds "
                    f"across {len(tracks)} track(s). Motion alone does not identify "
                    "the behavior."
                )
            observations.append(
                Observation(
                    observation_id=stable_id(
                        "obs",
                        chunk.chunk_id,
                        self.provider,
                        kind,
                        round(start, 2),
                    ),
                    animal_id=chunk.animal_id,
                    enclosure_id=chunk.enclosure_id,
                    chunk_id=chunk.chunk_id,
                    behavior=behavior,
                    start_ts=chunk.start_ts + timedelta(seconds=start),
                    end_ts=chunk.start_ts + timedelta(seconds=end),
                    confidence=0.6,
                    evidence=evidence,
                    provider=self.provider,
                    provider_model=self.provider_model,
                    evidence_kind=EvidenceKind.MEASURED_MOTION,
                )
            )
        return ProviderAnalysis(observations=observations, data_gap=None)

    def _motion_spans(self, duration_seconds: float) -> list[tuple[str, float, float]]:
        step = 1.0 / self.sample_fps
        active = sorted({round(d.relative_seconds, 3) for d in self.detections})
        spans: list[tuple[str, float, float]] = []
        cursor = 0.0
        for moment in active:
            if moment - cursor >= self.min_inactivity_minutes * 60:
                spans.append(("still", cursor, moment))
            cursor = max(cursor, moment + step)
        if duration_seconds - cursor >= self.min_inactivity_minutes * 60:
            spans.append(("still", cursor, duration_seconds))
        if active:
            # A body is routinely missed for a few sampled frames while it pauses
            # or blends into the background. Merging across a real duration rather
            # than a multiple of the sampling step keeps one continuous movement
            # as one span; splitting on the step fragments it into slivers that
            # the activity floor then discards, reporting no motion at all.
            merge_gap = max(self.merge_gap_seconds, step * 3)
            run_start = active[0]
            previous = active[0]
            for moment in active[1:]:
                if moment - previous > merge_gap:
                    spans.append(("motion", run_start, previous + step))
                    run_start = moment
                previous = moment
            spans.append(("motion", run_start, min(previous + step, duration_seconds)))
        return [
            (kind, start, end)
            for kind, start, end in spans
            if kind == "still" or end - start >= self.min_activity_seconds
        ]


class CompositeAnalyzer:
    """Provider semantics plus measured motion, merged into one analysis.

    A provider failure still yields the motion track and a recorded
    :class:`~zoovision.domain.DataGap`, so reduced coverage is visible rather
    than silently converted into a normal result.
    """

    def __init__(self, primary: Any, motion: MotionEvidenceAnalyzer):
        self.primary = primary
        self.motion = motion

    def safe_analyze_file(self, path: str | Path, chunk: VideoChunkContext) -> ProviderAnalysis:
        return self._merge(self.primary.safe_analyze_file(path, chunk), chunk)

    def safe_analyze_url(self, video_url: str, chunk: VideoChunkContext) -> ProviderAnalysis:
        return self._merge(self.primary.safe_analyze_url(video_url, chunk), chunk)

    def _merge(
        self,
        provider_analysis: ProviderAnalysis,
        chunk: VideoChunkContext,
    ) -> ProviderAnalysis:
        motion_analysis = self.motion.analyze(chunk)
        seen = {item.observation_id for item in provider_analysis.observations}
        merged = list(provider_analysis.observations)
        for observation in motion_analysis.observations:
            if observation.observation_id not in seen:
                merged.append(observation)
        merged.sort(key=lambda item: (item.start_ts, item.observation_id))
        return ProviderAnalysis(
            observations=merged,
            data_gap=provider_analysis.data_gap,
            uncertainty=provider_analysis.uncertainty,
        )


def segment_video(
    source: Path,
    destination: Path,
    *,
    segment_seconds: int,
    max_segments: int,
) -> list[tuple[int, float, float, Path]]:
    """Split a real file into analyzable pieces.

    Uses ffmpeg's segment muxer with stream copy, which cuts on keyframes and so
    yields segments whose durations vary slightly from the requested length.
    Each piece is re-probed and the true duration is used to place it on the
    wall clock, rather than assuming the nominal length.
    """
    destination.mkdir(parents=True, exist_ok=True)
    pattern = destination / "segment_%04d.mp4"
    completed = run_media_tool(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-c",
            "copy",
            "-map",
            "0:v:0",
            "-f",
            "segment",
            "-segment_time",
            str(segment_seconds),
            "-reset_timestamps",
            "1",
            str(pattern),
        ],
        timeout=900,
    )
    pieces = sorted(destination.glob("segment_*.mp4"))
    if completed.returncode != 0 and not pieces:
        raise ValueError(f"ffmpeg could not segment {source.name}")
    results: list[tuple[int, float, float, Path]] = []
    offset = 0.0
    for index, piece in enumerate(pieces[:max_segments]):
        try:
            duration = probe_video(piece).duration_seconds
        except ValueError:
            continue
        results.append((index, offset, duration, piece))
        offset += duration
    if not results:
        raise ValueError(f"no readable segments were produced from {source.name}")
    return results


class VideoIngestService:
    """Runs ingestion jobs and records their progress in the store."""

    def __init__(
        self,
        *,
        store: SQLiteStore,
        raw_root: Path,
        analyzer_factory: Callable[[], Any] | None = None,
        detector_config: DetectorConfig | None = None,
        graph_writer: Any | None = None,
        archive: Any | None = None,
        embedder: Any | None = None,
        evidence_enricher: Any | None = None,
        escalation_scheduler: Any | None = None,
        alert_ack_minutes: int = 20,
        fixture_mode: bool = True,
        delivery_enabled: bool = False,
        webhook_configured: bool = False,
        now: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.raw_root = Path(raw_root)
        self.analyzer_factory = analyzer_factory
        self.detector_config = detector_config or DetectorConfig()
        self.graph_writer = graph_writer
        self.archive = archive
        self.embedder = embedder
        self.evidence_enricher = evidence_enricher
        self.escalation_scheduler = escalation_scheduler
        self.alert_ack_minutes = alert_ack_minutes
        self.fixture_mode = fixture_mode
        self.delivery_enabled = delivery_enabled
        self.webhook_configured = webhook_configured
        self.now = now or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()

    def resolve_source(self, source_name: str) -> Path:
        """Resolve an upload name to a real file inside the raw root."""
        candidate = (self.raw_root / "uploads" / source_name).resolve()
        root = (self.raw_root / "uploads").resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise FileNotFoundError(f"no ingestible video named {source_name}")
        return candidate

    def start(self, request: IngestRequest) -> IngestJob:
        job = self._new_job(request)
        self.store.save_ingest_job(job.model_dump(mode="json"))
        thread = threading.Thread(
            target=self._run_guarded,
            args=(job.job_id, request),
            name=f"ingest-{job.job_id[:12]}",
            daemon=True,
        )
        thread.start()
        return job

    def run(self, request: IngestRequest) -> IngestJob:
        """Run a job to completion on the calling thread."""
        job = self._new_job(request)
        self.store.save_ingest_job(job.model_dump(mode="json"))
        return self._run_guarded(job.job_id, request)

    def status(self, job_id: str) -> IngestJob | None:
        row = self.store.ingest_job(job_id)
        return IngestJob.model_validate(row) if row else None

    def recent(self, limit: int = 20) -> list[IngestJob]:
        return [IngestJob.model_validate(row) for row in self.store.recent_ingest_jobs(limit)]

    def _new_job(self, request: IngestRequest) -> IngestJob:
        moment = self.now()
        return IngestJob(
            job_id=stable_id("job", request.source_name, request.animal_id, moment.isoformat()),
            status="queued",
            source_name=request.source_name,
            animal_id=request.animal_id,
            enclosure_id=request.enclosure_id,
            created_at=moment,
            updated_at=moment,
            analyzer="provider+motion" if request.use_provider else "motion",
        )

    def _run_guarded(self, job_id: str, request: IngestRequest) -> IngestJob:
        try:
            return self._run(job_id, request)
        except Exception as error:  # noqa: BLE001 - surfaced to the operator as job state
            job = self.status(job_id)
            if job is None:
                raise
            job.status = "failed"
            job.error = f"{type(error).__name__}: {error}"
            job.updated_at = self.now()
            self._persist(job)
            return job

    def _run(self, job_id: str, request: IngestRequest) -> IngestJob:
        job = self.status(job_id)
        if job is None:
            raise RuntimeError("ingest job disappeared before it started")
        source = self.resolve_source(request.source_name)
        job.probe = probe_video(source)
        job.status = "running"
        self._persist(job)

        workspace = Path(tempfile.mkdtemp(prefix="zoovision-ingest-"))
        try:
            pieces = segment_video(
                source,
                workspace,
                segment_seconds=request.segment_seconds,
                max_segments=request.max_segments,
            )
            job.total_segments = len(pieces)
            self._persist(job)
            for index, offset, duration, piece in pieces:
                result = self._process_segment(request, index, offset, duration, piece, source)
                job.segments.append(result)
                job.completed_segments += 1
                job.detection_count += result.detection_count
                job.event_ids.extend(result.event_ids)
                job.rules_fired.extend(result.rules_fired)
                if result.data_gap_id:
                    job.data_gap_ids.append(result.data_gap_id)
                job.updated_at = self.now()
                self._persist(job)
            job.status = "complete"
            job.updated_at = self.now()
            self._persist(job)
            return job
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _process_segment(
        self,
        request: IngestRequest,
        index: int,
        offset: float,
        duration: float,
        piece: Path,
        source: Path,
    ) -> IngestSegmentResult:
        chunk_id = stable_id("chk", request.source_name, request.animal_id, index)
        start_ts = request.start_ts + timedelta(seconds=offset)
        detections = detections_for_chunk(
            piece,
            chunk_id=chunk_id,
            config=self.detector_config,
        )
        analyzer = self._analyzer_for(detections, request)
        # Motion regions are measured on the full-resolution segment; only the
        # copy offered to the provider is shrunk to fit its payload ceiling.
        analyzable = _provider_ready(piece)
        workflow = SegmentWorkflow(
            analyzer=analyzer,
            store=self.store,
            graph_writer=self.graph_writer,
            archive=self.archive,
            embedder=self.embedder,
            evidence_enricher=self.evidence_enricher,
            escalation_scheduler=self.escalation_scheduler,
            alert_ack_minutes=self.alert_ack_minutes,
            now=self.now,
        )
        outcome = workflow.run(
            SegmentWorkflowInput(
                chunk=VideoChunkContext(
                    chunk_id=chunk_id,
                    animal_id=request.animal_id,
                    enclosure_id=request.enclosure_id,
                    start_ts=start_ts,
                    end_ts=start_ts + timedelta(seconds=duration),
                ),
                animal_name=request.animal_name,
                species=request.species,
                camera_id=request.camera_id,
                source_path=f"uploads/{request.source_name}",
                content_sha256=_file_fingerprint(source),
                source_offset_seconds=offset,
                local_video_path=analyzable,
                archive_video_path=piece,
                shift_mode=request.shift_mode,
                baseline_state=_baseline_state(self.store, request.animal_id),
                fixture_mode=self.fixture_mode,
                delivery_enabled=self.delivery_enabled,
                webhook_configured=self.webhook_configured,
            )
        )
        # Detections are saved after the workflow, because the chunk row they
        # reference is created during its ingest node.
        self.store.save_detections(detections)
        return IngestSegmentResult(
            index=index,
            chunk_id=chunk_id,
            start_ts=start_ts,
            duration_seconds=duration,
            route=outcome.route,
            observation_count=outcome.observation_count,
            detection_count=len(detections),
            event_ids=outcome.event_ids,
            rules_fired=outcome.rules_fired,
            data_gap_id=outcome.data_gap_id,
        )

    def _analyzer_for(self, detections: list[Detection], request: IngestRequest) -> Any:
        motion = MotionEvidenceAnalyzer(
            [
                detection
                for detection in detections
                if detection.source is DetectionSource.MOTION_REGION
            ],
            sample_fps=self.detector_config.sample_fps,
        )
        if not request.use_provider or self.analyzer_factory is None:
            return motion
        return CompositeAnalyzer(primary=self.analyzer_factory(), motion=motion)

    def _persist(self, job: IngestJob) -> None:
        with self._lock:
            self.store.save_ingest_job(job.model_dump(mode="json"))


def _provider_ready(piece: Path) -> Path:
    """Return a copy of the segment small enough for the provider's payload cap.

    Long or high-bitrate footage exceeds the base64 ceiling, and an oversized
    request would be recorded as a data gap rather than analyzed. Transcoding a
    reduced proxy keeps real coverage. If the transcode fails, the original is
    returned and the provider's own limit check records the gap honestly.
    """
    if piece.stat().st_size <= PROVIDER_PAYLOAD_LIMIT_BYTES:
        return piece
    proxy = piece.with_name(f"{piece.stem}_proxy.mp4")
    completed = run_media_tool(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-i",
            str(piece),
            "-vf",
            "scale='min(640,iw)':-2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            "-an",
            str(proxy),
        ],
        timeout=600,
    )
    if completed.returncode == 0 and proxy.is_file() and proxy.stat().st_size > 0:
        return proxy
    return piece


def _baseline_state(store: SQLiteStore, animal_id: str) -> BaselineState:
    for row in store.dump_table("animals"):
        if row["animal_id"] == animal_id:
            return BaselineState(row["baseline_state"])
    return BaselineState.LEARNING


def _file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
