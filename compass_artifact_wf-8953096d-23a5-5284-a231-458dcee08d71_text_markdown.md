# Overnight Animal-Welfare Monitoring: Technical Architecture & Product Design
## "Hack the Video Agent Context" (AWS/HackerSquad, SF 2026)

## TL;DR
- **Build it as a Strands-orchestrated pipeline where each sponsor is load-bearing:** TwelveLabs Pegasus 1.5 does schema-constrained per-chunk behavior extraction and Marengo 3.0 does per-animal video-to-video anomaly search; OpenAI GPT-5.6 Terra (via the Strands `OpenAIResponsesModel`) merges/structures and phrases alerts; Neo4j Aura is the context graph + vector index that stores every animal's baseline and powers the GraphRAG morning briefing. The reference repo `jpadams/video-context-graph` already wires all four together and already defaults to `gpt-5.6` / `gpt-5.6-terra` — fork it, don't rebuild it (https://github.com/jpadams/video-context-graph).
- **The load-bearing design decision is the individual baseline + deterministic triage split:** TwelveLabs/OpenAI produce observations; a non-LLM Python rule engine decides urgency against each animal's own daytime-only baseline. This is what makes the system trustworthy and auditable and is your strongest judging differentiator over a generic "ask questions about video" demo.
- **Your biggest technical truth to confront up front:** TwelveLabs has *no documented non-human-animal capability*, and its audio understanding names only "musical tones, beeping, environmental sounds" — not barking/whining/growling (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio). Treat animal-behavior and animal-sound detection as an unverified extension you validate in shadow mode, not a guarantee. This honesty is itself a scoring asset for a welfare product.

## Key Findings

### The four sponsors, current versions, and where each sits
- **TwelveLabs** — Current models are **Marengo 3.0** (embeddings/search, GA Dec 1 2025 at AWS re:Invent, four-hour video support, 36 languages — https://press.aboutamazon.com/aws/2025/12/twelvelabs-launches-its-most-powerful-video-understanding-model-marengo-3-0-on-twelvelabs-and-amazon-bedrock) and **Pegasus 1.5** (video-to-text + Time-Based Metadata segmentation, GA April 20 2026; Pegasus 1.2 remains for general analysis — https://docs.twelvelabs.io/docs/concepts/models/pegasus). Structured JSON-schema output is native to Pegasus 1.5 via `response_format`. Free plan gives a single 10-hour limit shared across indexing and analysis (older docs say 600 minutes — https://www.twelvelabs.io/pricing). Contact Kyle Cabigon (kc@twelvelabs.io) to raise limits.
- **OpenAI** — Your committed model **GPT-5.6 Terra** is real and documented: model ID `gpt-5.6-terra`, GA July 9 2026, 1.05M-token context, 128K max output, Responses API, reasoning-effort control, structured outputs, vision input, Programmatic Tool Calling, and native Compaction + encrypted reasoning items (https://developers.openai.com/api/docs/models/gpt-5.6-terra).
- **Strands Agents (AWS)** — Genuinely used as the orchestrator via agents-as-tools + Graph/Swarm/Workflow primitives, with the `OpenAIResponsesModel` provider pointing at GPT-5.6, and a deployment path to Amazon Bedrock AgentCore Runtime (https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/).
- **Neo4j** — Aura Free tier (200k nodes / 400k relationships), native vector index + vector-search-with-filters (GA), official Neo4j MCP server, and the NICD "GraphRAG makes AI agents 80% more truthful" study as your GraphRAG justification (https://neo4j.com/blog/agentic-ai/study-graphrag-ai-agents-80-percent-more-truthful/).

### The reference repo already does most of your plumbing
`jpadams/video-context-graph` (forked from `neo4j-labs/create-context-graph`) is a FastAPI + Strands backend + Next.js/NVL frontend that ingests video → Pegasus analyze → OpenAI Structured Outputs → Marengo embed (512-dim) → Neo4j write, with a live graph viz and an agent exposing graph tools. It already defaults `OPENAI_MODEL=gpt-5.6`, `OPENAI_EXTRACTION_MODEL=gpt-5.6-terra`, `MARENGO_MODEL=marengo3.0`, `PEGASUS_MODEL=pegasus1.2` (https://github.com/jpadams/video-context-graph). Reuse the ingestion/agent/vector plumbing; replace the entity/topic ontology with an animal-behavior ontology.

---

## Details

## 1. Sponsor-Maximization Matrix

### 1.1 TwelveLabs — what the product uses, and the advanced features to exploit
**Load-bearing role:** TwelveLabs is the only component that turns raw enclosure video into machine-readable, timestamped behavior — nothing downstream works without it.

**APIs / models used:**
- **Pegasus 1.5 async analysis** — `POST /analyze/tasks` (async, videos up to 2 hours) with `analysis_mode=time_based_metadata` and a `response_format` JSON schema that returns an `observations[]` array. This is the core ingestion call per 15-minute chunk. Model string `pegasus1.5`. Context window 261,120 tokens shared input+output; responses up to 98,304 tokens (https://docs.twelvelabs.io/docs/concepts/models/pegasus, https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task).
- **Structured/JSON-schema output** — Pegasus 1.5 was purpose-built for schema-conformant JSON (launch claim: outperforms Gemini 3.1 Pro on aggregated segmentation by 13.1%, fewer invalid-JSON failures — https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html). This is what lets your rule engine stay deterministic. See also https://docs.twelvelabs.io/docs/get-started/release-notes.
- **Marengo 3.0 embeddings + any-to-video search** — video-to-video similarity search filtered to one animal's `user_metadata` catches anomalies that don't fit a named behavior enum. Marengo 3.0 produces 512-dim embeddings across visual/audio/dialogue/on-screen-text (https://www.twelvelabs.io/product/embed); note Marengo 2.7 via the Embed API historically produced 1024-dim (https://aws.amazon.com/blogs/big-data/optimize-multimodal-search-using-the-twelvelabs-embed-api-and-amazon-opensearch-service/), so verify dimension at ingest time as the repo does. Model concept page: https://docs.twelvelabs.io/docs/concepts/models/marengo.
- **Metadata-filtered search** — `POST /search` supports a stringified-JSON `filter` over `user_metadata` you first set via `PUT /indexes/{index-id}/videos/{video-id}`. This is the mechanism that scopes search to a single animal's history (https://docs.twelvelabs.io/api-reference/any-to-video-search/make-search-request).
- **Webhooks** — register an endpoint to receive `analyze.task.ready` / `analyze.task.failed` and `index.task.ready` events instead of polling (https://docs.twelvelabs.io/docs/webhooks, schema at https://docs.twelvelabs.io/docs/webhooks-notification-schema). Webhooks are supported for Search and Analyze but NOT for the Embed API.
- **Upload** — `POST /assets` (direct local upload ≤200MB; URL upload ≤4GB; multipart for larger local files) then index/analyze. A 15-minute 720p chunk is well within limits (https://docs.twelvelabs.io/v1.3/api-reference/upload-content/direct-uploads/create).
- **Audio** — Marengo audio embeddings cover "non-verbal audio (musical tones, beeping, environmental sounds)" and "transcription" (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio).

**Advanced-feature exploitation for higher score:** batch analysis (`POST /analyze/batches`, up to 1,000 requests in one call, requires Pegasus 1.5) to fan out a whole night of chunks at once; per-definition time ranges to bound billing; multimodal prompting with a reference image of the specific animal to disambiguate enclosure-mates.

### 1.2 OpenAI GPT-5.6 Terra — every Key API feature + agentic primitive mapped
**Load-bearing role:** the reasoning layer that merges observations with the animal's baseline/care record and phrases the human-readable alert — but never decides severity.

**Verified GPT-5.6 Terra facts:** model ID `gpt-5.6-terra` (the bare `gpt-5.6` alias routes to Sol, not Terra); GA July 9 2026; 1.05M context; 128K max output; standard short-context pricing $2.50/1M input, $15/1M output; prompts >272K input priced 2× input/1.5× output; served on the **Responses API**; reasoning.effort control (repo uses `low`, also accepts `none`); knowledge cutoff Feb 16 2026 (https://developers.openai.com/api/docs/models/gpt-5.6-terra, https://developers.openai.com/api/docs/models, https://openai.com/index/gpt-5-6/).

**Four Key API features → concrete placement:**
1. **Multimodal context** → Analysis Agent reasons over Pegasus observation JSON + Neo4j baseline/care context in one call; optionally attach a key frame from the clip.
2. **Structured outputs** → Analysis Agent emits the `events[]` contract (JSON-schema-constrained), and the alert-phrasing agent emits `{headline, why_unusual, action}` so no free-text parsing downstream.
3. **Function calling** → agent tools `query_baseline(animal_id, behavior)`, `query_care_record(animal_id)`, `search_scene(animal_id, text)`, `run_cypher(read_only)`.
4. **Compaction** → across a full night per enclosure (dozens of chunks), use Responses API server-side compaction (`context_management` + `compact_threshold`, or the `/responses/compact` endpoint) to keep the rolling investigation within budget; ZDR-friendly with `store=false` (https://developers.openai.com/api/docs/guides/compaction).

**Three Advanced agentic primitives → concrete placement:**
1. **Programmatic tool calling** → the morning-report agent writes an in-runtime program that batches per-animal graph lookups, joins Event+Baseline deltas, dedups, and returns only the evidence rows (https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling).
2. **Multi-agent** → specialists: visual/behavior analyst, audio-note reviewer, graph investigator (mirrors the Strands agents-as-tools shape).
3. **Persisted reasoning** → keep `reasoning.encrypted_content` / `reasoning.context: "all_turns"` across the multi-step 2am investigation of one animal so each new chunk is not an isolated prompt (https://developers.openai.com/api/docs/guides/conversation-state).

### 1.3 Strands Agents — genuinely load-bearing orchestration
**Role:** the top-level orchestrator whose tool list mixes plain functions (deterministic) and sub-agents (LLM), exactly as your design specifies.

- **Agents-as-tools** — pass a sub-agent directly in the `tools=[]` array; the SDK converts it to a tool (https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/).
- **Multi-agent primitives** — Graph (deterministic directed orchestration via `GraphBuilder`), Swarm (autonomous handoffs), Workflow (task pipeline from `strands-agents-tools`). For your fixed day/night branch, use **Graph** (deterministic path) rather than Swarm, because your execution path is known in advance and you want auditable, low-token coordination (https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/, https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/).
- **OpenAI provider** — `strands.models.openai_responses` / `OpenAIResponsesModel` points Strands at `gpt-5.6-terra` on the Responses API; it can also connect to Bedrock's OpenAI-compatible Mantle endpoint with a Bedrock API key (https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/, https://strandsagents.com/docs/api/python/strands.models.openai_responses/).
- **AgentCore path** — deploy the orchestrator to Amazon Bedrock AgentCore Runtime (`BedrockAgentCoreApp`, `@app.entrypoint`, `agent.stream_async`), which handles containers/scaling/long-running tasks (up to 8 hours), plus AgentCore Memory/Gateway/Identity/Observability (CloudWatch + OTEL) (https://aws.amazon.com/blogs/machine-learning/strands-agents-sdk-a-technical-deep-dive-into-agent-architectures-and-observability/, https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html).
- **AWS Agent Toolkit during the build** — install the `aws-core` plugin (bundles the AWS MCP Server + curated skills) in Claude Code/Codex/Cursor/Kiro to scaffold the S3 buckets, Lambda watchers, and IAM policies; available at no additional charge, you pay only for resources (https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/, https://github.com/aws/agent-toolkit-for-aws, launch: https://aws.amazon.com/about-aws/whats-new/2026/05/agent-toolkit/). The AWS MCP Server gives the agent 300+ AWS services / real-time docs / sandboxed script execution; skills load only when relevant to save context.

### 1.4 Neo4j — the governable knowledge layer
**Role:** the context graph that stores every animal's baseline, care record, events, and alerts, and powers the morning GraphRAG briefing and the multi-week trend view.

- **Aura Free** — 200k nodes / 400k relationships, single database, no credit card (https://neo4j.com/cloud/platform/aura-graph-database/faq/). Note a documented source discrepancy: some Neo4j product pages have shown 50k/175k; cite the FAQ figure and flag the conflict (https://checkthat.ai/brands/neo4j/pricing).
- **Native vector index + filtered vector search (GA)** — store Marengo 512-dim embeddings on `:Clip` nodes for GraphRAG anomaly retrieval; vector search with in-index filters and native `VECTOR<FLOAT32>` type are GA (https://feedback.neo4j.com/changelog, https://neo4j.com/docs/aura/managing-instances/vector-optimization/).
- **Official MCP server** — `neo4j/mcp` (Docker `mcp/neo4j`, 4 tools: get-schema, read-cypher, write-cypher, list-gds-procedures) and Neo4j Labs `mcp-neo4j-cypher`; run the agent's graph access in read-only mode (`NEO4J_READ_ONLY=true`) (https://github.com/neo4j/mcp, https://github.com/neo4j-contrib/mcp-neo4j).
- **GraphRAG justification** — the independent NICD study, funded by Neo4j and titled *"Reducing Hallucinations in Complex Question Answering using Simple Graph-based Retrieval-Augmented Generation,"* tested 510 complex questions from the MoNaCo benchmark using a single LLM (GPT-5.4): GraphRAG increased truthfulness scores by ~80%, and more than doubled the answer rate from ~29% (vector-only RAG) to nearly 66%, while using tokens more efficiently. To be presented at the 52nd VLDB (Boston, Aug 31–Sep 4 2026) (https://neo4j.com/blog/agentic-ai/study-graphrag-ai-agents-80-percent-more-truthful/).

---

## 2. Full End-to-End Technical Architecture

### 2.1 Capture → ingestible files
Enclosure cameras are RTSP/ONVIF. TwelveLabs has no live-stream endpoint — it takes a file or a directly fetchable media URL. So a **segmenter** (ffmpeg segment muxer) sits in front of each camera producing ~15-minute closed MP4 segments with reset timestamps and strftime filenames like `enc07_2026-07-30_0200.mp4`. A **watcher** (S3 ObjectCreated → Lambda, or a filesystem inotify process) fires when a segment closes and hands the object to the Ingestion Agent. **Chunk requirements confirmed against docs:** 360p+ resolution, aspect ratio between 1:1 and 2.4:1, duration between 10 seconds and 2 hours — a 15-minute 720p clip is well inside these (https://docs.twelvelabs.io/sdk-reference/python/upload-content/video-indexing-tasks).

**Timestamp reconciliation:** Pegasus returns times relative to each chunk (observed precision to hundredths of a second, e.g. `6.50s`). The ingestion layer offsets every `start_time`/`end_time` by the chunk's wall-clock `chunk_start_ts` (parsed from the strftime filename) before anything is written downstream, so a behavior at 400s into `enc07_2026-07-30_0200.mp4` becomes `02:06:40`. Note: TwelveLabs publishes no formal timestamp-accuracy bound, only that segments carry start/end times (https://docs.twelvelabs.io/docs/guides/segment-videos) — treat sub-second precision as best-effort, not guaranteed.

### 2.2 Storage layout (S3)
- `s3://welfare-raw/{facility}/{enclosure_id}/{yyyy}/{mm}/{dd}/{enclosure}_{ts}.mp4` — raw 15-min chunks, 7-day retention (lifecycle rule).
- `s3://welfare-clips/{animal_id}/{event_id}.mp4` — extracted alert clips (ffmpeg cut on offset event start−5s to end+5s), 90-day retention.
- `s3://welfare-analysis/{animal_id}/{chunk_id}.json` — raw Pegasus observation JSON, 30-day retention.
TwelveLabs assets are separately retained in the TwelveLabs index (a Free-plan index expires at 90 days).

### 2.3 The agents in sequence (with endpoints & models)
1. **Agent 1 — Ingestion (TwelveLabs, no LLM).** Plain Strands `@tool` function. `assets.create` (or index task) → tag `user_metadata` `{enclosure_id, animal_id, shift, chunk_start_ts}` via `PUT /indexes/{index-id}/videos/{video-id}` → `POST /analyze/tasks` with `model_name=pegasus1.5`, `analysis_mode=time_based_metadata`, and the fixed `response_format` schema → receive webhook `analyze.task.ready` (or poll the task endpoint with exponential backoff). Emits `observations[]` of `{start_time, end_time, behavior, confidence, animals_involved, audio_notes, description}` with `behavior` a constrained enum: `pacing | vomiting | fighting | inactivity | water_bowl_tipped | escape_attempt | drinking | eating | resting | vocalizing | normal_activity`. In parallel, Marengo embeds the chunk (512-dim) for vector search.
2. **Agent 2 — Analysis (OpenAI GPT-5.6 Terra, Responses API).** Strands sub-agent. First pulls `BaselineProfile` + `CareRecord` from Neo4j. Merges/structures only — emits `events[]` `{animal_id, event_type, start_ts, end_ts, duration_min, baseline_delta_z, audio_flag, entities, relationships}`. `baseline_delta_z` is computed deterministically in Python and passed in as context; the model just attaches it. Structured Outputs enforce the schema.
3. **Agent 3 — Rule/Triage (deterministic Python, NOT an LLM).** First-match-wins: `fighting`→CRITICAL; `escape_attempt`→CRITICAL; `vomiting`→HIGH; `pacing >20min AND no water contact within 6h`→HIGH; `pacing >10min`→MODERATE; `inactivity > baseline+2σ`→MODERATE; `baseline_delta_z > 2.5`→MODERATE; `water_bowl_tipped`→LOW; else NONE. Output always carries `rule_fired`.
4. **Agent 4 — Indexing (Neo4j).** Idempotent `MERGE` writes keyed on `event_id = hash(animal_id, chunk_id, start_ts, behavior)` so reprocessing never duplicates. Graph writes described in §4.
5. **Agent 5 — Alert.** Fires only when `severity != NONE AND shift == night`; day-mode events just log. Writes an `Alert` node linked `TRIGGERED` with `sent_at`, `channel`, `ack_state`. LLM used only to phrase the message (tier already decided).
6. **Agent 6 — Reporting.** Scheduled at shift boundary (not event-driven). One aggregation query per animal joining Event + Baseline deltas for the whole shift.

**Strands orchestration shape:** the top-level orchestrator's tool list deliberately mixes plain functions and sub-agents — `ingest_tool` (plain), `analyze_tool` (sub-agent), `triage_tool` (plain, never an LLM), `index_tool` (plain), `alert_tool` (sub-agent, LLM only to phrase), `report_tool` (plain aggregation + template). The day/night branch is a wall-clock check against a configured shift window, implemented as a Strands **Graph** edge condition deciding whether an event goes to baseline-update logic or to the full triage→alert path — same ingestion/analysis code runs either way.

### 2.4 Baseline computation
For each `(animal_id, behavior_type)`, maintain rolling mean/std of duration & frequency over the last 7–14 **daytime-only** shifts. Night events never feed their own night's baseline — only prior daytime data does, recomputed once at day-end and frozen. `z = (observed − mean)/std`, used both as a rule input and as `baseline_delta_z`. **Cold start (<3 days):** fall back to a species/breed/age population-defaults lookup table, seeded with MammalNet population priors. Separately, Marengo video-to-video similarity (filtered to that animal's metadata) retrieves the nearest daytime clip + distance score for "looks off but no named behavior" anomalies.

### 2.5 Latency & cost budget
**Per 15-min chunk:** Pegasus async analysis of a 15-min video typically completes in low single-digit minutes (repo notes a short clip indexes in ~1–2 min; a 15-min analysis is proportionally longer — https://github.com/jpadams/video-context-graph). TwelveLabs Free plan bills 15 min of the shared 10-hour pool per chunk analyzed; Marengo embed adds to the same pool. GPT-5.6 Terra: a merge call on one chunk's observations + baseline is a few thousand tokens (~$0.01–0.03 at $2.50/1M in, $15/1M out). Neo4j writes are negligible.
**Per night per enclosure (~12h ≈ 48 chunks):** ~12 analysis-hours would exceed the Free 10-hour pool in a single night for one enclosure — so for the demo you MUST pre-index/pre-analyze overnight footage and replay, and for production raise limits via Kyle Cabigon (kc@twelvelabs.io) or use Bedrock's TwelveLabs models. This is the single most important cost constraint (https://docs.twelvelabs.io/docs/get-started/rate-limits).

### 2.6 Failure modes, retries, idempotency
- **Segmenter crash / dropped RTSP** → watcher detects missing sequence number; gap logged as a `DataGap` node so the morning report can say "02:10–02:25 not recorded."
- **Pegasus task failed** (`analyze.task.failed` webhook) → retry with backoff up to N times; after that, fall back to Marengo-only anomaly scan for that chunk and flag "reduced coverage."
- **Idempotency** → deterministic `event_id`; all graph writes are `MERGE`; re-running a chunk replaces its segments (repo pattern).
- **Invalid JSON from Pegasus** → schema-validation guard; on failure, re-prompt once, then drop to Marengo-only.

---

## 3. The Complete Zookeeper End-to-End Journey

**Named example:** keeper **Maria Chen**, animal **"Rex," a 4-year-old male African painted dog** in enclosure **ENC-07**.

**Day 1–7 — Onboarding / learning period.** Rex arrives, is assigned ENC-07's camera. The status board shows Rex's card as **"Baseline: learning (Day 3 of 7)."** No alerts fire. Daytime footage refines his profile: he paces ~4 min/hr in early morning, drinks 6–8×/shift, rests midday. Maria logs context: "still decompressing from transport, anxious at dusk." That note becomes a `CareRecord` flag the Analysis Agent will later cite.

**Day 8 — Shadow mode.** Baseline is now "established," but the system runs in **shadow mode**: overnight it logs what it *would* have flagged without paging anyone. Maria reviews the shadow log each morning for a week and confirms it caught the two real events (a bowl tip, a 12-min pacing bout) and didn't cry wolf.

**Day 15 — Trusted mode, a real night event.** At **02:06:40**, Pegasus flags `pacing` from 02:00–02:14 (14 min continuous) in chunk `enc07_2026-07-30_0200.mp4`, and no `drinking` since 20:30 (6h+). Deterministic triage: `pacing >10min` → MODERATE; the "no water in 6h" clause is close but pacing hasn't hit 20 min, so it stays **MODERATE**. Analysis Agent checks baseline (Rex normally paces ≤4 min/hr → z ≈ 3.1) and care record (dusk-anxiety note, no med side-effect explaining it). Alert fires.

**Maria's phone at 02:15 shows:**
> **🟠 ENC-07 · Rex — welfare check suggested**
> Rex has been pacing for 14 minutes and hasn't visited his water bowl in over 6 hours, which is unusual for him (he normally paces under 5 minutes at a stretch).
> **Tap to watch the 30-second clip →**
> *This is a welfare-check prompt, not a diagnosis.*

**If Maria doesn't acknowledge within 20 minutes:** the alert **escalates** — resends more insistently, then loops in the backup on-call contact (night supervisor). The graph records every send as an `Alert`/`TRIGGERED` edge with `sent_at` and `ack_state`.

**06:00 — Morning briefing (the centerpiece).** Every animal represented, those needing attention sorted to top:
> **Night Briefing — ENC block A — 2026-07-30**
> **① Rex (ENC-07) — FOLLOW UP.** 02:00–02:14 pacing (14 min, ~3σ above his norm); no water 20:30–06:00. [night clip] next to [his typical night: still/resting]. Suggested: welfare check + confirm water access.
> **② Nala (ENC-03) — note.** One bowl tip 23:10, otherwise normal. No action.
> **③ Kito (ENC-05) — normal.** Rested 21:00–05:40, drank 5×. No action.
> *(…every animal listed, normals collapsed…)*
> **Data gaps:** ENC-09 camera offline 03:10–03:25.

**Loop-closing feedback.** Maria checks Rex, finds his water bowl was pushed under the platform. She taps the event and records outcome: **"water access blocked — bowl relocated; no health issue."** That writes an `Outcome` node against the event, which (a) tells the baseline updater this pacing was environmental not pathological, and (b) feeds the trend view.

**Weeks later — vet trend view.** The staff vet opens Rex's multi-week view: a slow rise in average nightly pacing (4→7 min over a month), no single night having crossed HIGH. The GraphRAG query surfaces the trend + linked outcomes, prompting a proactive checkup — the exact slow-moving signal a single night never reveals.

**What a judge sees in 3 minutes:** status board (learning vs established) → trigger a pre-baked night event → phone alert with clip → 20-min no-ack escalation → 06:00 briefing covering every animal → keeper feedback closing the loop → vet trend view. All four sponsor logos light up in the pipeline diagram.

---

## 4. Graph Data Model (Neo4j)

**Node labels & key properties (types):**
- `(:Animal {animal_id STRING PK, name STRING, species STRING, breed STRING, sex STRING, dob DATE, enclosure_id STRING})`
- `(:Enclosure {enclosure_id STRING PK, block STRING, camera_id STRING})`
- `(:Shift {shift_id STRING PK, date DATE, mode STRING /* day|night */, start_ts DATETIME, end_ts DATETIME})`
- `(:Event {event_id STRING PK, type STRING, start_ts DATETIME, end_ts DATETIME, duration_min FLOAT, severity STRING, rule_fired STRING, confidence FLOAT, clip_ref STRING, audio_flag BOOL})`
- `(:BaselineProfile {animal_id STRING, behavior_type STRING, mean FLOAT, std FLOAT, n_shifts INT, updated_at DATETIME})`
- `(:CareRecord {animal_id STRING, med STRING, feeding_schedule STRING, medical_flags LIST, note STRING, logged_by STRING, ts DATETIME})`
- `(:Alert {alert_id STRING PK, severity STRING, sent_at DATETIME, channel STRING, ack_state STRING, escalated BOOL})`
- `(:Outcome {outcome_id STRING PK, resolution STRING, entered_by STRING, ts DATETIME})`
- `(:Clip {clip_id STRING PK, s3_uri STRING, embedding VECTOR<FLOAT32>(512), start_ts DATETIME})`
- `(:DataGap {enclosure_id STRING, start_ts DATETIME, end_ts DATETIME})`

**Relationships (with properties):**
- `(:Animal)-[:PERFORMED]->(:Event)`
- `(:Event)-[:OCCURRED_DURING]->(:Shift)`
- `(:Event)-[:DEVIATES_FROM {z FLOAT}]->(:BaselineProfile)`
- `(:Event)-[:TRIGGERED]->(:Alert)`
- `(:Event)-[:RESOLVED_BY]->(:Outcome)`
- `(:Animal)-[:HAS_BASELINE]->(:BaselineProfile)`
- `(:Animal)-[:HAS_CARE_RECORD]->(:CareRecord)`
- `(:Animal)-[:HOUSED_IN]->(:Enclosure)`
- `(:Event)-[:HAS_CLIP]->(:Clip)`

**Constraints / indexes:** unique constraints on every `*_id`; composite index on `(:BaselineProfile animal_id, behavior_type)`; range index on `Event.start_ts`; **vector index** on `Clip.embedding` (512-dim, cosine) for GraphRAG anomaly retrieval.

**Query PATTERNS (described):**
- **Alert query:** match `(:Animal)-[:PERFORMED]->(e:Event)-[:OCCURRED_DURING]->(s:Shift {mode:'night'})` where `e.severity <> 'NONE'` and `s.date = today`, return ordered by severity rank then `start_ts`.
- **Morning report:** for each Animal, `OPTIONAL MATCH` its night Events + `HAS_BASELINE`, aggregate per-animal day-vs-night deltas so *every* animal appears even with zero events; attach `HAS_CLIP` and any `RESOLVED_BY` outcome.
- **Multi-week trend:** match one Animal's Events over a rolling 30-night window grouped by week, computing weekly mean pacing/inactivity and joining `Outcome` resolutions; combine with a `Clip.embedding` vector search (filtered to that animal) for visual-drift detection — this is the GraphRAG retrieval the vet-facing agent narrates.

---

## 5. What Is Deliberately NOT Automated

**The guarantee: the system never diagnoses, never dispenses medication, never takes any physical action. It only watches, logs, notifies.** This is enforced *architecturally*, not just by a prompt:
- **Severity is decided by deterministic Python (Agent 3), not an LLM.** The LLM cannot escalate or invent urgency; it only attaches context and phrases text. Every alert carries `rule_fired` tracing to an exact human-auditable rule the facility agreed to in advance.
- **The alert schema has no "diagnosis" or "treatment" field.** The alert-phrasing agent's Structured Output is constrained to `{headline, why_unusual, action}` where `action` is drawn from a fixed set (`welfare_check`, `verify_water`, `observe`) — it is structurally impossible for it to output a medication instruction.
- **No actuator tools exist.** The agent tool list contains only read/analyze/notify functions — there is no tool that can open a gate, dispense food, or change the environment. The Neo4j MCP access runs read-only (`NEO4J_READ_ONLY=true`).
- **Human-in-the-loop is mandatory before paging:** shadow mode must be confirmed by staff before the system is allowed to send a single real page.
- **Day shift is never alerted** — humans present are assumed faster than the pipeline; the system only refines baseline and folds in staff-logged context during the day.

---

## 6. Hackathon-Specific Execution Plan

**Pre-bake vs run-live (given TwelveLabs latency & Free-tier 10-hour cap):**
- **Pre-bake:** all overnight footage already uploaded, indexed, and analyzed into TwelveLabs before the demo; Pegasus observation JSON + Marengo embeddings already in Neo4j; baselines already computed from "prior daytime" clips. This avoids blowing the 10-hour Free pool live and avoids multi-minute indexing waits on stage.
- **Run live:** the Strands orchestration, the deterministic triage, the OpenAI merge/phrasing call, the Neo4j GraphRAG morning-report query, the phone alert, and the escalation timer. Optionally run one short (~1 min) clip through Pegasus live to prove the ingestion path is real.

**Faking overnight footage convincingly (datasets, verified):**
- **MammalNet** (Vision-CAIR, CVPR 2023; Chen, Hu, Coker, Berumen, Costelloe, Beery, Rohrbach, Elhoseiny, pp. 13052–13061) — official download links on the repo README: `https://mammalnet.s3.amazonaws.com/trimmed_videos.tar.gz`, `https://mammalnet.s3.amazonaws.com/annotation.tar`, `https://mammalnet.s3.amazonaws.com/full_video.tar.gz` (repo: https://github.com/Vision-CAIR/MammalNet; paper: https://arxiv.org/abs/2306.00576). Confirmed stats: 539 hours, over 18K videos (18,346), 173 mammal categories, 17 orders, 69 families, and **12 behaviors: eat food, drink water, hunt, mate, feed baby, give birth, groom, fight, urinate, defecate, sleep, vomit.** Crucially, MammalNet's labels already include **fight** and **vomit**, which map directly onto your CRITICAL and HIGH triage rules — use these clips as ground-truth positives to prove the pipeline catches real events. Real YouTube zoo/farm/wild footage, so audio tracks are generally intact. (Note: the project page https://mammal-net.github.io still says the dataset "will be made available soon" — the GitHub README is the authoritative source for working links; the project distributes annotations, videos are YouTube-sourced.)
- **Animal Kingdom** (SUTD, CVPR 2022; Ng, Ong, Zheng, Ni, Yeo & Liu, pp. 19023–19034, arXiv:2204.08129) — 50 hours of annotated video, 30K video sequences for fine-grained multi-label action recognition, 33K frames for pose estimation, 850 species across 6 major animal classes; download via Google Form request.
- **WildEarth** safari cams — 24/7 "LIVE at the Waterhole" with real ambient audio, multi-hour YouTube VOD archives (~$10/mo full archive).
- **explore.org** — most cams have sound (sanctuaries/private homes muted for privacy); African Wildlife/Africam run 24/7; archive clips tend to be short highlights (3–10 min).
- **To simulate a specific overnight event:** concatenate a MammalNet "vomit" or "fight" clip into an otherwise calm night VOD, run it through the pre-baked pipeline, and show the single high-signal alert firing against the calm baseline.

**Qualification checklist → evidence:**
- ✓ **Strands** — top-level orchestrator with mixed plain-function + sub-agent tool list, `OpenAIResponsesModel` provider, Graph primitive for the day/night branch.
- ✓ **TwelveLabs** — Pegasus 1.5 schema analysis + Marengo 3.0 metadata-filtered similarity search, visible in the pipeline diagram and one live short-clip call.
- ✓ **OpenAI** — GPT-5.6 Terra (`gpt-5.6-terra`) doing merge/structure + alert phrasing on the Responses API, with Structured Outputs and Compaction.
- ✓ **Neo4j** — Aura graph with vector index; morning report is a live GraphRAG query; cite the NICD 80%-more-truthful study as your rationale.

**Biggest technical risks & mitigations:**
1. **TwelveLabs has no documented animal capability, and its audio scope names only "musical tones, beeping, environmental sounds"** — it may miss animal-specific behaviors and non-speech vocalizations (whining/growling). *Mitigation:* frame animal-behavior/sound detection as an unverified extension validated in shadow mode; lean on Marengo visual-anomaly search (which needs no named label) as a backstop; use MammalNet's labeled fight/vomit clips to empirically measure hit rate before the demo and report the number honestly.
2. **Free-tier 10-hour pool** can't sustain a live full night. *Mitigation:* pre-bake; email Kyle Cabigon to raise limits; or use Bedrock TwelveLabs models.
3. **Pegasus timestamp accuracy is not formally bounded.** *Mitigation:* keep clips attached to every alert so a human verifies in 10 seconds; don't over-trust sub-second offsets.
4. **Enclosure-mate confusion** (which animal is pacing). *Mitigation:* multimodal reference image per animal in the Pegasus prompt; one camera per animal where possible.
5. **Model-string drift** — `gpt-5.6` alias routes to Sol not Terra. *Mitigation:* pin `gpt-5.6-terra` explicitly (repo already does).

---

## 7. What to reuse vs replace from `jpadams/video-context-graph`

**Reuse as-is:** the Strands+OpenAI agent wiring (`app/agent.py`, SSE streaming), the TwelveLabs client (`app/twelvelabs_client.py`, Marengo embed/search + Pegasus analyze), the Neo4j vector client (`app/vector_client.py`), the ingest pipeline shape (`scripts/ingest.py`: index → Pegasus analyze → OpenAI Structured Outputs → Marengo embed 512-dim → Neo4j MERGE), the idempotent re-ingest behavior, the `cypher/schema.cypher` constraints+vector-index pattern, and the `.env` model config (already `gpt-5.6` / `gpt-5.6-terra` / `marengo3.0` / `pegasus1.2`). Agent tools it already ships: `search_video_moments`, `explore_graph`, `twelvelabs_search`, `run_cypher` / `get_graph_schema`. API endpoints already built: `/api/chat/stream`, `/api/search`, `/api/expand`, `/api/cypher`, `/api/schema` (https://github.com/jpadams/video-context-graph).

**Replace:** the ontology (`data/ontology.yaml`) — swap Video/Segment/Entity/Topic for Animal/Enclosure/Shift/Event/BaselineProfile/CareRecord/Alert/Outcome/Clip; the extraction schema — swap generic entities/topics for the behavior-enum `observations[]`; add the deterministic triage engine (repo has none — its agent just answers questions); add the day/night branch, baseline computation, alerting + escalation, and the scheduled morning report; upgrade `PEGASUS_MODEL` to `pegasus1.5` for `time_based_metadata` segmentation (repo defaults to 1.2 because 1.2 is what an index accepts at creation — note this quirk).

**Where its schema differs from yours:** the repo's whole thesis is *cross-video entity MERGE* (same person/object collapses to one node across videos, keyed by normalized name). Yours is *per-animal temporal baselines* — you don't want cross-animal collapse; you want each Animal isolated with its own BaselineProfile, and Events chained to Shifts. Keep the MERGE-idempotency mechanic but re-key it on your `event_id`, not on normalized entity names.

---

## Recommendations

**Stage 1 (first 6 hours) — spine.** Fork `jpadams/video-context-graph`. Keep its TwelveLabs/OpenAI/Neo4j clients. Swap the ontology to the animal model (§4) and the extraction schema to the behavior enum. Get one MammalNet clip flowing end-to-end: Pegasus (`pegasus1.5`, `time_based_metadata`) → GPT-5.6 Terra merge → Neo4j. **Benchmark that changes the plan:** if Pegasus reliably emits your behavior enum on animal clips, proceed; if it returns garbage on animals, pivot to Marengo-similarity-only + GPT-5.6 vision on sampled frames.

**Stage 2 (next 6 hours) — the differentiators.** Build the deterministic triage engine (§2.3), the daytime-only baseline computation with z-scores, the day/night Strands Graph branch, and the alert + 20-min escalation timer. This is what separates you from a generic video-Q&A demo — invest here.

**Stage 3 (next 4 hours) — the demo surface.** Morning briefing as a live GraphRAG Cypher query (every animal represented), the phone alert with attached clip, the vet trend view, and the loop-closing outcome entry. Pre-bake a calm night VOD with a spliced-in MammalNet fight/vomit clip.

**Stage 4 (final polish).** Email Kyle Cabigon to raise TwelveLabs limits. Install the AWS `aws-core` plugin to scaffold S3/Lambda/IAM cleanly. Add AgentCore Runtime deployment if time allows (bonus AWS depth). Rehearse the 3-minute script.

**Thresholds that change recommendations:** if the Free 10-hour pool is exhausted in testing → move to Bedrock TwelveLabs models or get limits raised before demo day. If Pegasus animal-behavior hit rate < ~60% on your MammalNet validation set → demote behavior-enum triage to a secondary signal, make Marengo visual-anomaly the primary detector, and say so on stage.

## Caveats
- **TwelveLabs on animals is unverified.** There is *no* official TwelveLabs documentation or credible third-party example of animal-behavior detection or non-speech animal-sound classification; audio scope is documented only as "musical tones, beeping, environmental sounds" (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio). Whether animal sounds fall under "environmental sounds" is an inference, not documented. Validate empirically; present hit rates honestly.
- **Pegasus timestamp accuracy is not formally published** — only that segments carry start/end times; observed precision is to hundredths of a second but no error bound is guaranteed (https://docs.twelvelabs.io/docs/guides/segment-videos).
- **Neo4j Free-tier limits show a documented source conflict** (FAQ: 200k/400k; some product pages have shown 50k/175k). Cited the FAQ; verify in-console before the demo.
- **Marengo embedding dimension:** Marengo 3.0 product page and the repo indicate 512-dim; older Embed API docs cite 1024-dim for Marengo 2.7. Auto-detect at ingest (repo does this) rather than hard-coding.
- **GPT-5.6 Terra specifics** are drawn from OpenAI's developer docs plus third-party trackers; a few numbers (exact snapshot strings, some pricing edge cases) appear only on aggregator sites (e.g. https://www.requesty.ai/models/openai-responses/gpt-5.6-terra, https://coursiv.io/blog/gpt-5-6-terra) — pin `gpt-5.6-terra` and confirm against https://developers.openai.com/api/docs/models/gpt-5.6-terra at build time.
- **Free-plan hours** are documented inconsistently (10-hour shared pool in current release notes — https://docs.twelvelabs.io/docs/get-started/release-notes — vs "600 minutes" in older pricing FAQ — https://www.twelvelabs.io/pricing) — treat as ~10 hours and confirm in-dashboard.
- This is a **welfare-support** tool, not a medical device; the "never diagnoses/dispenses/acts" boundary is a hard product requirement, not a limitation to engineer around.

---

## Full Source URL List (grouped)

**TwelveLabs**
- https://docs.twelvelabs.io/docs/concepts/models/pegasus
- https://docs.twelvelabs.io/docs/concepts/models/marengo
- https://docs.twelvelabs.io/docs/concepts/models
- https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task
- https://docs.twelvelabs.io/api-reference/analyze-videos
- https://docs.twelvelabs.io/api-reference/any-to-video-search/make-search-request
- https://docs.twelvelabs.io/docs/guides/analyze-videos
- https://docs.twelvelabs.io/docs/guides/segment-videos
- https://docs.twelvelabs.io/docs/guides/create-embeddings/audio
- https://docs.twelvelabs.io/docs/guides/search/entity-search
- https://docs.twelvelabs.io/docs/filtering
- https://docs.twelvelabs.io/v1.3/api-reference/upload-content/direct-uploads/create
- https://docs.twelvelabs.io/sdk-reference/python/upload-content/video-indexing-tasks
- https://docs.twelvelabs.io/docs/webhooks
- https://docs.twelvelabs.io/docs/webhooks-notification-schema
- https://docs.twelvelabs.io/docs/get-started/rate-limits
- https://docs.twelvelabs.io/docs/get-started/release-notes
- https://www.twelvelabs.io/pricing
- https://www.twelvelabs.io/product/embed
- https://www.twelvelabs.io/product/analyze
- https://www.twelvelabs.io/blog/introducing-marengo-2-7
- https://www.twelvelabs.io/blog/marengo-pegasus-on-amazon-bedrock
- https://www.twelvelabs.io/blog/automated-video-data-labeler
- https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html
- https://press.aboutamazon.com/aws/2025/12/twelvelabs-launches-its-most-powerful-video-understanding-model-marengo-3-0-on-twelvelabs-and-amazon-bedrock
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-pegasus.html
- https://aws.amazon.com/blogs/big-data/optimize-multimodal-search-using-the-twelvelabs-embed-api-and-amazon-opensearch-service/

**OpenAI (GPT-5.6 Terra)**
- https://developers.openai.com/api/docs/models/gpt-5.6-terra
- https://developers.openai.com/api/docs/models
- https://openai.com/index/gpt-5-6/
- https://developers.openai.com/api/docs/guides/compaction
- https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling
- https://developers.openai.com/api/docs/guides/conversation-state
- https://developers.openai.com/api/reference/resources/responses/methods/compact
- https://developers.openai.com/cookbook/examples/responses_api/reasoning_items
- https://www.requesty.ai/models/openai-responses/gpt-5.6-terra
- https://coursiv.io/blog/gpt-5-6-terra

**Strands Agents / AWS**
- https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/
- https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/
- https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/
- https://strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/
- https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/
- https://strandsagents.com/docs/user-guide/concepts/model-providers/
- https://strandsagents.com/docs/api/python/strands.models.openai_responses/
- https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/
- https://aws.amazon.com/blogs/machine-learning/strands-agents-sdk-a-technical-deep-dive-into-agent-architectures-and-observability/
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html
- https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/
- https://docs.aws.amazon.com/agent-toolkit/latest/userguide/what-is-agent-toolkit.html
- https://github.com/aws/agent-toolkit-for-aws
- https://github.com/awslabs/agent-plugins
- https://aws.amazon.com/about-aws/whats-new/2026/05/agent-toolkit/

**Neo4j**
- https://neo4j.com/cloud/platform/aura-graph-database/faq/
- https://neo4j.com/docs/aura/managing-instances/vector-optimization/
- https://neo4j.com/docs/aura/aura-agent/
- https://feedback.neo4j.com/changelog
- https://neo4j.com/blog/agentic-ai/study-graphrag-ai-agents-80-percent-more-truthful/
- https://github.com/neo4j/mcp
- https://github.com/neo4j-contrib/mcp-neo4j
- https://pypi.org/project/mcp-neo4j-cypher/
- https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/
- https://medium.com/neo4j/introducing-neo4js-native-vector-data-type-36a4aaa42d4d
- https://checkthat.ai/brands/neo4j/pricing

**Reference repo**
- https://github.com/jpadams/video-context-graph

**Datasets**
- https://github.com/Vision-CAIR/MammalNet
- https://arxiv.org/abs/2306.00576
- https://ar5iv.labs.arxiv.org/html/2306.00576
- https://mammalnet.s3.amazonaws.com/trimmed_videos.tar.gz
- https://mammalnet.s3.amazonaws.com/annotation.tar
- https://mammalnet.s3.amazonaws.com/full_video.tar.gz
- https://cvpr.thecvf.com/virtual/2023/poster/21258
- https://arxiv.org/abs/2204.08129 (Animal Kingdom, CVPR 2022)
- https://www.mdpi.com/1424-8220/24/24/7978 (dog bark/howl classification — separate research, not TwelveLabs)