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
- fast local YOLOv8n animal-object candidates plus a separate deterministic
  motion-region fallback, both as normalized track-linked bounding boxes;
- an ingest path that accepts an arbitrary uploaded video, probes it, segments
  it, and routes every segment through the same deterministic triage;
- idempotent SQLite persistence and static, idempotent Neo4j `MERGE` writers;
- a pinned Strands graph for bounded ingest, data-gap, day, night, triage, and
  indexing routes with a per-node audit trail;
- a keeper workspace with an interactive knowledge graph, a playable camera
  feed with labeled object boxes and an event timeline, an analysis pane, an
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
npm ci
npm --prefix frontend ci
uv run python scripts/prepare_fixture_videos.py
npm run build
npm --prefix frontend run build
uv run uvicorn zoovision.api:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The fixture preparation
creates a 30-minute African lion feed plus 15-minute African elephant and
mountain gorilla feeds under ignored `data/raw/fixtures/`.

For frontend development, run the API on port 8000 and:

```bash
npm run dev:all
```

This starts the API and imported monitoring workspace together, selects free
ports automatically, and prints the URL to open. Press Ctrl+C once to stop both.

To run the two processes separately:

```bash
ZOOVISION_API_ORIGIN=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1
```

Then open [http://localhost:3000](http://localhost:3000). The imported
monitoring workspace proxies `/api` and `/media` to FastAPI so graph, video,
analysis, readiness, and grounded chat use backend records.

The original Vite console remains available for development with:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Video sources

| Fixture | Original | License | Prepared duration |
| --- | --- | --- | --- |
| African lion in Kruger National Park | Wikimedia Commons | CC BY-SA 2.0 | 30 minutes |
| African elephants in Mana Pools National Park | Wikimedia Commons | CC BY 3.0 | 15 minutes |
| Mountain gorilla in Volcanoes National Park | Wikimedia Commons | CC BY 3.0 | 15 minutes |

Exact source pages, creators, download URLs, byte sizes, SHA-256 checksums, and
timeline notes are in [`fixtures/video_sources.json`](fixtures/video_sources.json).
The preparation script normalizes timestamps and repeats each source to make
long evaluation feeds. It never represents them as continuous original
recordings.

## Architecture

```text
camera chunk
  -> strict provider response validation
  -> YOLOv8n object candidates + motion-region measurement
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
| YOLOv8n | normalized boxes, tracks, COCO class candidates | *where a candidate animal object appears* | identity, behavior, severity, diagnosis |
| Motion-region detector (MOG2) | normalized boxes, tracks | *where* pixels changed | species, identity, behavior |
| TwelveLabs Pegasus | timestamped behavior observations | *what a model read in the scene* | severity, diagnosis |
| Triage rules | severity, `rule_fired`, action | *what policy says about the evidence* | anything not in the evidence |

YOLOv8n runs locally at two sampled frames per second, uses Apple MPS or CUDA
when available, and restricts inference to COCO animal classes. Its class text
is always displayed as a model candidate requiring human verification. MOG2
continues to provide deterministic motion evidence and is the only detection
source passed into the motion-evidence analyzer. Neither detector assigns
behavior, identity, severity, diagnosis, or treatment.

The first YOLO run downloads `yolov8n.pt`; the weight file is ignored by Git.
Ultralytics publishes its code and trained models under AGPL-3.0 and also offers
an enterprise license. Deployments must comply with one of those licensing
paths; see the [Ultralytics licensing documentation](https://www.ultralytics.com/license).

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
than the nominal segment length, localizes YOLOv8 object candidates and motion
regions, asks the configured video provider for behavior semantics, and routes
every segment through the same
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
- **Ultralytics YOLOv8:** `yolov8n.pt` runs locally for fast animal-object
  candidates. `ZOOVISION_YOLO_*` settings control device, sampling, confidence,
  image size, and batching. These boxes are non-authoritative and never enter
  deterministic triage.
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
  separate credential fields and no arbitrary Cypher endpoint exists.
  `/api/graph` uses a fixed, read-only ontology query against Neo4j and returns
  `503` if Neo4j is unconfigured or unavailable; it never substitutes SQLite
  graph data. Fixture mode may read the configured graph but does not enable
  graph writes.
- **Slack:** fixture mode, day shift, shadow/learning baselines, missing rules,
  disabled delivery, or a missing webhook each block the send.
- **Neo4j Visualization Library:** the console renders the knowledge graph with
  `@neo4j-nvl/react`, following the live Neo4j graph pattern from
  [`jpadams/video-context-graph`](https://github.com/jpadams/video-context-graph).
  ZooVision keeps that project's NVL force-layout approach but uses a fixed,
  read-only welfare-ontology query instead of exposing arbitrary Cypher. NVL is
  proprietary: its licence permits use only with Neo4j Aura or a commercial
  Neo4j product, which is how this project is configured. A deployment that
  drops Aura must also drop NVL. NVL declares `@segment/analytics-next` as a
  dependency; telemetry is disabled in the renderer configuration.

Both graph consoles read `/api/graph`, whose payload is sourced directly from
Neo4j. Event writes also persist `Camera` and `Clip` context with static,
idempotent `MERGE` operations.

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
  --source data/raw/fixtures/lion-provider-probe-30s.mp4 \
  --animal-id animal-nox --animal-name Nox \
  --species "African lion" --enclosure-id ENC-07 --camera-id CAM-07A \
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
npm run lint
npm run build
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=high
```

Live provider checks are separate from deterministic tests. Before real paging,
collect labeled footage, measure timestamp and behavior precision/recall, review
false negatives with animal-care staff, run an approved shadow period, verify
production retention and access controls, and activate each baseline manually.

When `ZOOVISION_ENV=production`, startup fails unless fixture mode is disabled
and TwelveLabs, OpenAI, Neo4j writes, and S3 archival are configured. Production
ingest cannot disable the video provider, OpenAI chat does not fall back to a
local response, and every validated provider observation is idempotently written
to Neo4j even when deterministic triage produces no welfare event. Alert
delivery remains separately gated by a configured webhook, explicit delivery
enablement, and an active human-reviewed baseline.

## Production deployment

The production UI runs as a Sites worker and proxies `/api` and `/media` to the
Python service. Two separate credentials protect that path:

- `ZOOVISION_EDGE_AUTH_USERNAME` and `ZOOVISION_EDGE_AUTH_PASSWORD` challenge
  every browser request at the edge.
- `ZOOVISION_PROXY_SHARED_SECRET` is removed from incoming requests, injected by
  the worker, and required by FastAPI for every API and media request except the
  minimal health check.

Store these values as managed deployment secrets. Do not put them in Git or DNS.
The same proxy secret must be configured in Sites and in the API service.

The backend deployment package is in [`deploy/`](deploy/). It runs FastAPI as a
non-root user, keeps SQLite, model weights, uploads, and derived media on a
persistent volume, and uses Caddy for automatic HTTPS. On the host:

```bash
cp deploy/.env.production.example deploy/.env.production
docker compose --project-directory deploy up -d --build
```

Set `ZOOVISION_API_HOST` to the API hostname, such as `api.example.com`, and
point that hostname's DNS record to the backend host before starting Caddy.
Configure Sites with:

```text
ZOOVISION_EDGE_AUTH_ENABLED=true
ZOOVISION_EDGE_AUTH_USERNAME=<managed value>
ZOOVISION_EDGE_AUTH_PASSWORD=<managed secret>
ZOOVISION_PROXY_SHARED_SECRET=<same managed secret as the API>
ZOOVISION_API_ORIGIN=https://api.example.com
```

The staff-facing site hostname, such as `app.example.com`, is attached to Sites.
The backend hostname is not intended for browser use: direct API and media
requests are rejected without the proxy credential. Production API docs are
disabled.

The original architecture brief remains available in
[`compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md`](compass_artifact_wf-8953096d-23a5-5284-a231-458dcee08d71_text_markdown.md).
