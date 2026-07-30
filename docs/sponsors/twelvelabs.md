# TwelveLabs — ZooVision Sponsor Reference

> **Researched:** 2026-07-30 · **Verification status:** High. ~30 live fetches against `docs.twelvelabs.io`, `twelvelabs.io`, `docs.aws.amazon.com/bedrock`, PyPI, GitHub and press releases. Both headline models (Marengo 3.0, Pegasus 1.5) **exist as documented**. 13 of 17 brief claims confirmed, 3 wrong, 1 unverifiable. Three architecture-breaking discoveries: **video-to-video search does not exist**, **Pegasus 1.5 is not on Bedrock**, and **segmentation billing multiplies by segment-definition count**.
> **Role in ZooVision:** Load-bearing perception layer — Pegasus 1.5 turns each ~15-min enclosure segment into schema-constrained timestamped behavior observations; Marengo 3.0 produces 512-dim embeddings for per-animal clip retrieval. Nothing downstream (triage, graph, alerts, briefing) works without it.

---

## 1. Snapshot

| Dimension | Reality (verified 2026-07-30) |
|---|---|
| **What it is** | Video-native foundation-model platform. Two model families + an agent layer. REST API at `https://api.twelvelabs.io/v1.3`, auth via `x-api-key` header. Official Python (`twelvelabs` 1.3.1) and Node SDKs. |
| **Current models** | **Marengo 3.0** (`marengo3.0`) — embeddings + search. **Pegasus 1.5** (`pegasus1.5`) — video→text, structured JSON, time-based-metadata segmentation. **Pegasus 1.2** (`pegasus1.2`) — legacy, still the API *default*, general analysis only. **Jockey 1.0** (`jockey1.0`) — agent layer, research preview. Marengo 2.7 is **sunset** (dead since 2026-03-30). |
| **How ZooVision uses it** | (a) `POST /analyze/tasks` with `model_name=pegasus1.5`, `analysis_mode=time_based_metadata`, `response_format.type=segment_definitions` → timestamped behavior segments per chunk. (b) `POST /embed/v2/tasks` with `marengo3.0` → 512-dim clip embeddings → Neo4j vector index. (c) Similarity retrieval done **in Neo4j**, not via `/search`. |
| **Key limit** | Pegasus: **4 s – 2 h**, ≤ 2 GB, 360×360 min, 261,120-token context. Free plan: **600 min (10 h) cumulative, lifetime, never resets** — shared across indexing + analysis + segmentation. Index expires 90 days on Free. |
| **Biggest risk** | **Zero documented non-human-animal capability** anywhere in TwelveLabs docs, blog, case studies, benchmarks, or GitHub. Every published eval is news / film&TV / sports / speech. Behavior-recognition quality on a nocturnal snow leopard is completely unknown until you test it. Compounding risk: segmentation cost = `duration × n_segment_definitions`, so a 3-definition schema on one 12-h night on one camera = 2,160 billable minutes ≈ 3.6× the entire Free-plan lifetime quota. |

---

## 2. Current product & model lineup (as of July 2026)

### 2.1 Marengo 3.0 — embeddings & search
Source: [Marengo model concept page](https://docs.twelvelabs.io/docs/concepts/models/marengo), [Bedrock Marengo 3.0 page](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html), [Marengo 3.0 blog](https://www.twelvelabs.io/blog/marengo-3-0)

| Property | Value (documented) |
|---|---|
| Model string | `marengo3.0` |
| Embedding dimension | **512** ("512-dimensional embeddings for faster processing and reduced storage"). Bedrock docs state explicitly: "Reduced from 1024 to 512". |
| Video duration | 4 sec – **4 hours** |
| Audio duration | up to 4 hours |
| File size | ≤ 4 GB (direct API); ≤ 6 GB via Bedrock S3 |
| Resolution | 360×360 to 5184×2160 |
| Aspect ratio | between 1:1 and 1:2.4, or between 2.4:1 and 1:1 |
| Text input | max 500 tokens |
| Image | JPEG/PNG, min 128×128, max 32 MB |
| Audio formats | WAV (uncompressed), MP3, FLAC |
| Languages | **36 languages plus English** |
| Modalities (`embedding_option`) | `visual`, `audio`, `transcription` — plus `fused` returned when `embedding_type` includes `fused_embedding` |
| Embedding scope | `clip` (per segment) and/or `asset` (whole file). Default: both. |
| Segmentation | `dynamic` (shot-boundary, `min_duration_sec` 1–5, default 4) or `fixed` (`duration_sec` 1–10, default 6) |
| Sync vs async | Sync for video/audio **< 10 minutes**; async for 10 min – 4 h |
| Benchmarks (vendor-published) | 70.2% composite general video retrieval (14 benchmarks); 73.2% audio; 92.2% image; 88.3% text. MSRVTT 72.5% (vs Vertex 59.5%, Nova 69.6%). SoccerNet-Action 79.4 mAP. Latency ~0.05 s per second of video (~310 s for a 1-hour video). |

### 2.2 Pegasus 1.5 — video→text, structured output, segmentation
Source: [Pegasus model concept page](https://docs.twelvelabs.io/docs/concepts/models/pegasus), [async task API ref](https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task), [segment guide](https://docs.twelvelabs.io/docs/guides/segment-videos)

| Property | Value (documented) |
|---|---|
| Model string | `pegasus1.5` |
| Context window | **261,120 tokens for input and output per request** |
| Max response | **98,304 tokens** (raised from 65,536 on 2026-05-28) |
| Video duration | **4 sec – 2 hours** (sync `/analyze` caps at 1 hour) |
| File size | ≤ 2 GB |
| Resolution | 360×360 to 5184×2160 |
| Aspect ratio | between 1:1 and 1:2.4, or between 2.4:1 and 1:1 |
| Formats | any FFmpeg-supported container |
| Capabilities | video→text general analysis; **video segmentation with custom segment definitions**; multimodal prompting with **up to 4 reference images**; **video clipping** (`start_time`/`end_time`, min 4 s clip) |
| Structured output | `response_format.type = "json_schema"` (general) or `"segment_definitions"` (segmentation) |
| Indexing | **NOT required.** Accepts `url`, `asset_id`, or `base64_string` directly. `pegasus1.5` is **not** a valid `model_name` for `POST /indexes`. |
| Languages | Full: English. Partial: Arabic, Chinese, French, German, Italian, Japanese, Korean, Portuguese, Russian, Spanish, Thai, Vietnamese |
| Benchmark (vendor) | Aggregate segmentation quality 0.4279 vs Gemini 3.1 Pro 0.3370. Multimodal prompting 0.4555 vs 0.3243. Press release: "outperforms Gemini 3.1 Pro on aggregated segmentation by 13.1%", "boundary accuracy within approximately 350 milliseconds". |

### 2.3 Pegasus 1.2 — legacy
Still the **API default** when `model_name` is omitted. Docs: "Pegasus 1.2 remains available for general analysis only." 2,000-token prompt limit, 4,096-token max response. No segmentation, no `prompt_v2`, no clipping. **No EOL date published.** This is the only Pegasus available on Bedrock and inside indexes.

### 2.4 Jockey 1.0 — agent layer (research preview, launched 2026-07-15)
Source: [twelvelabs.io/jockey](https://www.twelvelabs.io/jockey), [MCP docs](https://docs.twelvelabs.io/docs/advanced/model-context-protocol), [intro page](https://docs.twelvelabs.io/docs/get-started/introduction)

"A unified agentic system that reasons across your videos and images. Ask it a question, and it plans its own steps, then answers with grounded, cited moments." Combines Pegasus (extraction) + Marengo (retrieval) + a planner. Concepts: **knowledge stores**, configurable ingestion, corpus digest, entity resolution, agentic search, structured references, **Responses API**.

- MCP endpoint: `https://mcp.twelvelabs.io/jockey/mcp` (OAuth, remote HTTP transport)
- SDK shape (third-party-reported, see §8): `client.responses.create(model="jockey1.0", knowledge_store_id=..., session_id=..., input=[ResponseInputItem(...)])`
- Docs describe the split as: "Use Models for embeddings and per-video analysis, and Agents for corpus-level reasoning."
- Jockey standalone pricing (from the Jockey page, distinct from API pricing): Free 5 GB storage; Plus $20/mo 100 GB; Pro $100/mo 500 GB.
- **The brief did not mention Jockey at all.** For a hackathon literally named "Hack the Video Agent Context", this is the single most scoring-relevant thing TwelveLabs shipped this quarter.

### 2.5 Entity search
Source: [entity search guide](https://docs.twelvelabs.io/docs/guides/search/entity-search)

Create an entity collection, register named entities with reference images, then query with `<@entity_id>` inline syntax (e.g. `"<@entity123> is walking"`). Free plan: **1 entity collection, up to 15 entities** (the default sample collection counts).

⚠️ **Documented for people only.** "Entities: Represent the specific people you want to find in videos." Guidance: "Choose clear, high-quality images that show each person's face clearly." Animals are never mentioned. Whether a lion/leopard reference image works is **untested and undocumented** — see §10.

---

## 3. Release timeline / what's new

All from [docs.twelvelabs.io/docs/get-started/release-notes](https://docs.twelvelabs.io/docs/get-started/release-notes) unless noted.

| Date | Change | ZooVision relevance |
|---|---|---|
| 2025-12-01 | **Marengo 3.0 GA** at AWS re:Invent, simultaneously on TwelveLabs + Amazon Bedrock. 4-h video (2× 2.7), 512-dim embeddings, −50% storage, 2× faster indexing, 12→36 languages. ([AWS press release](https://press.aboutamazon.com/aws/2025/12/twelvelabs-launches-its-most-powerful-video-understanding-model-marengo-3-0-on-twelvelabs-and-amazon-bedrock)) | Confirms the embedding model + dimension |
| 2026-01-26 | Custom API-key expiration: 3/6/12 months, custom date, or never. Default 12 months. | Set "never" for the demo key |
| 2026-02-15 | **`/gist` and `/summarize` endpoints removed.** Migrate to `/analyze`. | Any old sample code using these is dead |
| 2026-02-28 | Marengo 2.7 deprecation notice | — |
| 2026-03-11 | Multi-image search (up to 10 images/request); Embed API **v2**; **fused embeddings** | v2 is the current embed API |
| ~mid-March 2026 | Platform **auto-reindexed** existing videos to Marengo 3.0 | — |
| 2026-03-30 | **Marengo 2.7 sunset (7 PM PT).** Verbatim: "You no longer can index new content, perform search requests, or retrieve any embeddings from previously indexed content." | Any 1024-dim 2.7 embeddings are unrecoverable |
| 2026-03-31 | Async analysis endpoints — videos up to **2 hours** (was 1-h sync limit) | The endpoint ZooVision uses |
| 2026-04-08 | Deletion safeguards announced (effective 2026-04-26): deleting a referenced asset returns **409 Conflict** unless `force=true` | Cleanup scripts need `force=true` |
| 2026-04-15 | Asset HLS streaming + thumbnails; new fields `size`, `duration`, `method`; filename filtering | `enable_hls` / `enable_thumbnail` for evidence clips |
| 2026-04-20 | **Pegasus 1.5 GA** with video segmentation. Breaking: `ResponseFormat` split into `SyncResponseFormat` / `AsyncResponseFormat`. | The core ZooVision dependency |
| 2026-04-24 | `custom_id` on async analysis tasks (1–64 chars, alnum/hyphen/underscore) | Correlate task → camera+chunk |
| 2026-04-27 | Pegasus 1.5 general analysis + `prompt_v2` reference images (≤4) + **video clipping** (`start_time`/`end_time`, ≥4 s) + per-definition `time_ranges` | Clip-scoped re-analysis for alert evidence |
| 2026-05-06 | Pegasus 1.5 on the **synchronous** `/analyze` endpoint | Fast path for <1 h |
| 2026-05-07 | **Free plan: single 10-hour limit shared across indexing and video analysis.** Verbatim: "Previously, only indexing hours counted toward this limit." Also: **paid segmentation cost now factors in segment-definition count.** | Both are budget-critical |
| 2026-05-22 | `user_metadata` at upload time; **timestamp formatting** `seconds` / `hh:mm:ss` / `hh:mm:ss.fff` | Per-animal metadata at ingest |
| 2026-05-28 | Pegasus 1.5 context window **261,120** tokens; max response **98,304** (was 65,536); new `usage.input_tokens` | Confirms brief claim 3 |
| 2026-06-02 | SDKs support metadata-on-upload + timestamp formatting | Need SDK ≥ this release |
| 2026-06-04 | `PUT /assets/{asset_id}/user-metadata` (full replace) alongside existing PATCH (merge) | — |
| 2026-06-05 | `error` object with human-readable reason on embedding-task failures | Better failure handling |
| 2026-06-18 | **Batch analysis:** up to **1,000** analysis requests in one call; **requires Pegasus 1.5** | Submit a whole night in one call |
| 2026-07-01 | TwelveLabs raises **$100M Series B** ([GlobeNewswire](https://www.globenewswire.com/news-release/2026/07/01/3320545/0/en/TwelveLabs-Raises-100-Million-in-Series-B-Funding-to-Build-Video-Superintelligence.html)) | Sponsor context / demo-day framing |
| 2026-07-07 | **All uploads now async.** Every asset returns `status: processing`; you must poll until `ready`. Invalid files now fail *asynchronously*. New `technical_metadata` object. Multipart → 10 GB, images → 32 MB. | **Pipeline-breaking if you assumed synchronous upload validation** |
| 2026-07-15 | **Jockey research preview** | Hackathon-theme goldmine |
| 2026-07-20 | **Google Drive data connector** | Alternative ingest path |
| 2026-07-22 | Multipart audio → 10 GB; images → 32 MB | — |
| 2026-07-23 | Python SDK **1.3.1** on PyPI ([PyPI](https://pypi.org/project/twelvelabs/)) | Pin this |
| 2026-07-30 | **TwelveLabs Claude Code plugin** announced ([blog](https://www.twelvelabs.io/blog/claude-code-plugin)) — index / search / analyze / embed / entity search under a `twelvelabs:` slash-command namespace | Same-day; great demo garnish |

**No Marengo 3.1 and no Pegasus 2 exist.** Searched for both explicitly; nothing found.

---

## 4. APIs & SDK surface ZooVision calls

### 4.0 Basics
- Base URL: `https://api.twelvelabs.io` · version segment `v1.3` → `https://api.twelvelabs.io/v1.3`
- Auth: header `x-api-key: <YOUR_API_KEY>`
- URL pattern: `{Method} {BaseURL}/{version}/{resource}/{path_parameters}`
- Python SDK: `pip install twelvelabs` → **1.3.1** (2026-07-23), requires Python `>=3.8,<4.0`
- Docs trick: append `.md` to any docs URL for raw markdown; append `/llms.txt` to a section for its index; docs MCP server at `https://docs.twelvelabs.io/_mcp/server`

### 4.1 Upload — `POST /assets`
Source: [create asset](https://docs.twelvelabs.io/api-reference/upload-content/direct-uploads/create), [upload methods](https://docs.twelvelabs.io/docs/concepts/upload-methods)

`POST https://api.twelvelabs.io/v1.3/assets` · `multipart/form-data`

| Param | Type | Notes |
|---|---|---|
| `method` | string, **required** | `direct` (local file) or `url` (public URL) |
| `file` | binary | required when `method=direct`. ≤ **200 MB** video/audio, ≤ 32 MB images |
| `url` | string | required when `method=url`. ≤ **4 GB** video/audio, ≤ 32 MB images |
| `filename` | string | optional |
| `enable_hls` | boolean | default `false` — generates HLS playlist |
| `enable_thumbnail` | boolean | default `false` |
| `user_metadata` | string | **JSON-encoded**; values limited to string / integer / float / boolean |

Response `201`:
```json
{ "_id": "...", "method": "direct|url|multipart",
  "status": "processing|ready|failed",
  "filename": "...", "file_type": "...",
  "created_at": "2022-06-02T10:30:00Z", "user_metadata": {} }
```

**Mandatory polling** (verbatim): *"Poll the Retrieve an asset endpoint until the status of the asset is `ready` before you use it. This applies to every upload, including small files."*

Size ceilings by path:

| Path | Video/Audio | Images |
|---|---|---|
| Direct, local file | 200 MB | 32 MB |
| Direct, public URL | 4 GB | 32 MB |
| **Multipart** (local) | **10 GB** | 32 MB |
| Google Drive connector | video 10 GB / audio 4 GB | 32 MB |
| Inline one-time URL | 4 GB | — |
| Inline base64 | 36 MB | 32 MB |

ZooVision's ~15-min 1080p MP4s land comfortably in the direct-local 200 MB lane, or use `method=url` against a presigned S3 URL (≤4 GB).

### 4.2 Async segmentation — `POST /analyze/tasks` (the ZooVision workhorse)
Source: [API ref](https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task), [segment guide](https://docs.twelvelabs.io/docs/guides/segment-videos)

`POST https://api.twelvelabs.io/v1.3/analyze/tasks` · `application/json` · returns `202`

| Param | Type | Default | Notes |
|---|---|---|---|
| `video` | object, **required** | — | `{type:"url"\|"asset_id"\|"base64_string", ...}` |
| `model_name` | string | **`pegasus1.2`** | `pegasus1.2` \| `pegasus1.5` — **always set this explicitly** |
| `analysis_mode` | string | `general` | `general` \| `time_based_metadata` |
| `response_format` | object | — | `json_schema` or `segment_definitions` |
| `prompt` | string | — | **not supported when `analysis_mode=time_based_metadata`** |
| `prompt_v2` | object | — | pegasus1.5 only; `{input_text, media_sources[]}`, ≤4 images |
| `temperature` | number | `0.2` | 0–1 |
| `max_tokens` | int | `4096` | p1.2: 2–4,096 · p1.5 general: 512–98,304 · time_based_metadata: **2,048–98,304** |
| `custom_id` | string | — | 1–64 alnum/hyphen/underscore |
| `start_time` / `end_time` | number | — | p1.5 only; clip ≥ 4 s |
| `min_segment_duration` | number | — | ≥ 2 s |
| `max_segment_duration` | number | — | ≥ 2 s |

Segmentation limits: **max 10 segment definitions per request**, **max 20 fields per definition**, **max 4 media sources per definition**. Field types: `string`, `boolean`, `number`, `integer`, `array` (plus `timestamp` in the API-ref schema, which requires a `format` of `seconds` \| `hh:mm:ss` \| `hh:mm:ss.fff`).

Response shape (verbatim from the segment guide):
```json
{
  "<segment_definition_id>": [
    { "start_time": 0.0, "end_time": 45.0,
      "metadata": { "<field_name>": "<value>" } }
  ]
}
```
Segments do not overlap within a definition. `start_time`/`end_time` are floating-point seconds (example given: `45.0`). Each definition ID becomes its own top-level key.

Runnable ZooVision call:

```python
import json, time
from twelvelabs import TwelveLabs
from twelvelabs.types import AsyncResponseFormat, VideoContext_AssetId

client = TwelveLabs(api_key="<YOUR_API_KEY>")

BEHAVIOR_DEF = {
    "id": "behavior_events",
    "description": (
        "Segment the enclosure footage into intervals of distinct animal "
        "behavior. Start a new segment whenever the animal's activity state "
        "changes or when it enters or leaves frame."
    ),
    "fields": [
        {"name": "behavior", "type": "string",
         "description": "Primary observed behavior",
         "enum": ["resting", "sleeping", "pacing", "feeding", "drinking",
                  "grooming", "locomotion", "vocalizing", "out_of_frame",
                  "abnormal_posture", "other"]},
        {"name": "animal_visible", "type": "boolean",
         "description": "True if any animal is visible in this segment"},
        {"name": "animal_count", "type": "integer",
         "description": "Number of distinct animals visible"},
        {"name": "posture", "type": "string",
         "description": "lying / sitting / standing / unknown"},
        {"name": "location_in_enclosure", "type": "string",
         "description": "Where in frame, e.g. den, water, feeding station"},
        {"name": "evidence", "type": "string",
         "description": "One sentence of literal visual evidence. No inference."},
        {"name": "confidence", "type": "number",
         "description": "0.0-1.0 confidence in the behavior label"},
    ],
}

task = client.analyze_async.tasks.create(
    video=VideoContext_AssetId(asset_id="<ASSET_ID>"),
    model_name="pegasus1.5",
    analysis_mode="time_based_metadata",
    response_format=AsyncResponseFormat(
        type="segment_definitions",
        segment_definitions=[BEHAVIOR_DEF],
        segment_time_format="seconds",
    ),
    min_segment_duration=5,
    max_tokens=8192,
    custom_id="cam-snowleopard-a-20260730T0215Z",  # camera + chunk correlation
)

while True:
    task = client.analyze_async.tasks.retrieve(task.task_id)
    if task.status in ("ready", "failed"):
        break
    time.sleep(5)

if task.status == "failed":
    raise RuntimeError(task.error)

segments = json.loads(task.result.data)["behavior_events"]
```

> **Cost note:** keep this to **ONE** segment definition. Every extra definition multiplies your billed minutes 1:1 (§6).

### 4.3 Sync analysis — `POST /analyze` (for alert-clip re-reads)
Source: [open-ended analysis](https://docs.twelvelabs.io/api-reference/analyze-videos/analyze), [structured responses](https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses)

`POST https://api.twelvelabs.io/v1.3/analyze` · videos **4 s – 1 hour**.

- `stream` defaults to **`true`** → NDJSON with `stream_start` / `text_generation` / `stream_end`. Set `stream=false` for a single JSON body.
- `video_id` is **deprecated** (pegasus1.2 pre-indexed only). Pegasus 1.5 has **removed** it.
- Only `response_format.type = "json_schema"` is valid here (no `segment_definitions` on the sync path).
- Non-streamed response: `{ id, data, finish_reason: "stop"|"length", usage: {output_tokens, input_tokens}, error? }`. **`data` is a JSON *string*** — `json.loads` it.

JSON-Schema support (verbatim from the structured-responses guide): types `array`, `boolean`, `integer`, `null`, `number`, `object`, `string`; keywords `pattern`, `minimum`, `maximum`, `required`, `minItems` (**accepts only 0 or 1**); composition **only `anyOf`**; refs via `$defs` + `$ref`. Docs state: *"The schema takes precedence over the prompt."* No documented schema size/nesting limit.

```python
import json
from twelvelabs import TwelveLabs
from twelvelabs.types import AnalyzePromptV2, SyncResponseFormat, VideoContext_AssetId

client = TwelveLabs(api_key="<YOUR_API_KEY>")

result = client.analyze(
    model_name="pegasus1.5",
    video=VideoContext_AssetId(asset_id="<CLIP_ASSET_ID>"),
    prompt_v_2=AnalyzePromptV2(
        input_text="Describe only what is literally visible. Do not speculate "
                   "about animal welfare, pain, or intent."
    ),
    response_format=SyncResponseFormat(
        type="json_schema",
        json_schema={
            "type": "object",
            "properties": {
                "observed_actions": {"type": "array", "items": {"type": "string"}},
                "posture": {"type": "string"},
                "notable_deviation": {"type": "string"},
            },
            "required": ["observed_actions", "posture"],
        },
    ),
    stream=False,
)
data = json.loads(result.data) if result.data else {}
```

Note the SDK kwarg is `prompt_v_2` (underscore before the 2), not `prompt_v2`.

### 4.4 Batch analysis — `POST /analyze/batches`
Source: [analyze-videos API ref](https://docs.twelvelabs.io/api-reference/analyze-videos), release note 2026-06-18

- Up to **1,000** analysis requests per call. **Requires Pegasus 1.5.**
- Returns a **single batch identifier** used to monitor progress and retrieve **per-item results**.
- SDK method: `client.analyze_async.batches.create(...)`; there is also a documented "Cancel a batch" operation.

⚠️ **UNVERIFIED:** exact request-body field names (`requests[]`?), the batch-retrieval path, and whether batches support `analysis_mode=time_based_metadata`. The dedicated API-ref page did not resolve at `/api-reference/analyze-videos/batch-analysis/create` or `/api-reference/analyze-videos/batches` (both 404); "Create a batch" / "Batch analysis" / "Cancel a batch" appear only as sibling links. **Read the live page before coding against it.**

### 4.5 Embeddings — Embed API **v2**
Source: [embeddings for new videos](https://docs.twelvelabs.io/docs/guides/create-embeddings/video/new)

```python
task = client.embed.v_2.tasks.create(          # async: 10 min – 4 h
    input_type="video",
    model_name="marengo3.0",
    video=VideoInputRequest(...),
)
task = client.embed.v_2.tasks.retrieve(task_id=task.id)

response = client.embed.v_2.create(            # sync: < 10 min
    input_type="video",
    model_name="marengo3.0",
    video=VideoInputRequest(...),
)
```

Returned objects in `data`: `embedding` (list of floats), `embedding_option` (`visual` | `audio` | `transcription` | `fused`), `embedding_scope` (`clip` | `asset`), `start_sec`, `end_sec`.

> **Field-name drift:** the old v1.3 Embed shape (`float_`, `start_offset_sec`, `end_offset_sec`) is gone. Use `embedding`, `start_sec`, `end_sec`. Anything you copy from a pre-2026 tutorial will KeyError.

For a 15-min segment: `embedding_option=["visual"]`, `embedding_scope=["clip"]`, dynamic segmentation with `min_duration_sec=4` yields ~one 512-float vector per shot — exactly the granularity for a Neo4j vector index (`vector.dimensions: 512`, `vector.similarity_function: cosine`).

### 4.6 Search & metadata filtering
Source: [make search request](https://docs.twelvelabs.io/api-reference/any-to-video-search/make-search-request), [filtering guide](https://docs.twelvelabs.io/docs/guides/search/filtering), [metadata](https://docs.twelvelabs.io/docs/advanced/metadata)

`POST https://api.twelvelabs.io/v1.3/search` · **`multipart/form-data`**

| Param | Notes |
|---|---|
| `index_id` | required |
| `search_options` | required array: `visual`, `audio`, `transcription` |
| `query_text` | ≤ 500 tokens |
| `query_media_type` | **`image` only** |
| `query_media_url` / `query_media_file` | up to **10** images |
| `transcription_options` | `lexical` \| `semantic` (default both) |
| `group_by` | `video` \| `clip` (default `clip`) |
| `operator` | `or` \| `and` (default `or`) |
| `page_limit` | max **50**, default 10 |
| `filter` | **stringified JSON** over system + user metadata |
| `include_user_metadata` | boolean |

Filter operators: exact match, plus `gte` / `lte`. Documented examples:
`{"id": ["67cec9caf45d9b64a58340fc"]}` · `{"duration": {"gte": 600, "lte": 800}}` · `{"filename": "Animal Encounters part 1"}`

```python
import json
results = client.search.query(
    index_id=index.id,
    query_text="animal pacing repeatedly along the same path",
    search_options=["visual"],
    filter=json.dumps({"animal_id": "snow-leopard-A7", "enclosure": "north-ridge"}),
    include_user_metadata=True,
)
```

Response: `data[]` with `start`, `end`, `video_id`, `rank`, `thumbnail_url` (**expires in 1 hour**), `transcription`, `user_metadata`, `clips[]`; plus `page_info` (`limit_per_page`, `total_results`, `next_page_token`) and `search_pool`.

**❗ There is no video query type.** Verbatim from the search section: *"Currently, the platform supports text and image queries."* See §9 claim 7-b and §8.

Setting `user_metadata` (values must be **string / integer / float / boolean** — *"If you want to store other types of data such as objects or arrays, you must convert your data into string values"*):

```python
# indexed video (documented, but see deprecation note below)
client.indexes.videos.update(
    index_id="<INDEX_ID>", video_id="<VIDEO_ID>",
    user_metadata={"animal_id": "snow-leopard-A7", "enclosure": "north-ridge",
                   "is_night": True, "chunk_start_epoch": 1785000000},
)
```

Metadata endpoint landscape (three generations coexisting):

| Endpoint | Method | Status |
|---|---|---|
| `/assets` (`user_metadata` form field) | POST | current — set at upload |
| `/assets/{asset_id}/user-metadata` | PATCH (merge) / **PUT** (replace, added 2026-06-04) | current |
| `/indexes/{index-id}/indexed-assets/{indexed-asset-id}` | PATCH | current — "Partial update indexed asset" |
| `/indexes/{index-id}/videos/{video-id}` | PATCH | ⚠️ **"This method will be deprecated in a future version. New implementations should use the Partial update indexed asset method."** |

Set fields to `null` to delete them.

### 4.7 Indexes (needed for Marengo search, NOT for Pegasus 1.5)
Source: [create index](https://docs.twelvelabs.io/api-reference/indexes/create), [search guide](https://docs.twelvelabs.io/docs/guides/search)

`POST https://api.twelvelabs.io/v1.3/indexes`. Valid `model_name`: **`marengo3.0`** and **`pegasus1.2`** only. `model_options`: `visual` and/or `audio`. `addons: ["thumbnail"]` — Marengo only, cannot be disabled after creation.

```python
index = client.indexes.create(
    index_name="zoovision-night",
    models=[{"model_name": "marengo3.0", "model_options": ["visual", "audio"]}],
)
asset = client.assets.create(method="url", url="<PRESIGNED_S3_URL>")
# poll asset.status == "ready" first
indexed_asset = client.indexes.indexed_assets.create(index_id=index.id, asset_id=asset.id)
```
Indexing takes "30–40% of the duration of the video".

### 4.8 Webhooks
Source: [webhooks](https://docs.twelvelabs.io/docs/advanced/webhooks), [response schema](https://docs.twelvelabs.io/docs/advanced/webhooks/response-schema)

Event types (exact strings): **`index.task.ready`**, **`index.task.failed`**, **`analyze.task.ready`**, **`analyze.task.failed`**.

Verbatim scope: *"Webhooks are supported for the Search and Analyze APIs but are unavailable for the Embed API."*

Registered **in the dashboard only** — https://playground.twelvelabs.io/dashboard/integrations/webhooks — no documented registration API.

Signature header is **`TL-Signature`** (not `twelvelabs-signature`), containing `t=<unix timestamp>,v1=<HMAC-SHA256>`.

```json
{
  "id": "whe_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "created_at": "2024-09-26T10:30:45.123Z",
  "type": "analyze.task.ready",
  "data": {
    "id": "64f8d2c7e4a1b37f8a9c5d12",
    "custom_id": "client-ref-42",
    "status": "ready",
    "created_at": "2024-09-26T10:29:19.968Z"
  }
}
```
Because Embed has no webhook, ZooVision must **poll** `client.embed.v_2.tasks.retrieve()` for embeddings while it can be webhook-driven for analysis.

---

## 5. Advanced features worth exploiting (hackathon scoring)

1. **Jockey + MCP + Claude Code plugin.** The hackathon is "Hack the Video Agent Context". TwelveLabs shipped the video agent context layer 15 days ago (knowledge stores, corpus digest, entity resolution, Responses API) and a Claude Code plugin *today*. Wiring `https://mcp.twelvelabs.io/jockey/mcp` into your GraphRAG morning-briefing flow — "ask across the whole archive, get cited moments back" — is the highest-leverage sponsor-alignment move available.
2. **`custom_id` + webhooks** → fully event-driven overnight pipeline. Encode `camera_id`, `animal_id` and chunk start time into `custom_id`; Strands reacts to `analyze.task.ready` instead of polling 48 tasks/camera/night.
3. **`prompt_v2` with up to 4 reference images.** Feed reference stills of *this specific animal* and *this enclosure's normal state* to disambiguate individuals and reduce false positives — the closest documented substitute for animal identity, and cheaper than entity collections.
4. **Video clipping (`start_time`/`end_time`, ≥4 s).** Once triage flags a segment, re-analyze **just that window** with a deeper schema. Billing is scoped to the window, so a 30-s deep re-read costs 0.5 min instead of 15.
5. **Per-definition `time_ranges`.** Run an expensive definition only over the hours that matter (e.g. 02:00–04:00) while a cheap definition covers the whole night.
6. **`fused_embedding`.** One vector combining visual + audio instead of two — halves Neo4j vector rows and captures "quiet stillness" vs "thrashing with noise" in a single embedding.
7. **Batch analysis (1,000 requests/call).** Submit an entire night across all cameras in one HTTP call, one batch ID to track.
8. **Timestamp formatting.** `segment_time_format: "hh:mm:ss.fff"` gives millisecond-formatted stamps for human-facing alerts while keeping `seconds` for the triage engine.
9. **`enable_hls` + `enable_thumbnail`** on `POST /assets` — TwelveLabs generates the playable evidence clip and thumbnail for you; skip a whole ffmpeg step in the alert UI.
10. **Marengo's `dynamic` segmentation with `min_duration_sec`.** Shot-boundary-aware embedding segments mean your "similar past clip" retrieval aligns to real behavioral units, not arbitrary 6-s tiles.

---

## 6. Limits, quotas, pricing

### 6.1 Pricing — Developer (pay-as-you-go)
Source: [twelvelabs.io/pricing](https://www.twelvelabs.io/pricing)

| Item | Price |
|---|---|
| Video indexing | **$0.042 / minute** |
| Infrastructure (monthly, storage) | $0.0015 / minute |
| Search API | $4 / 1,000 queries |
| Embed API — video / audio | **$0.042 / $0.0083 per minute** |
| Embed API — image / text | $0.1 / $0.07 per 1,000 requests |
| Analyze API — input video | **$0.0292 / minute** |
| Analyze API — output text | **$0.0075 / 1k tokens** |
| Developer plan capacity | unlimited video hours & indexes, 10,000 h/index, **25 concurrent tasks** |
| Enterprise | custom, committed-use contract |

### 6.2 ⚠️ The segmentation cost multiplier — read this twice
Source: [FAQ](https://docs.twelvelabs.io/docs/resources/frequently-asked-questions), [segment guide](https://docs.twelvelabs.io/docs/guides/segment-videos)

Verbatim: *"Each segment definition is charged separately, so your total billed duration equals the video window multiplied by the number of segment definitions."*

Documented examples:
- 1-hour video, 4 segment definitions, `start`/`end` = 0–60 s → **4 minutes billed** (60 s × 4)
- 1-hour video, full duration, 3 definitions → **3 billable hours**
- 1-hour video, 10–40 min range, 5 definitions → **2.5 billable hours**

Free plan carve-out: *"The video duration counts toward your plan quota. The number of segment definitions does not affect this quota."*

**ZooVision arithmetic** (12-h night, 15-min segments = 48 chunks = 720 min per camera per night):

| Config | Billed min/camera/night | Analyze input cost |
|---|---|---|
| 1 segment definition | 720 | **$21.02** |
| 3 segment definitions | 2,160 | **$63.07** |
| 5 segment definitions | 3,600 | **$105.12** |
| + Marengo video embeddings (all footage) | 720 | +$30.24 |
| + Marengo indexing (if using `/search`) | 720 | +$30.24 |

Plus output tokens at $0.0075/1k. **Design implication: one rich segment definition with many fields, not many definitions.** Field count is free (up to 20); definition count is not.

### 6.3 Free plan
Source: [pricing](https://www.twelvelabs.io/pricing), [FAQ](https://docs.twelvelabs.io/docs/resources/frequently-asked-questions), [manage your plan](https://docs.twelvelabs.io/docs/get-started/manage-your-plan)

- **600 minutes (10 hours) total, shared across indexing, analysis, and segmentation.** *"The limit is cumulative and does not reset if you delete indexes or videos."*
- 100 videos per index; 10 video-hours per index; **5 concurrent indexing tasks**
- Playground sample videos (~1 hour) **already count against your 600 min**
- **Indexes expire 90 days from creation** and are permanently deleted; upgrading to Developer converts not-yet-expired indexes to unlimited retention
- Entity search: 1 collection, ≤ 15 entities
- No credit card required

> **One 12-hour night on one camera = 720 minutes > the entire 600-minute lifetime Free quota.** ZooVision cannot be demoed on Free with real overnight volume. Either get sponsor credits, add a card (Developer Tier 1), or demo on a curated 20–40 min highlight reel.

### 6.4 Rate limits
Source: [rate limits](https://docs.twelvelabs.io/docs/get-started/rate-limits)

Dimensions: **DPD** duration/day (min), **DPH** duration/hour (min), **RPD** requests/day, **RPM** requests/min, **TPD** tokens/day (thousands), **TPM** tokens/min (thousands).

| Category | Free & Dev T1 (DPD/DPH/RPD/RPM/TPD/TPM) | Dev T2 | Dev T3 |
|---|---|---|---|
| Index | 3,000 / 600 / 3,000 / 60 / – / – | 6,000 / 1,200 / 6,000 / 120 | 12,000 / 2,400 / 12,000 / 240 |
| Upload | – / – / 3,000 / 60 | – / – / 6,000 / 120 | – / – / 12,000 / 240 |
| Search | – / – / 3,000 / 600 | – / – / 6,000 / 1,200 | – / – / 12,000 / 2,400 |
| **Analyze** | **3,000 / 600 / 1,000 / 60 / 500K / 30K** | 6,000 / 1,200 / 2,000 / 120 / 1,000K / 60K | 12,000 / 2,400 / 3,000 / 240 / 1,500K / 120K |
| Embed – Video | 3,000 / 600 / 3,000 / 25 | 6,000 / 1,200 / 6,000 / 50 | 12,000 / 2,400 / 9,000 / 75 |
| Embed – Audio | 3,000 / 600 / 3,000 / 25 | 6,000 / 1,200 / 6,000 / 50 | 12,000 / 2,400 / 9,000 / 75 |
| Embed – Text/Image | – / – / 3,000 / 600 | – / – / 12,000 / 1,200 | – / – / 30,000 / 2,400 |

Tiers: **T1** = default once a payment method is added; **T2** = spend $200/month; **T3** = spend $400/month; Enterprise = custom.

Headers: `X-RateLimit-Request-Remaining`, `X-RateLimit-Request-Reset`. Over-limit → **HTTP 429**.

**Analyze DPH = 600 min/hour** on Free/T1. ZooVision's 720 min/night spread over 12 h = 60 min/h — fine. But if segment-definition multiplication also multiplies DPD/DPH consumption (⚠️ **UNVERIFIED** — docs don't say), a 5-definition schema would consume 300 min/h of headroom.

**Raising limits:** documented path is *only* self-serve tier upgrade or the Enterprise contact form at https://www.twelvelabs.io/contact. **No email address for rate-limit increases appears anywhere in public docs.**

---

## 7. Amazon Bedrock path vs direct API

Source: [Bedrock TwelveLabs models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html), [Bedrock Marengo 3.0](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html), [TwelveLabs Bedrock analyze guide](https://docs.twelvelabs.io/docs/cloud-partner-integrations/amazon-bedrock/analyze-videos)

### ❌ Pegasus 1.5 is NOT on Amazon Bedrock

Verbatim from AWS: *"Amazon Bedrock offers three TwelveLabs models: TwelveLabs Pegasus 1.2 … TwelveLabs Marengo Embed 2.7 … TwelveLabs Marengo Embed 3.0."*

| Model | Bedrock model ID | Operations |
|---|---|---|
| Pegasus **1.2** | `twelvelabs.pegasus-1-2-v1:0` | `InvokeModel`, `InvokeModelWithResponseStream` |
| Marengo Embed 2.7 | (legacy) | `StartAsyncInvoke` |
| **Marengo Embed 3.0** | `twelvelabs.marengo-embed-3-0-v1:0` | `InvokeModel` (text/image/text_image/multi_input), `StartAsyncInvoke` (video/audio/…) |

Inference profiles: `global.` / `us.` / `eu.` / `apac.` prefixes (e.g. `us.twelvelabs.marengo-embed-3-0-v1:0`). Marengo 3.0 regions: `InvokeModel` in us-east-1 + eu-west-1 (profiles) + ap-northeast-2; `StartAsyncInvoke` base models in us-east-1, eu-west-1, ap-northeast-2.

**Consequence for ZooVision:** `analysis_mode=time_based_metadata` — the entire reason TwelveLabs is load-bearing here — **does not exist on Bedrock**. The Bedrock Pegasus request body is just `{"inputPrompt": "...", "mediaSource": {"s3Location"|"base64String"}}`; no `response_format`, no `segment_definitions`, no `analysis_mode`, no `prompt_v2`. **You must call the direct TwelveLabs API for Pegasus 1.5.** Do not let "the hackathon is AWS-hosted" push you onto Bedrock for analysis.

### Where Bedrock *does* help
Marengo Embed 3.0 on Bedrock is genuinely better for ZooVision's embedding leg:
- Reads directly from S3 (`s3Location.uri` + `bucketOwner`) — no re-upload of segments you already stored
- Bigger files: **6 GB / 4 hours** vs 4 GB direct
- Async results written to your own bucket via `outputDataConfig.s3OutputDataConfig.s3Uri`
- IAM instead of a bearer key; usage on the AWS bill
- Confirms the dimension change verbatim: *"Reduced embedding dimension – Reduced from 1024 to 512."*

```python
import boto3, json
client = boto3.client("bedrock-runtime")

model_input = {
    "inputType": "video",
    "video": {
        "mediaSource": {"s3Location": {
            "uri": "s3://zoovision-segments/cam-a/20260730T0215Z.mp4",
            "bucketOwner": "123456789012"}},
        "segmentation": {"method": "dynamic", "dynamic": {"minDurationSec": 4}},
        "embeddingOption": ["visual", "audio"],
        "embeddingType": ["separate_embedding", "fused_embedding"],
        "embeddingScope": ["clip", "asset"],
    },
}
invocation = client.start_async_invoke(
    modelId="twelvelabs.marengo-embed-3-0-v1:0",
    modelInput=model_input,
    outputDataConfig={"s3OutputDataConfig": {"s3Uri": "s3://zoovision-embeddings/"}},
)
```
Output objects: `{"data": {"embedding": [...], "embeddingOption": "...", "embeddingScope": "...", "startSec": 0, "endSec": 4.2}}`.

Caveats: base64-inline media must stay under Bedrock's **25 MB** invocation quota (use S3). Bedrock naming is camelCase (`embeddingOption`, `startSec`) vs the direct API's snake_case (`embedding_option`, `start_sec`) — **do not share a parser between the two paths.**

**Recommended split:** Pegasus 1.5 segmentation via direct API (`api.twelvelabs.io/v1.3`); Marengo 3.0 embeddings via Bedrock `StartAsyncInvoke` straight off your S3 segments. Mention both in the demo — it's an AWS-hosted hackathon and this is a legitimately AWS-native architecture.

---

## 8. Gotchas, version drift & deprecations

**Architecture-breaking**

1. **No video-to-video search.** *"Currently, the platform supports text and image queries."* `query_media_type` accepts only `image`. ZooVision's "video-to-video similarity search" must be implemented as: Marengo clip embedding → cosine similarity **in the Neo4j vector index**. Do not plan on `/search` for this. (Silver lining: this is already ZooVision's design, so the fix is wording + not calling `/search`.)
2. **Pegasus 1.5 is not on Bedrock.** §7.
3. **Segmentation billing multiplies by definition count.** §6.2.
4. **Free plan cannot hold a real night.** §6.3.
5. **Pegasus 1.5 cannot live in an index.** `POST /indexes` accepts only `marengo3.0` and `pegasus1.2`. Pegasus 1.5 is index-free by design — pass `url`/`asset_id`/`base64_string`. You need two parallel ingestion paths: asset-only for Pegasus, asset+index for Marengo search.

**Version drift that will break copy-pasted code**

6. **Docs URL scheme changed.** `docs.twelvelabs.io/reference/*` **404s**; the live path is `docs.twelvelabs.io/api-reference/*`. Several plausible URLs 404 today: `/reference/api-reference`, `/reference/analyze-videos`, `/docs/resources/rate-limits`, `/docs/get-started/pricing`, `/docs/concepts/webhooks`, `/docs/concepts/embeddings`, `/docs/guides/upload-methods`, `/docs/resources/faq`, `/docs/guides/entities`, `/api-reference/analyze-videos/batches`, `/docs/guides/analyze-videos/batch-analysis`.
7. **Embed response field renames.** `float_` → `embedding`; `start_offset_sec`/`end_offset_sec` → `start_sec`/`end_sec`. Embed API is now **v2** (`client.embed.v_2.*`).
8. **`embedding_option` renamed on Marengo 3.0.** 2.7 used `visual-text` / `visual-image` / `audio`; 3.0 uses `visual` / `audio` / `transcription`. Bedrock also switched from a **flat** to a **nested** request structure.
9. **`ResponseFormat` split** into `SyncResponseFormat` and `AsyncResponseFormat` (2026-04-20 breaking change). Wrong import = type error.
10. **`video_id` removed in Pegasus 1.5**, deprecated generally. Use `video={"type":"asset_id","asset_id":...}` / `VideoContext_AssetId`.
11. **`prompt` deprecated** in favour of `prompt_v2` (SDK kwarg: `prompt_v_2`). `prompt` is **rejected** when `analysis_mode=time_based_metadata`.
12. **`model_name` defaults to `pegasus1.2`.** Forget it and you silently lose segmentation, structured output, clipping, and the big context window. **Always set it explicitly.**
13. **`stream` defaults to `true`** on sync `/analyze`. Forget `stream=False` and you get NDJSON where you expected JSON.
14. **All uploads are async since 2026-07-07.** Every asset returns `status: processing`; invalid files fail *later*, not at upload. A pipeline that assumes "201 = usable" will fail intermittently.
15. **`user_metadata` values are primitives only** — string / integer / float / boolean. No arrays, no nested objects. Serialize lists to strings.
16. **`PATCH /indexes/{index-id}/videos/{video-id}` is officially slated for deprecation** in favour of `PATCH /indexes/{index-id}/indexed-assets/{indexed-asset-id}`. Three coexisting metadata generations (§4.6) — pick the indexed-assets one.
17. **`task.result.data` is a JSON string**, not a dict. `json.loads` it. Same for sync `result.data`.
18. **`thumbnail_url` in search results expires in 1 hour.** Re-fetch or copy to S3 before storing in Neo4j.
19. **Embed API has no webhooks.** Poll.
20. **Webhooks register in the dashboard only** — no API. That's a manual pre-demo setup step, and a single point of failure if the endpoint URL changes.
21. **Signature header is `TL-Signature`**, format `t=<ts>,v1=<hmac-sha256>`.

**Deprecated / dead**

22. **Marengo 2.7: SUNSET 2026-03-30 19:00 PT.** *"You no longer can index new content, perform search requests, or retrieve any embeddings from previously indexed content."* Any 1024-dim vectors from 2.7 are permanently unreachable. (AWS Bedrock docs still list Marengo Embed 2.7 as an available model — treat that as AWS doc lag and do not use it.)
23. **`/gist` and `/summarize` removed 2026-02-15.** Use `/analyze`.
24. **"Video indexing tasks" (`POST /tasks`) marked deprecated** — the bundled upload+index path. Use `POST /assets` then `POST /indexes/{id}/indexed-assets`.
25. **Deletion safeguards since 2026-04-26:** deleting a referenced asset returns **409 Conflict** unless `force=true`.
26. **Pegasus 1.2 has no published EOL**, but it is "general analysis only" and is the model AWS/VideoDB integrations are pinned to. Don't build new work on it.
27. **API keys default to 12-month expiry.** For a project you'll revisit, set "never expire".

**Capability gaps**

28. **No live-stream ingest.** Accepted inputs: local file, public URL, base64, S3 (Bedrock), Google Drive connector. No RTSP/RTMP endpoint. Real-time is only available through the **VideoDB partner integration** — which "Establishes live video stream connections from RTSP sources, IP cameras, or other streaming protocols" but runs **Pegasus 1.2**, so no segmentation. ZooVision's ffmpeg-segments approach is the correct and only Pegasus-1.5-compatible design.
29. **Audio is non-speech-only for the Models.** Modality docs: Audio = *"Ambient sounds, music, and sound effects"* + *"Human speech (Agents)"* or *"Non-speech audio only (Models)"*. Enumerated: *"Musical tones and melodies," "Beeping, alarms, and mechanical sounds," "Environmental sounds (rain, traffic, nature)."* No animal vocalization category. Distress vocalizations are **not** a documented capability.
30. **Entity search is documented for people/faces only.**
31. **No formal timestamp-accuracy bound in the docs.** Prompt-engineering guide gives zero accuracy numbers, zero hallucination warnings for timestamps. The only published figure is a press-release claim of *"boundary accuracy within approximately 350 milliseconds"* — marketing, not a documented SLA. Segment `start_time`/`end_time` are floats in seconds; formats offered are `seconds`, `hh:mm:ss`, `hh:mm:ss.fff` (**thousandths**, not hundredths).

---

## 9. Corrections to the ZooVision brief

| # | Brief claim | Verdict | Reality | Source |
|---|---|---|---|---|
| 1 | Marengo 3.0 GA Dec 1 2025 at re:Invent, 4-h video, 36 languages; Pegasus 1.5 GA Apr 20 2026 w/ Time-Based Metadata; Pegasus 1.2 remains for general analysis | ✅ **confirmed** | All four sub-claims verified verbatim. Pegasus docs: "Pegasus 1.2 … remains available for general analysis only." | [AWS PR](https://press.aboutamazon.com/aws/2025/12/twelvelabs-launches-its-most-powerful-video-understanding-model-marengo-3-0-on-twelvelabs-and-amazon-bedrock) · [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) · [Pegasus page](https://docs.twelvelabs.io/docs/concepts/models/pegasus) |
| 2 | Native JSON-schema via `response_format`; "beats Gemini 3.1 Pro on aggregated segmentation by 13.1%" | ✅ **confirmed** | `response_format.type` = `json_schema` or `segment_definitions`. 13.1% is verbatim in the launch press release. Underlying scores: 0.4279 vs 0.3370. **But** segmentation needs `analysis_mode="time_based_metadata"` *and* `response_format.type="segment_definitions"` — two params, not one. | [structured responses](https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses) · [PRWeb](https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html) · [Pegasus 1.5 blog](https://www.twelvelabs.io/blog/introducing-pegasus-1-5) |
| 3 | Context 261,120 tokens shared in+out; responses ≤ 98,304 | ✅ **confirmed** | Verbatim: "261,120 tokens for input and output per request", "up to 98,304 tokens". Raised from 65,536 on 2026-05-28. `max_tokens` floor is 2,048 in `time_based_metadata` mode. | [Pegasus page](https://docs.twelvelabs.io/docs/concepts/models/pegasus) · [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) |
| 4 | `POST /analyze/tasks` with `analysis_mode=time_based_metadata`, ≤2 h, model `pegasus1.5` | ✅ **confirmed** (one addition) | All three exact. Full URL `https://api.twelvelabs.io/v1.3/analyze/tasks`. **Addition:** you must *also* set `response_format.type="segment_definitions"`, and `prompt` is rejected in this mode. Also: max 10 definitions, 20 fields each. | [async task ref](https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task) · [segment guide](https://docs.twelvelabs.io/docs/guides/segment-videos) |
| 5 | `POST /analyze/batches`, ≤1,000 requests, requires Pegasus 1.5 | ✅ **confirmed** | All three confirmed by API-ref overview + 2026-06-18 release note. Returns one batch ID, per-item results. ⚠️ Exact request-body field names unverified (dedicated page 404s at the URLs I tried). | [analyze-videos ref](https://docs.twelvelabs.io/api-reference/analyze-videos) · [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) |
| 6 | Marengo 3.0 = 512-dim across visual/audio/dialogue/on-screen-text; 2.7 was 1024-dim | ✅ **confirmed** (modality names wrong) | 512 confirmed twice; Bedrock: "Reduced from 1024 to 512." **But** the modality enum is `visual`, `audio`, `transcription` (+`fused`) — there is no separate "dialogue" or "on-screen-text" embedding option; OCR/logos fold into `visual`, speech into `transcription`. 2.7's names were `visual-text`/`visual-image`/`audio`. | [Marengo page](https://docs.twelvelabs.io/docs/concepts/models/marengo) · [Bedrock Marengo 3.0](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html) |
| 7a | `POST /search` accepts a stringified-JSON `filter` over `user_metadata`; metadata set via `PUT /indexes/{index-id}/videos/{video-id}` | ⚠️ **mostly right, endpoint stale** | Stringified-JSON `filter` ✅ (`json.dumps`, operators `=`/`gte`/`lte`). Metadata endpoint is **PATCH**, not PUT, and carries: *"This method will be deprecated in a future version. New implementations should use the Partial update indexed asset method"* = `PATCH /indexes/{index-id}/indexed-assets/{indexed-asset-id}`. Modern options: `user_metadata` at `POST /assets`, or `PUT`/`PATCH /assets/{asset_id}/user-metadata`. Values must be primitives. | [filtering](https://docs.twelvelabs.io/docs/guides/search/filtering) · [videos/update](https://docs.twelvelabs.io/api-reference/videos/update) · [index-content/update](https://docs.twelvelabs.io/api-reference/index-content/update) |
| 7b | (implied by brief's pipeline) Marengo does **video-to-video similarity search** | ❌ **WRONG — architecture-critical** | Verbatim: *"Currently, the platform supports text and image queries."* `query_media_type` accepts only `image`; no video query type exists. Video-to-video similarity must be done by generating Marengo clip embeddings and comparing them **yourself** (ZooVision's Neo4j vector index). Metadata-scoping to one animal works, but as a Neo4j predicate, not a `/search` filter. | [any-to-video search](https://docs.twelvelabs.io/api-reference/any-to-video-search) · [search guide](https://docs.twelvelabs.io/docs/guides/search) |
| 8 | Webhooks for `analyze.task.ready`/`.failed`/`index.task.ready`; supported for Search & Analyze, NOT Embed | ✅ **confirmed** | Exact strings: `index.task.ready`, `index.task.failed`, `analyze.task.ready`, `analyze.task.failed`. Verbatim: "Webhooks are supported for the Search and Analyze APIs but are unavailable for the Embed API." **Additions:** dashboard-only registration, header `TL-Signature` = `t=…,v1=<HMAC-SHA256>`. | [webhooks](https://docs.twelvelabs.io/docs/advanced/webhooks) · [response schema](https://docs.twelvelabs.io/docs/advanced/webhooks/response-schema) |
| 9 | `POST /assets`: local ≤200 MB, URL ≤4 GB, multipart for larger | ✅ **confirmed** + updated ceiling | 200 MB / 4 GB exact. **Multipart is now 10 GB** (raised from 4 GB on 2026-07-07). Images 32 MB everywhere. Inline base64 caps at 36 MB video/audio. **Critical addition (2026-07-07):** all uploads return `status: processing`; polling to `ready` is mandatory for *every* upload. | [upload methods](https://docs.twelvelabs.io/docs/concepts/upload-methods) · [create asset](https://docs.twelvelabs.io/api-reference/upload-content/direct-uploads/create) |
| 10 | Video requirements: 360p+, aspect 1:1–2.4:1, **10 s – 2 h** | ❌ **duration wrong** | Docs say **"4 sec to 2 hours"** for Pegasus (Marengo: 4 sec to 4 hours). Minimum is **4 seconds, not 10**. Resolution is stated as a pixel range **360×360 to 5184×2160** (an upper bound too, which the brief omits). Aspect: "Between 1:1 and 1:2.4, or between 2.4:1 and 1:1" — matches. Pegasus file size ≤ 2 GB (brief omits). Also: sync `/analyze` caps at **1 hour**, not 2. | [Pegasus page](https://docs.twelvelabs.io/docs/concepts/models/pegasus) · [Marengo page](https://docs.twelvelabs.io/docs/concepts/models/marengo) |
| 11 | Free: single 10-h limit shared across indexing & analysis (older docs said 600 min); index expires 90 days | ✅ **confirmed** — but the parenthetical is a misread | Release note verbatim: "The Free plan now includes a single 10-hour limit shared across indexing and video analysis." 90-day expiry confirmed. **However 600 minutes IS 10 hours** — the FAQ says "a total of 600 minutes (10 hours)". These are the same number, not an old vs new figure. Real additions: quota is **cumulative and never resets**, playground samples count, segmentation definitions do *not* multiply the Free quota, 100 videos/index, 5 concurrent tasks. | [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) · [FAQ](https://docs.twelvelabs.io/docs/resources/frequently-asked-questions) · [pricing](https://www.twelvelabs.io/pricing) |
| 12 | Audio scope documented only as non-verbal audio (musical tones, beeping, environmental sounds) + transcription — NOT barking/whining/growling | ✅ **confirmed** | Modality docs enumerate exactly: "Musical tones and melodies", "Beeping, alarms, and mechanical sounds", "Environmental sounds (rain, traffic, nature)". Plus: Audio = *"Non-speech audio only (Models)"* vs *"Human speech (Agents)"*. Marengo page adds "Analyzes music, lyrics, sound, and silence". **No animal-vocalization category anywhere.** Mild nuance: "nature" under environmental sounds is arguably adjacent, but nothing species-specific is claimed. | [modalities](https://docs.twelvelabs.io/docs/concepts/modalities) · [Marengo page](https://docs.twelvelabs.io/docs/concepts/models/marengo) |
| 13 | No documented non-human-animal capability anywhere | ✅ **confirmed** | Six independent searches (docs, blog, case studies, Marengo 3.0 benchmark blog, Pegasus 1.5 blog, GitHub orgs). Zero animal/wildlife/zoo/veterinary case study, benchmark, or example. Published verticals: news, film & TV, sports, advertising, security, media archives. Pegasus 1.5 eval set = "news broadcasts, movies and television, sports footage". Marengo 3.0 blog: no animal benchmarks. Entity search is people/faces. The only animal string found in all of TwelveLabs' docs is a filter *example filename*, `"Animal Encounters part 1"`. | [Pegasus 1.5 blog](https://www.twelvelabs.io/blog/introducing-pegasus-1-5) · [Marengo 3.0 blog](https://www.twelvelabs.io/blog/marengo-3-0) · [github.com/twelvelabs-io](https://github.com/twelvelabs-io) · [entity search](https://docs.twelvelabs.io/docs/guides/search/entity-search) |
| 14 | No live-stream endpoint — file or directly-fetchable URL only | ✅ **confirmed** (+1 new input) | No RTSP/RTMP/live endpoint in the API. Inputs: local file, public URL, base64, S3 (Bedrock), and — **new 2026-07-20** — the **Google Drive data connector**. Real-time exists only via the **VideoDB** partner integration, which handles RTSP/IP-camera ingest + webhook alerting but runs **Pegasus 1.2** (so no segmentation). ffmpeg-segments is the right call. | [VideoDB integration](https://docs.twelvelabs.io/docs/resources/partner-integrations/video-db-real-time-video-understanding) · [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) |
| 15 | Timestamp accuracy not formally bounded/published; observed to hundredths of a second | ✅ **confirmed** (with a caveat + a correction) | No accuracy bound, SLA, or error figure in any docs page, including the prompt-engineering guide. **Caveat:** the launch press release does claim *"boundary accuracy within approximately 350 milliseconds"* — marketing, not documentation. **Correction:** the finest documented timestamp *format* is `hh:mm:ss.fff` = **thousandths**, and raw segment times are unbounded floats in seconds. Treat timestamps as approximate and always ship the evidence clip. | [prompt engineering](https://docs.twelvelabs.io/docs/guides/analyze-videos/prompt-engineering) · [PRWeb](https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html) · [release notes](https://docs.twelvelabs.io/docs/get-started/release-notes) |
| 16 | Contact "Kyle Cabigon (kc@twelvelabs.io)" can raise rate limits | ⚠️ **UNVERIFIED — treat as internal, do not publish** | A person named Kyle Cabigon is credibly associated with TwelveLabs (appears in a Product Hunt discussion explaining the design rationale for the Jockey MCP renderer). **The email address `kc@twelvelabs.io` appears in no public source I could find.** Searched: `"Kyle Cabigon" TwelveLabs`, docs rate-limits page, contact page. Documented rate-limit escalation is **only** self-serve tier upgrade or the Enterprise form at https://www.twelvelabs.io/contact — no email published. If a sponsor rep gave you this at the event, keep it in a private channel. | [rate limits](https://docs.twelvelabs.io/docs/get-started/rate-limits) · [Product Hunt](https://www.producthunt.com/products/twelvelabs) |
| 17 | TwelveLabs models available on Amazon Bedrock as an alternative to the direct API | ❌ **WRONG as applied to ZooVision** | Bedrock offers exactly **three**: Pegasus **1.2** (`twelvelabs.pegasus-1-2-v1:0`), Marengo Embed 2.7, Marengo Embed 3.0 (`twelvelabs.marengo-embed-3-0-v1:0`). **Pegasus 1.5 is not on Bedrock.** The Bedrock Pegasus body is only `{inputPrompt, mediaSource}` — no `response_format`, no `segment_definitions`, no `analysis_mode`, no `prompt_v2`. Bedrock is therefore **not** an alternative for ZooVision's core capability; it *is* a good path for Marengo 3.0 embeddings straight off S3 (6 GB / 4 h, IAM auth). | [Bedrock TwelveLabs models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html) · [TL Bedrock analyze guide](https://docs.twelvelabs.io/docs/cloud-partner-integrations/amazon-bedrock/analyze-videos) |

### Things the brief MISSED entirely
- **Jockey 1.0 / Agents (2026-07-15, research preview)** — knowledge stores, corpus digest, entity resolution, agentic search, Responses API. The hackathon's exact theme.
- **MCP server** at `https://mcp.twelvelabs.io/jockey/mcp` + **Claude Code plugin** (announced today, 2026-07-30).
- **The segmentation cost multiplier** (`duration × n_definitions`) — the single biggest budget landmine.
- **Marengo 2.7 is dead** (sunset 2026-03-30); old 1024-dim embeddings unrecoverable.
- **All uploads became async on 2026-07-07** — mandatory polling.
- **Pegasus 1.5 cannot be in an index**; two ingestion paths required.
- **Entity search** (`<@entity_id>` syntax) — people-only, but a plausible per-animal experiment.
- **`prompt_v2` reference images (≤4)** and **video clipping** — cheap precision wins.
- **`custom_id`** for task↔camera correlation.
- **Deletion safeguards** (409 unless `force=true`) and **`/gist`+`/summarize` removal**.
- **$100M Series B (2026-07-01)** — useful demo-day framing.

---

## 10. Open questions to resolve before demo day

1. **Does Pegasus 1.5 actually recognize animal behavior?** Untestable from docs — **zero** published animal capability. Run this first, before writing any other code: one 15-min real night-vision enclosure clip, the ZooVision segment definition, and a human-labelled ground truth. If `behavior` labels are noise, the whole pipeline is decorative. Budget half a day.
2. **Night-vision / IR footage.** All published benchmarks are daylight broadcast content. Do 850 nm monochrome IR frames survive Marengo's visual encoder and Pegasus's grounding? Test grayscale + low-contrast explicitly.
3. **Does the segment-definition multiplier also consume rate-limit DPD/DPH**, or only billing? Docs are silent. Affects overnight throughput planning. Ask the sponsor rep.
4. **Batch analysis exact request schema.** The dedicated API-ref page 404'd at every URL I tried. Confirm `POST /analyze/batches` body shape, per-item `custom_id`, results retrieval path, and whether `analysis_mode=time_based_metadata` is allowed in batches — before betting the pipeline on it.
5. **Can an entity be a non-human?** Try registering one snow leopard with 5 reference stills; query `<@leopard_a7> pacing`. If it works it's a killer per-animal scoping demo. If it silently fails, fall back to `prompt_v2` reference images + Neo4j metadata. Free plan allows 1 collection / 15 entities.
6. **Quota strategy.** 720 min/camera/night vs 600 min lifetime Free. Decide now: sponsor credits, Developer Tier 1 card, or a curated 20–40 min demo reel. Get this answered at the sponsor booth in hour one.
7. **Segment-boundary alignment across chunk seams.** A behavior spanning 14:50–15:10 splits across two independent Pegasus calls. Does the triage engine stitch adjacent-chunk segments? Overlapping ffmpeg segments (e.g. 15 min + 30 s overlap) cost extra billed minutes — decide the trade.
8. **`min_segment_duration` tuning for stillness.** A sleeping animal produces one enormous segment; a pacing one produces many. Sweep `min_segment_duration` 2/5/15 s and see which gives the triage engine usable granularity without token blowup.
9. **Baseline-vs-night comparability.** ZooVision baselines are daytime-only, but observations are night IR. Are Marengo embeddings of the same animal in daylight vs IR even in the same neighbourhood of the 512-d space? Measure cosine similarity day-vs-night for identical behavior before trusting the baseline.
10. **Webhook setup is dashboard-only.** No API. Someone must click through https://playground.twelvelabs.io/dashboard/integrations/webhooks with a publicly reachable URL (ngrok/Lambda URL) and implement `TL-Signature` verification. Add it to the demo runbook, or fall back to polling.
11. **Bedrock region + model access.** `twelvelabs.marengo-embed-3-0-v1:0` needs explicit model access enabled, and `StartAsyncInvoke` base models are only in us-east-1 / eu-west-1 / ap-northeast-2. Confirm your hackathon account and bucket are in-region.
12. **Jockey access.** "Research preview with limited sign-ups." Apply now; if approved, `client.responses.create(model="jockey1.0", ...)` for the 06:00 GraphRAG briefing is the strongest sponsor-alignment story available. ⚠️ The Jockey/Responses SDK signature is third-party-reported, not read off a docs page I fetched — verify against live docs.
13. **Pegasus 1.2 EOL.** Unannounced. Anything you build on VideoDB or Bedrock Pegasus rests on a legacy model with no published sunset date.
14. **Does Pegasus 1.5 use audio at all when handed a bare URL?** There's no `model_options` on the index-free path, so audio inclusion is implicit and undocumented. If ZooVision ever wants vocalization evidence, verify empirically — and remember audio is documented as non-speech ambient only.

---

## 11. Sources

**Fetched: TwelveLabs docs — models & concepts**
- https://docs.twelvelabs.io/docs/concepts/models/pegasus — Pegasus 1.5/1.2 versions, 261,120-token context, 98,304 max response, 4 s–2 h, ≤2 GB, resolution/aspect, languages
- https://docs.twelvelabs.io/docs/concepts/models/marengo — Marengo 3.0, **512-dim**, 4 s–4 h, ≤4 GB, 36 languages, audio = "music, lyrics, sound, and silence"
- https://docs.twelvelabs.io/docs/concepts/models — model overview ("Use Marengo for embeddings, Pegasus for text generation"); no versions/deprecations listed
- https://docs.twelvelabs.io/docs/concepts/modalities — **verbatim audio scope**: musical tones, beeping/alarms/mechanical, environmental (rain/traffic/nature); "Non-speech audio only (Models)"
- https://docs.twelvelabs.io/docs/concepts/upload-methods — 200 MB / 4 GB / **10 GB multipart**, base64 36 MB, sync-vs-async duration bands, mandatory polling
- https://docs.twelvelabs.io/docs/get-started/introduction — capability list; Jockey research preview; "Models for … Agents for corpus-level reasoning"
- https://docs.twelvelabs.io/docs/get-started/release-notes (+ `.md`) — **full timeline Oct 2025 → Jul 2026**; Marengo 2.7 sunset wording; Free-plan 10 h; batch analysis; async uploads; Jockey
- https://docs.twelvelabs.io/docs/get-started/rate-limits (+ `.md`) — full DPD/DPH/RPD/RPM/TPD/TPM tables for Free + Dev T1/T2/T3; 429; escalation = tier upgrade or contact form (**no email**)
- https://docs.twelvelabs.io/docs/get-started/migration-guide — `video_id` **removed** in 1.5; `prompt`→`prompt_v_2`; `ResponseFormat` split; **no Pegasus 1.2 EOL**
- https://docs.twelvelabs.io/docs/resources/frequently-asked-questions — **billing worked examples** (3 defs = 3 h); 600 min = 10 h cumulative; 100 videos/index; indexing = 30–40% of duration
- https://docs.twelvelabs.io/docs/llms.txt — docs index; revealed `/docs/advanced/claude-code-plugin`, `/docs/advanced/metadata`, webhook sub-pages
- https://docs.twelvelabs.io/llms.txt — `.md` / `/llms.txt` conventions; docs MCP at `/_mcp/server`; v1.3 default

**Fetched: TwelveLabs docs — guides**
- https://docs.twelvelabs.io/docs/guides/analyze-videos — sync <1 h vs async ≤2 h vs batches; NDJSON streaming events
- https://docs.twelvelabs.io/docs/guides/segment-videos — **`analysis_mode` + `response_format` both required**; 10 defs / 20 fields / 4 media sources; response JSON shape; **Python + Node samples verbatim**
- https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses — JSON-Schema types/keywords, `anyOf` only, `minItems` 0|1, "schema takes precedence over the prompt", sync + stream samples
- https://docs.twelvelabs.io/docs/guides/analyze-videos/prompt-engineering — **no timestamp accuracy figures published**
- https://docs.twelvelabs.io/docs/guides/search — index creation with `marengo3.0`; `indexed_assets.create`; **"platform supports text and image queries"**
- https://docs.twelvelabs.io/docs/guides/search/filtering — `filter` is stringified JSON; `gte`/`lte`; AND semantics
- https://docs.twelvelabs.io/docs/guides/search/entity-search — **people only**, "show each person's face clearly"; `<@entity_id>`; Free = 1 collection / 15 entities
- https://docs.twelvelabs.io/docs/guides/create-embeddings/video/new — `client.embed.v_2.tasks.create`; `embedding_option` = visual/audio/transcription (+fused); scope clip/asset; fields `embedding`/`start_sec`/`end_sec`
- https://docs.twelvelabs.io/docs/advanced/metadata — primitives only; `client.indexes.videos.update`; filter usage
- https://docs.twelvelabs.io/docs/advanced/webhooks (+ `.md`) — "supported for Search and Analyze … unavailable for the Embed API"; dashboard-only registration
- https://docs.twelvelabs.io/docs/advanced/webhooks/response-schema — **exact event strings**; `TL-Signature` = `t=…,v1=…`; payload examples
- https://docs.twelvelabs.io/docs/advanced/model-context-protocol — `https://mcp.twelvelabs.io/jockey/mcp`; `claude mcp add --transport http --scope user jockey …`; OAuth
- https://docs.twelvelabs.io/docs/resources/partner-integrations/video-db-real-time-video-understanding — **VideoDB does RTSP/IP-camera ingest, running Pegasus 1.2**

**Fetched: TwelveLabs API reference**
- https://docs.twelvelabs.io/api-reference/introduction — base URL, `v1.3`, URL pattern
- https://docs.twelvelabs.io/api-reference/authentication — **`x-api-key`**; base `…/v1.3`; key expiry default 12 months
- https://docs.twelvelabs.io/api-reference/analyze-videos — three endpoints: `/analyze`, `/analyze/tasks`, `/analyze/batches` (1,000, requires Pegasus 1.5)
- https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task — **full param table**, `video` union, `prompt_v2`, `response_format` structures, `max_tokens` ranges, `custom_id`, 202 response
- https://docs.twelvelabs.io/api-reference/analyze-videos/analyze — sync spec; **`stream` defaults true**; `video_id` deprecated; `usage.input_tokens`; 4 s–1 h
- https://docs.twelvelabs.io/api-reference/any-to-video-search — **"Currently, the platform supports text and image queries"**
- https://docs.twelvelabs.io/api-reference/any-to-video-search/make-search-request — multipart/form-data, full param list, filter examples, response shape, thumbnail 1-h expiry
- https://docs.twelvelabs.io/api-reference/indexes/create — **only `marengo3.0` and `pegasus1.2` valid**; `model_options`; thumbnail addon
- https://docs.twelvelabs.io/api-reference/upload-content — three methods; **video indexing tasks deprecated**
- https://docs.twelvelabs.io/api-reference/upload-content/direct-uploads/create — `POST /assets` full spec; **mandatory polling quote**
- https://docs.twelvelabs.io/api-reference/videos/update — **PATCH** + deprecation warning pointing to indexed-assets
- https://docs.twelvelabs.io/api-reference/index-content/update — `PATCH /indexes/{index-id}/indexed-assets/{indexed-asset-id}`
- https://docs.twelvelabs.io/sdk-reference/python — SDK follows API structure (partial method list only)
- https://docs.twelvelabs.io/sdk-reference/python/analyze-videos — method names `analyze`, `analyze_stream`, `analyze_async.tasks.create`, `analyze_async.batches.create`

**Fetched: 404s worth recording (do not link these in the brief)**
`/reference/api-reference` · `/reference/analyze-videos` · `/reference/update-video-information` · `/docs/resources/rate-limits` · `/docs/get-started/pricing` · `/docs/concepts/webhooks` · `/docs/concepts/embeddings` · `/docs/guides/upload-methods` · `/docs/resources/faq` · `/docs/guides/entities` · `/api-reference/video-embeddings/create-video-embedding-task` · `/api-reference/analyze-videos/batches` · `/api-reference/analyze-videos/batch-analysis/create` · `/docs/guides/analyze-videos/batch-analysis`

**Fetched: AWS**
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html — **"Amazon Bedrock offers three TwelveLabs models"**: Pegasus 1.2, Marengo Embed 2.7, Marengo Embed 3.0. **No Pegasus 1.5.**
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html — `twelvelabs.marengo-embed-3-0-v1:0`; **"Reduced from 1024 to 512"**; nested request structure; 6 GB / 4 h; 25 MB base64 cap; regions; full param + response reference; Python examples
- https://press.aboutamazon.com/aws/2025/12/twelvelabs-launches-its-most-powerful-video-understanding-model-marengo-3-0-on-twelvelabs-and-amazon-bedrock — Marengo 3.0 GA **2025-12-01** at re:Invent; 4-h, −50% storage, 2× indexing, 12→36 languages

**Fetched: TwelveLabs marketing & press**
- https://www.twelvelabs.io/pricing — all Developer per-unit prices; Free 10 h / 600 min / 90 days / 100 videos / 5 concurrent; Dev 25 concurrent
- https://www.twelvelabs.io/blog/introducing-pegasus-1-5 — 0.4279 vs Gemini 3.1 Pro 0.3370 segmentation; 0.4555 vs 0.3243 multimodal prompting; eval verticals = news/film-TV/sports; **no animals**
- https://www.twelvelabs.io/blog/marengo-3-0 — 512-dim vs Nova 3072 / Vertex 1408; 70.2/73.2/92.2/88.3 composites; MSRVTT 72.5; SoccerNet 79.4 mAP; latency 0.05 s/s; **no animal benchmarks**
- https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html — **GA 2026-04-20**; **"13.1%"** vs Gemini 3.1 Pro; **"~350 milliseconds"** boundary accuracy; no Bedrock mention
- https://www.twelvelabs.io/jockey — Jockey capabilities, MCP URL, research preview / limited sign-ups, Jockey storage pricing
- https://www.twelvelabs.io/blog/claude-code-plugin — **dated 2026-07-30**; index/search/analyze/embed/entity-search; `twelvelabs:` namespace
- https://www.twelvelabs.io/blog/twelve-labs-and-videodb — **dated 2026-07-30**; VideoDB = real-time infra layer, TwelveLabs = **Pegasus 1.2** model
- https://www.globenewswire.com/news-release/2026/07/01/3320545/0/en/TwelveLabs-Raises-100-Million-in-Series-B-Funding-to-Build-Video-Superintelligence.html — $100M Series B, 2026-07-01

**Fetched: packages & code**
- https://pypi.org/project/twelvelabs/ — **`twelvelabs` 1.3.1, 2026-07-23**; Python >=3.8,<4.0; history 1.3.0 (07-21), 1.2.9 (07-07), 1.2.8 (06-18), 1.2.7 (06-08)
- https://github.com/twelvelabs-io — repo list: `twelvelabs-python`, `twelvelabs-js`, `twelve-labs-claude-code-plugin`, `tl-solutions-samples`, `tl-marengo-bedrock-s3`, `multi-modal-video-search`, `twelvelabs-developer-experience`, `video-embeddings-evaluation-framework`, `tl-whitepapers`; **no animal/wildlife repo**
- https://github.com/twelvelabs-io/twelvelabs-python — README samples: `indexes.create`, `assets.create`, `indexes.indexed_assets.create`, `search.query`, `analyze`, `analyze_stream`

**Searches run that found NOTHING (negative evidence for claim 13)**
`TwelveLabs wildlife animal behavior video analysis case study` · `"twelvelabs" Pegasus animal OR dog OR cat OR zoo OR livestock behavior detection prompt` · `TwelveLabs Pegasus "animal" video understanding limitations non-human subjects` · `site:twelvelabs.io animal wildlife zoo` · `TwelveLabs Marengo Pegasus "animal" OR "pet" OR "veterinary" demo hackathon example github` — no TwelveLabs animal/wildlife/zoo/veterinary case study, benchmark, blog post, doc page, or first-party example exists as of 2026-07-30.

**Search that could not verify claim 16**
`"Kyle Cabigon" TwelveLabs` — person plausibly affiliated (Product Hunt discussion on the Jockey MCP renderer); **`kc@twelvelabs.io` appears in no public source.**
