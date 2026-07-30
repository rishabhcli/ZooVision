# ZooVision

ZooVision is an evidence-backed overnight animal-welfare monitoring console for
zoo and sanctuary teams. It turns fixed-camera video into timestamped
observations, applies deterministic Python triage, preserves provenance, and
gives keepers a review and handoff workflow.

ZooVision is a welfare-support tool, not a medical device. It does not diagnose,
recommend medication, dispense treatment, manipulate an enclosure, or expose
actuator tools.

## Implemented status

The repository now contains a working fixture-mode product:

- strict observation, detection, baseline, event, alert, outcome, and data-gap
  domain types;
- daytime-only per-animal baselines with learning, shadow, active, and paused states;
- first-match deterministic triage with stable event IDs and `rule_fired`;
- cross-chunk observation stitching and wall-clock timestamp provenance;
- a deterministic motion-region detector that localizes movement as normalized,
  track-linked bounding boxes with no model weights and no network call;
- an ingest path that accepts an arbitrary uploaded video, probes it, segments
  it, and routes every segment through the same deterministic triage;
- idempotent SQLite persistence and static, idempotent Neo4j `MERGE` writers;
- a pinned Strands graph for bounded ingest, data-gap, day, night, triage, and
  indexing routes with a per-node audit trail;
- a keeper workspace with an interactive knowledge graph, a camera feed that
  overlays measured motion boxes and an event timeline, an analysis pane, an
  ingest console, and a grounded chat rail;
- checksum-pinned, freely licensed fixed-camera video fixtures;
- schema-constrained TwelveLabs and OpenAI adapters behind opt-in gates;
- explicit Slack delivery gates and configurable retention enforcement;
- production static serving and CI.

Fixture observations are synthetic scenarios, visibly labeled in the UI. The
footage is real, freely licensed evaluation media, but it is not labeled behavior
ground truth. No production behavior-recognition accuracy claim is made.

## Quick start

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), Node 26, npm, and
FFmpeg 8.

```bash
cp .env.example .env
uv sync --frozen --dev
npm --prefix frontend ci
uv run python scripts/prepare_fixture_videos.py
npm --prefix frontend run build
uv run uvicorn zoovision.api:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The fixture preparation
creates one 30-minute infrared badger feed and two 15-minute fixed-camera feeds
under ignored `data/raw/fixtures/`.

For frontend development, run the API on port 8000 and:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Video sources

| Fixture | Original | License | Prepared duration |
| --- | --- | --- | --- |
| European badger infrared garden camera | Wikimedia Commons | CC BY-SA 4.0 | 30 minutes |
| Powerextra outdoor trail-camera test | Wikimedia Commons | CC BY 3.0 | 15 minutes |
| California condor nest camera | Wikimedia Commons | Public domain | 15 minutes |

Exact source pages, creators, download URLs, byte sizes, SHA-256 checksums, and
timeline notes are in [`fixtures/video_sources.json`](fixtures/video_sources.json).
The badger container advertises roughly 5h15m because its first packet starts near
that timestamp; it contains about 30 seconds of actual footage. The preparation
script normalizes timestamps and repeats each source to make long evaluation
feeds. It never represents them as continuous original recordings.

## Architecture

```text
camera chunk
  -> strict provider response validation
  -> motion-region measurement (bounding boxes)
  -> wall-clock observation normalization
  -> cross-chunk stitching
  -> daytime baseline lookup
  -> deterministic first-match triage
  -> idempotent SQLite / Neo4j write
  -> shadow record or gated night alert
  -> acknowledgement, keeper outcome, morning brief
```

### What each layer may claim

Three sources of evidence are kept separate and are labeled separately in the
console, because they support different claims:

| Source | Produces | May claim | May not claim |
| --- | --- | --- | --- |
| Motion-region detector (MOG2) | normalized boxes, tracks | *where* pixels changed | species, identity, behavior |
| TwelveLabs Pegasus | timestamped behavior observations | *what a model read in the scene* | severity, diagnosis |
| Triage rules | severity, `rule_fired`, action | *what policy says about the evidence* | anything not in the evidence |

The detector needs no model weights, no network call, and no license beyond
OpenCV's, and it returns the same boxes for the same frames on every run. It is
suited to the product's actual deployment: fixed cameras and infrared night
footage, where a learned background separates a moving body cleanly. It is not
an animal classifier, and the console labels its output "motion regions"
everywhere it appears.

## Analyzing any video

Upload footage in the console's **Ingest** tab, or drive the same path over HTTP:

```bash
curl -F file=@night-footage.mp4 http://127.0.0.1:8000/api/ingest/upload
curl -X POST http://127.0.0.1:8000/api/ingest/jobs \
  -H 'content-type: application/json' \
  -d '{"source_name":"night-footage.mp4","animal_id":"animal-nox",
       "animal_name":"Nox","enclosure_id":"ENC-07","shift_mode":"night"}'
```

The job probes the container with ffprobe, splits it with ffmpeg's segment
muxer, re-probes each piece so wall-clock placement uses true durations rather
than the nominal segment length, measures motion regions, asks the configured
video provider for behavior semantics, and routes every segment through the same
deterministic triage as fixture footage. Segments larger than the provider's
base64 ceiling are transcoded to a reduced proxy so coverage is analyzed instead
of being written off as a gap. Poll `GET /api/ingest/jobs/{job_id}` for progress.

Only night segments can raise an event. Day segments refine context. A provider
failure becomes a recorded `DataGap`, and the motion track survives it.

Models may extract, normalize, merge, or phrase facts. They cannot assign or
override severity. A provider failure or invalid schema becomes a `DataGap`.
Only night events can page, and delivery additionally requires an active
human-reviewed baseline, a configured webhook, and
`ZOOVISION_ALERT_DELIVERY_ENABLED=true`. Fixture mode always blocks delivery.

The implemented triage order is:

| Rule | Signal | Severity |
| --- | --- | --- |
| `R001_FIGHTING` | Fighting | `CRITICAL` |
| `R002_ESCAPE_ATTEMPT` | Escape attempt | `CRITICAL` |
| `R003_VOMITING` | Vomiting | `HIGH` |
| `R004_PACING_20M_NO_WATER_6H` | Pacing >20m and no water contact >=6h | `HIGH` |
| `R005_PACING_10M` | Pacing >10m | `MODERATE` |
| `R006_INACTIVITY_2SD` | Inactivity z-score >2 | `MODERATE` |
| `R007_BASELINE_DELTA_2_5` | Baseline delta z-score >2.5 | `MODERATE` |
| `R008_WATER_BOWL_TIPPED` | Water bowl tipped | `LOW` |

## Integrations

The local `.env` is ignored. Keep all credentials there and commit only sanitized
examples.

- **OpenAI:** `gpt-5.6-luna` phrases evidence and `gpt-5.6-terra` phrases reports
  through strict Pydantic Structured Outputs. `store=false` is used. Both paths
  are non-authoritative and opt-in.
- **TwelveLabs:** Pegasus 1.5 accepts a direct public raw-media URL and returns a
  strict relative-timestamp schema. Live use is opt-in and should remain in
  shadow mode until measured against labeled animal footage.
- **AWS:** raw chunks, analysis JSON, and evidence clips use separate private S3
  buckets with 7, 30, and 90 day lifecycle policies. Marengo 3.0 is the Bedrock
  embedding model with response-derived vector dimensions. Synchronous text
  embedding and S3 archival are live-proven; the implemented asynchronous S3
  video job remains opt-in until its cross-account execution role is verified.
  Pegasus 1.5 remains on the direct TwelveLabs API.
- **Neo4j:** application-owned writes use static `MERGE` queries. Read access has
  separate credential fields and no arbitrary Cypher endpoint exists. If an
  Aura tier cannot create a dedicated reader, keep agent graph access disabled
  rather than reusing the writer identity.
- **Slack:** fixture mode, day shift, shadow/learning baselines, missing rules,
  disabled delivery, or a missing webhook each block the send.
- **Neo4j Visualization Library:** the console renders the knowledge graph with
  `@neo4j-nvl/react`. NVL is proprietary: its licence permits use only with
  Neo4j Aura or a commercial Neo4j product, which is how this project is
  configured. A deployment that drops Aura must also drop NVL. NVL declares
  `@segment/analytics-next` as a dependency; it is tree-shaken out of the
  production bundle, and the built assets contain no telemetry endpoint. Its
  vulnerable transitive `js-cookie` is pinned forward by an `overrides` entry in
  `frontend/package.json`.

The graph the console draws is projected from SQLite, so it renders whether or
not Aura is reachable. Neo4j remains the system of record for application-owned
graph writes, and both are keyed by the same stable identifiers.

Probe non-mutating integrations without printing secrets:

```bash
uv run python scripts/probe_integrations.py
```

The probe lists OpenAI model visibility and verifies Neo4j connectivity. It does
not probe TwelveLabs without a media request or Slack by sending a message.

Provision the three configured AWS buckets and their retention policies:

```bash
uv run python scripts/provision_aws.py
```

The operation is idempotent, blocks all public access, and uses S3-managed
encryption so it does not create a billable customer-managed KMS key.

Run the explicit, billable Bedrock Marengo text-embedding smoke test separately:

```bash
uv run python scripts/probe_bedrock.py
```

`AWS_BEDROCK_PROFILE` can select a workshop account locally when an organization
policy blocks Bedrock in the storage account. Explicit
`AWS_BEDROCK_*ACCESS_KEY*` temporary credentials take precedence when supplied.
On AWS compute, leave both mechanisms unset and use the runtime's attached role.

Initialize Aura constraints, create the clip vector index with the dimension
measured by the provider probe, and sync fixture evidence twice to verify
idempotency:

```bash
uv run python scripts/provision_neo4j.py --vector-dimension 512
```

The example dimension above is the value measured in the configured account;
do not reuse it for another model without probing that model's response first.

Run one raw chunk through the bounded Strands execution graph with an explicit
timezone-aware start and shift:

```bash
uv run python scripts/run_segment.py \
  --source data/raw/fixtures/badger-provider-probe-30s.mp4 \
  --animal-id animal-nox --animal-name Nox \
  --species "European badger" --enclosure-id ENC-07 --camera-id CAM-07A \
  --start 2026-07-30T02:00:00-07:00 --duration-seconds 30 --shift night
```

The command accepts only existing files below the configured raw-video root,
uses the schema-constrained provider adapter, and routes failures to a persisted
`DataGap`. Fixture mode keeps all alert delivery in shadow.

## Operations

Retention defaults are configurable: raw chunks 7 days, analysis JSON 30 days,
and evidence clips 90 days.

```bash
uv run python scripts/enforce_retention.py
uv run python scripts/enforce_retention.py --apply
```

The first command is a dry run. The second deletes only expired files below the
configured raw, analysis, and clips directories.

## Verification

```bash
uv run ruff check backend scripts
uv run ruff format --check backend scripts
uv run pytest --cov=zoovision --cov-fail-under=90
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
```

Live provider checks are separate from deterministic tests. Before real paging,
collect labeled footage, measure timestamp and behavior precision/recall, review
false negatives with animal-care staff, run an approved shadow period, verify
production retention and access controls, and activate each baseline manually.

The original architecture brief remains available in
[`compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md`](compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md).
