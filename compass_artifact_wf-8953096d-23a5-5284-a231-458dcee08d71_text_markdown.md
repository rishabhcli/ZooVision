# Overnight Animal-Welfare Monitoring: Technical Architecture & Product Design
## "Hack the Video Agent Context" (AWS/HackerSquad, SF 2026)

## TL;DR
- **Build it as a Strands-orchestrated pipeline where each sponsor is load-bearing:** TwelveLabs Pegasus 1.5 does schema-constrained per-chunk behavior extraction; Marengo 3.0 produces clip embeddings; Neo4j performs the per-animal vector retrieval; and OpenAI GPT-5.6 Luna (via the Strands `OpenAIResponsesModel`) merges/structures evidence and phrases alerts. Deterministic Python alone assigns severity. The reference repo `jpadams/video-context-graph` is a starting point for plumbing, not a drop-in: replace its current model configuration, generic ontology, and search assumptions before relying on it (https://github.com/jpadams/video-context-graph).
- **The load-bearing design decision is the individual baseline + deterministic triage split:** TwelveLabs/OpenAI produce observations; a non-LLM Python rule engine decides urgency against each animal's own daytime-only baseline. This is what makes the system trustworthy and auditable and is your strongest judging differentiator over a generic "ask questions about video" demo.
- **Your biggest technical truth to confront up front:** TwelveLabs has *no documented non-human-animal capability*, and its audio understanding names only "musical tones, beeping, environmental sounds" — not barking/whining/growling (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio). Treat animal-behavior and animal-sound detection as an unverified extension you validate in shadow mode, not a guarantee. This honesty is itself a scoring asset for a welfare product.

## Key Findings

### The four sponsors, current versions, and where each sits
- **TwelveLabs** — Use **Pegasus 1.5** on the direct TwelveLabs API for time-based, schema-constrained segmentation. It is not available on Bedrock. Use **Marengo 3.0** to create 512-dimensional embeddings, then retrieve similar clips with Neo4j's vector index; TwelveLabs does not provide video-to-video search. The Free plan's 600-minute (10-hour) allocation is cumulative, shared, and does not reset. Each segmentation definition multiplies paid duration, so use one rich definition (https://docs.twelvelabs.io/docs/concepts/models/pegasus).
- **OpenAI** — Pin **`gpt-5.6-luna`**, not the bare `gpt-5.6` alias (which routes to Sol) and not Terra. Luna has the same 1.05M-token context and 128K maximum output, supports Chat Completions, Responses, and Batch, and is priced at $0.20/1M input, $0.02/1M cached input, and $1.20/1M output as of 2026-07-30. ZooVision uses the Responses API for its structured merge and phrasing path (https://developers.openai.com/api/docs/models/gpt-5.6-luna).
- **Strands Agents (AWS)** — Use a pinned Graph-based orchestrator with `OpenAIResponsesModel`; model nodes use `structured_output_model=`, not the deprecated `agent.structured_output()`. Graph fan-in has OR semantics, so every join must state its AND condition explicitly (https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/).
- **Neo4j** — Aura Free tier (200k nodes / 400k relationships), native vector index + vector-search-with-filters (GA), official Neo4j MCP server, and the NICD "GraphRAG makes AI agents 80% more truthful" study as your GraphRAG justification (https://neo4j.com/blog/agentic-ai/study-graphrag-ai-agents-80-percent-more-truthful/).

### The reference repo already does most of your plumbing
`jpadams/video-context-graph` (forked from `neo4j-labs/create-context-graph`) is a FastAPI + Strands backend + Next.js/NVL frontend that demonstrates video ingestion, structured outputs, embeddings, Neo4j writes, and a graph UI. Its current defaults are not ZooVision's plan: set the explicit Luna model, replace Pegasus 1.2 with a direct Pegasus 1.5 integration, remove any assumption that a provider can run video-to-video search, and replace the entity/topic ontology with the animal-behavior ontology (https://github.com/jpadams/video-context-graph).

---

## Details

## 1. Sponsor-Maximization Matrix

### 1.1 TwelveLabs — what the product uses, and the advanced features to exploit
**Load-bearing role:** TwelveLabs is the only component that turns raw enclosure video into machine-readable, timestamped behavior — nothing downstream works without it.

**APIs / models used:**
- **Pegasus 1.5 async analysis** — `POST /analyze/tasks` (async, videos up to 2 hours) with `analysis_mode=time_based_metadata` and a `response_format` JSON schema that returns an `observations[]` array. This is the core ingestion call per 15-minute chunk. Model string `pegasus1.5`. Context window 261,120 tokens shared input+output; responses up to 98,304 tokens (https://docs.twelvelabs.io/docs/concepts/models/pegasus, https://docs.twelvelabs.io/api-reference/analyze-videos/create-async-analysis-task).
- **Structured/JSON-schema output** — Pegasus 1.5 was purpose-built for schema-conformant JSON (launch claim: outperforms Gemini 3.1 Pro on aggregated segmentation by 13.1%, fewer invalid-JSON failures — https://www.prweb.com/releases/twelvelabs-launches-pegasus-1-5--turning-raw-video-into-structured-queryable-data-at-scale-302746725.html). This is what lets your rule engine stay deterministic. See also https://docs.twelvelabs.io/docs/get-started/release-notes.
- **Marengo 3.0 embeddings** — create clip embeddings and verify the returned dimension at ingest. Marengo 3.0 is 512-dimensional; Marengo 2.7's 1024-dimensional embeddings are retired and incompatible. Store the vectors on `:Clip` nodes and query Neo4j by cosine distance with an `animal_id` predicate (https://docs.twelvelabs.io/docs/concepts/models/marengo).
- **Retrieval correction** — TwelveLabs any-to-video search accepts text or image queries, not video queries. The per-animal "looks off" backstop is therefore Marengo clip embedding -> Neo4j vector retrieval, never a TwelveLabs video-to-video request.
- **Webhooks** — register an endpoint to receive `analyze.task.ready` / `analyze.task.failed` and `index.task.ready` events instead of polling (https://docs.twelvelabs.io/docs/webhooks, schema at https://docs.twelvelabs.io/docs/webhooks-notification-schema). Webhooks are supported for Search and Analyze but NOT for the Embed API.
- **Upload** — `POST /assets` (direct local upload ≤200MB; URL upload ≤4GB; multipart for larger local files) then index/analyze. A 15-minute 720p chunk is well within limits (https://docs.twelvelabs.io/v1.3/api-reference/upload-content/direct-uploads/create).
- **Audio** — Marengo audio embeddings cover "non-verbal audio (musical tones, beeping, environmental sounds)" and "transcription" (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio).

**Advanced-feature exploitation for higher score:** batch analysis (`POST /analyze/batches`, up to 1,000 requests in one call, requires Pegasus 1.5) can fan out a curated demo reel; use one segment definition with many fields because every additional definition multiplies paid duration; and trial `prompt_v2` reference images per animal only in shadow mode. Animal identity support is unverified.

### 1.2 OpenAI GPT-5.6 Luna — every Key API feature + agentic primitive mapped
**Load-bearing role:** the reasoning layer that merges observations with the animal's baseline/care record and phrases the human-readable alert — but never decides severity.

**Pinned GPT-5.6 Luna facts:** model ID `gpt-5.6-luna` (the bare `gpt-5.6` alias routes to Sol); 1.05M context; 128K maximum output; standard pricing $0.20/1M input, $0.02/1M cached input, and $1.20/1M output; Batch pricing is half of those rates. Luna supports Chat Completions, Responses, and Batch. ZooVision uses Responses with `reasoning.effort: "low"` and strict structured outputs. Keep static instructions and the schema as the exact shared prefix, place chunk-specific evidence last, and measure cache hits from response usage (https://developers.openai.com/api/docs/models/gpt-5.6-luna).

**Four Key API features → concrete placement:**
1. **Multimodal context** → Analysis Agent reasons over Pegasus observation JSON + Neo4j baseline/care context in one call; optionally attach a key frame from the clip.
2. **Structured outputs** → Analysis Agent emits the `events[]` contract (JSON-schema-constrained), and the alert-phrasing agent emits `{headline, why_unusual, action}` so no free-text parsing downstream.
3. **Function calling** → agent tools `query_baseline(animal_id, behavior)`, `query_care_record(animal_id)`, `search_scene(animal_id, text)`, `run_cypher(read_only)`.
4. **Compaction** → use server-side compaction only for bounded investigations, not as an unbounded overnight session. Production real-time calls set `store=false` to avoid Responses application-state retention. Zero Data Retention remains a separate, approval-gated control; only use that label after the account is approved (https://developers.openai.com/api/docs/guides/compaction).

**Three Advanced agentic primitives → concrete placement:**
1. **Programmatic tool calling** → the morning-report agent writes an in-runtime program that batches per-animal graph lookups, joins Event+Baseline deltas, dedups, and returns only the evidence rows (https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling).
2. **Multi-agent** → only use specialists where an evaluation proves they improve the result; the fixed, auditable Graph remains the controller and never delegates triage.
3. **Persisted reasoning** → keep `reasoning.encrypted_content` / `reasoning.context: "all_turns"` across the multi-step 2am investigation of one animal so each new chunk is not an isolated prompt (https://developers.openai.com/api/docs/guides/conversation-state).

### 1.3 Strands Agents — genuinely load-bearing orchestration
**Role:** the top-level orchestrator whose tool list mixes plain functions (deterministic) and sub-agents (LLM), exactly as your design specifies.

- **Agents-as-tools** — pass a sub-agent directly in the `tools=[]` array; the SDK converts it to a tool (https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/).
- **Multi-agent primitives** — Graph (deterministic directed orchestration via `GraphBuilder`), Swarm (autonomous handoffs), Workflow (task pipeline from `strands-agents-tools`). For your fixed day/night branch, use **Graph** (deterministic path) rather than Swarm, because your execution path is known in advance and you want auditable, low-token coordination (https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/, https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/).
- **OpenAI provider** — `strands.models.openai_responses.OpenAIResponsesModel` points Strands at explicit `gpt-5.6-luna` on the Responses API. Bedrock Mantle is a real optional routing path, but its OpenAI GPT-5.6 model configuration, context limit, availability, and quotas must be integration-tested before it becomes the primary route (https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/, https://strandsagents.com/docs/api/python/strands.models.openai_responses/).
- **AgentCore path** — deploy per-segment orchestration to Amazon Bedrock AgentCore Runtime only after the local path is verified. Runtime supports long-running work up to 8 hours, but ZooVision must not hold a 12-hour shift or a 20-minute acknowledgement timer open in one agent session. Persist continuity in Neo4j and run timers in EventBridge Scheduler (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html).
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
Enclosure cameras are RTSP/ONVIF. TwelveLabs has no live-stream endpoint, so a **segmenter** (ffmpeg segment muxer) produces ~15-minute closed MP4 segments with reset timestamps and strftime filenames like `enc07_2026-07-30_0200.mp4`. An EventBridge-routed S3 ObjectCreated watcher fires when a segment closes and hands the object to the ingestion node. Pegasus accepts 4-second to 2-hour video, 360x360 to 5184x2160 resolution, 1:1 to 2.4:1 aspect ratios, and files up to 2 GB; a 15-minute 720p clip is within those bounds (https://docs.twelvelabs.io/docs/concepts/models/pegasus).

**Timestamp reconciliation:** Pegasus returns times relative to each chunk (observed precision to hundredths of a second, e.g. `6.50s`). The ingestion layer offsets every `start_time`/`end_time` by the chunk's wall-clock `chunk_start_ts` (parsed from the strftime filename) before anything is written downstream, so a behavior at 400s into `enc07_2026-07-30_0200.mp4` becomes `02:06:40`. Note: TwelveLabs publishes no formal timestamp-accuracy bound, only that segments carry start/end times (https://docs.twelvelabs.io/docs/guides/segment-videos) — treat sub-second precision as best-effort, not guaranteed.

### 2.2 Storage layout (S3)
- `s3://welfare-raw/{facility}/{enclosure_id}/{yyyy}/{mm}/{dd}/{enclosure}_{ts}.mp4` — raw 15-min chunks, 7-day retention (lifecycle rule).
- `s3://welfare-clips/{animal_id}/{event_id}.mp4` — extracted alert clips (ffmpeg cut on offset event start−5s to end+5s), 90-day retention.
- `s3://welfare-analysis/{animal_id}/{chunk_id}.json` — raw Pegasus observation JSON, 30-day retention.
Keep raw video, extracted clips, and analysis artifacts in separate buckets with explicit lifecycle rules. Pegasus 1.5 accepts an asset or URL directly and does not need an index. Any optional TwelveLabs index has its own retention; its Free-plan expiry is not a substitute for the S3 policy.

### 2.3 The agents in sequence (with endpoints & models)
1. **Node 1 — Ingestion (TwelveLabs, no LLM).** A `MultiAgentBase` graph node wraps explicit Python. Upload/poll until the asset is ready, then call the direct `POST /analyze/tasks` API with `model_name=pegasus1.5`, `analysis_mode=time_based_metadata`, and `response_format.type="segment_definitions"`. Use one rich segment definition. Receive `analyze.task.ready` through a verified webhook or bounded polling. Validate the result at the boundary and offset every relative timestamp by `chunk_start_ts`. Emit an observation contract with a constrained behavior enum; never treat a provider's free text as an event. In parallel, request the Marengo 3.0 embedding and store its returned dimension with the vector.
2. **Node 2 — Analysis (OpenAI GPT-5.6 Luna, Responses API).** A Strands agent with `structured_output_model=` first reads `BaselineProfile` and `CareRecord` through read-only tools. It merges and normalizes evidence only, emitting `events[]` with source chunk, wall-clock timestamps, behavior, confidence, and facts. Python computes `duration_min` and `baseline_delta_z`; Luna may repeat these supplied values but does not calculate or interpret urgency.
3. **Agent 3 — Rule/Triage (deterministic Python, NOT an LLM).** First-match-wins: `fighting`→CRITICAL; `escape_attempt`→CRITICAL; `vomiting`→HIGH; `pacing >20min AND no water contact within 6h`→HIGH; `pacing >10min`→MODERATE; `inactivity > baseline+2σ`→MODERATE; `baseline_delta_z > 2.5`→MODERATE; `water_bowl_tipped`→LOW; else NONE. Output always carries `rule_fired`.
4. **Agent 4 — Indexing (Neo4j).** Idempotent `MERGE` writes keyed on `event_id = hash(animal_id, chunk_id, start_ts, behavior)` so reprocessing never duplicates. Graph writes described in §4.
5. **Node 5 — Alert.** Fires only when `severity != NONE AND shift == night`; day-mode events only log and refine daytime baseline. The application writes an `Alert` node linked `TRIGGERED` with `sent_at`, `channel`, `ack_state`, and a clip reference before delivery. Luna may phrase the factual text from the already-fixed severity and constrained action. Slack is the demo channel; a phone provider is behind the same notifier interface for a separately verified production path.
6. **Node 6 — Reporting.** EventBridge Scheduler invokes a shift-boundary aggregation job. It uses one query per animal joining events, baselines, data gaps, and outcomes so every monitored animal appears.

**Strands orchestration shape:** the top-level `Graph` uses `MultiAgentBase` wrappers for deterministic Python nodes and named `Agent` objects for the two constrained Luna calls. The day/night branch is a wall-clock check against a configured shift window. Graph fan-in is OR by default, so an explicit AND condition guards every join (for example, requiring both a validated Pegasus result and a Marengo result). Use a per-segment graph invocation with Neo4j as durable continuity; do not keep a shift-long agent session alive.

### 2.4 Baseline computation
For each `(animal_id, behavior_type)`, maintain rolling mean/std of duration and frequency over the last 7-14 **daytime-only** shifts. Night events never feed their own night's baseline; recompute at day-end and freeze before the next night. `z = (observed - mean) / std` is deterministic rule input. **Cold start (<3 days):** record an insufficient-baseline state and require shadow review rather than deriving an urgent decision from a generic population prior. Separately, compare the current Marengo clip embedding with prior daytime embeddings in Neo4j, filtered by `animal_id`; a distant match is context for a reviewer, never a triage rule by itself.

### 2.5 Latency & cost budget
**Per 15-minute chunk:** provider latency must be measured in the target account. The TwelveLabs Free plan consumes its 600-minute lifetime allowance across indexing and analysis; never plan on a full live night. Paid Pegasus segmentation charges video duration multiplied by the number of segment definitions, so one 15-minute chunk with three definitions is 45 billable minutes. Luna's merge costs are low but must be measured with production prompts and output caps.
**Representative 6-camera night (288 merge calls):** at 7,000 input and 700 output tokens per call, prompt caching plus the Luna Batch API estimates about **$0.21** for the merge path. Luna's Tier-1 batch queue holds 5M tokens, enough for the approximately 2M-token workload; Terra's 1.5M limit would reject it. Batch is appropriate only for synthetic or consented demo footage because Batch and Files are not zero-data-retention eligible. Production uses bounded, real-time `store=false` Responses calls, and adopts Zero Data Retention only after approval; that path is more expensive and must be costed separately.

### 2.6 Failure modes, retries, idempotency
- **Segmenter crash / dropped RTSP** → watcher detects missing sequence number; gap logged as a `DataGap` node so the morning report can say "02:10–02:25 not recorded."
- **Pegasus task failed** (`analyze.task.failed` webhook) → retry under a bounded, observable policy. After exhaustion, write a `DataGap` with the failure details and do not synthesize an event or substitute a semantic conclusion from embeddings.
- **Idempotency** → deterministic `event_id`; all graph writes are `MERGE`; re-running a chunk replaces its segments (repo pattern).
- **Invalid or incomplete Pegasus output** → schema-validation guard, then one bounded retry. On a second failure, persist a `DataGap` and its source chunk reference; the triage and alert paths do not run.

---

## 3. The Complete Zookeeper End-to-End Journey

**Named example:** keeper **Maria Chen**, animal **"Rex," a 4-year-old male African painted dog** in enclosure **ENC-07**.

**Day 1–7 — Onboarding / learning period.** Rex arrives, is assigned ENC-07's camera. The status board shows Rex's card as **"Baseline: learning (Day 3 of 7)."** No alerts fire. Daytime footage refines his profile: he paces ~4 min/hr in early morning, drinks 6–8×/shift, rests midday. Maria logs context: "still decompressing from transport, anxious at dusk." That note becomes a `CareRecord` flag the Analysis Agent will later cite.

**Day 8 — Shadow mode.** Baseline is now "established," but the system runs in **shadow mode**: overnight it logs what it *would* have flagged without paging anyone. Maria reviews the shadow log each morning for a week and confirms it caught the two real events (a bowl tip, a 12-min pacing bout) and didn't cry wolf.

**Day 15 — Trusted mode, a real night event.** At **02:06:40**, Pegasus flags `pacing` from 02:00–02:14 (14 min continuous) in chunk `enc07_2026-07-30_0200.mp4`, and no `drinking` since 20:30 (6h+). Deterministic triage: `pacing >10min` → MODERATE; the "no water in 6h" clause is close but pacing hasn't hit 20 min, so it stays **MODERATE**. Analysis Agent checks baseline (Rex normally paces ≤4 min/hr → z ≈ 3.1) and care record (dusk-anxiety note, no med side-effect explaining it). Alert fires.

**Maria's Slack alert at 02:15 shows:**
> **ENC-07 / Rex - welfare check suggested**
> Rex has been pacing for 14 minutes and hasn't visited his water bowl in over 6 hours, which is unusual for him (he normally paces under 5 minutes at a stretch).
> **Tap to watch the 30-second clip →**
> *This is a welfare-check prompt, not a diagnosis.*

**If Maria doesn't acknowledge within 20 minutes:** an EventBridge Scheduler one-time schedule rechecks the persisted acknowledgement state before escalating to the backup on-call contact. The schedule is created with `ActionAfterCompletion: DELETE` and deleted on acknowledgement. The graph records every send as an `Alert`/`TRIGGERED` edge with `sent_at` and `ack_state`. SMS is not a hackathon assumption: US AWS SMS registration cannot be completed on that timeline.

**06:00 — Morning briefing (the centerpiece).** Every animal represented, those needing attention sorted to top:
> **Night Briefing — ENC block A — 2026-07-30**
> **① Rex (ENC-07) — FOLLOW UP.** 02:00–02:14 pacing (14 min, ~3σ above his norm); no water 20:30–06:00. [night clip] next to [his typical night: still/resting]. Suggested: welfare check + confirm water access.
> **② Nala (ENC-03) — note.** One bowl tip 23:10, otherwise normal. No action.
> **③ Kito (ENC-05) — normal.** Rested 21:00–05:40, drank 5×. No action.
> *(…every animal listed, normals collapsed…)*
> **Data gaps:** ENC-09 camera offline 03:10–03:25.

**Loop-closing feedback.** Maria checks Rex, finds his water bowl was pushed under the platform. She taps the event and records outcome: **"water access blocked — bowl relocated; no health issue."** That writes an `Outcome` node against the event, which (a) tells the baseline updater this pacing was environmental not pathological, and (b) feeds the trend view.

**Weeks later — vet trend view.** The staff vet opens Rex's multi-week view: a slow rise in average nightly pacing (4→7 min over a month), no single night having crossed HIGH. The GraphRAG query surfaces the trend + linked outcomes, prompting a proactive checkup — the exact slow-moving signal a single night never reveals.

**What a judge sees in 3 minutes:** status board (learning vs established) -> trigger a pre-baked night event -> Slack alert with clip -> acknowledgement state and pending escalation -> 06:00 briefing covering every animal -> keeper feedback closing the loop -> vet trend view. All four sponsor roles are visible in the pipeline diagram.

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
- **No actuator tools exist.** The agent tool list contains only read/analyze/notify functions; there is no tool that can open a gate, dispense food, or change the environment. Neo4j MCP access is read-only and all graph mutation stays in application-owned Python.
- **The boundary is enforced outside the agent.** When AgentCore Gateway is deployed, a Cedar AgentCore Policy allows only the declared read/analyze/notify routes and denies every actuator or write-capable route. Policy decisions are auditable in CloudWatch. This supplements, rather than replaces, least-privilege IAM and application checks.
- **Human-in-the-loop is mandatory before paging:** shadow mode must be confirmed by staff before the system is allowed to send a single real page.
- **Day shift is never alerted** — humans present are assumed faster than the pipeline; the system only refines baseline and folds in staff-logged context during the day.

---

## 6. Hackathon-Specific Execution Plan

**Pre-bake vs run-live (given TwelveLabs latency and its 600-minute lifetime Free cap):**
- **Pre-bake:** all overnight demo footage is already uploaded and analyzed through Pegasus 1.5; the validated observation JSON and Marengo embeddings are already in Neo4j; baselines come from separate daytime clips. This avoids spending the whole Free allowance and removes multi-minute provider waits from the demo.
- **Run live:** the Strands graph, deterministic triage, the Luna merge/phrasing call, the Neo4j morning-report query, the Slack alert, acknowledgement-state mutation, and the EventBridge escalation schedule. One short direct Pegasus 1.5 call is optional proof only after it is tested against the same schema.

**Faking overnight footage convincingly (datasets, verified):**
- **MammalNet** (Vision-CAIR, CVPR 2023; Chen, Hu, Coker, Berumen, Costelloe, Beery, Rohrbach, Elhoseiny, pp. 13052–13061) — official download links on the repo README: `https://mammalnet.s3.amazonaws.com/trimmed_videos.tar.gz`, `https://mammalnet.s3.amazonaws.com/annotation.tar`, `https://mammalnet.s3.amazonaws.com/full_video.tar.gz` (repo: https://github.com/Vision-CAIR/MammalNet; paper: https://arxiv.org/abs/2306.00576). Confirmed stats: 539 hours, over 18K videos (18,346), 173 mammal categories, 17 orders, 69 families, and **12 behaviors: eat food, drink water, hunt, mate, feed baby, give birth, groom, fight, urinate, defecate, sleep, vomit.** Crucially, MammalNet's labels already include **fight** and **vomit**, which map directly onto your CRITICAL and HIGH triage rules — use these clips as ground-truth positives to prove the pipeline catches real events. Real YouTube zoo/farm/wild footage, so audio tracks are generally intact. (Note: the project page https://mammal-net.github.io still says the dataset "will be made available soon" — the GitHub README is the authoritative source for working links; the project distributes annotations, videos are YouTube-sourced.)
- **Animal Kingdom** (SUTD, CVPR 2022; Ng, Ong, Zheng, Ni, Yeo & Liu, pp. 19023–19034, arXiv:2204.08129) — 50 hours of annotated video, 30K video sequences for fine-grained multi-label action recognition, 33K frames for pose estimation, 850 species across 6 major animal classes; download via Google Form request.
- **WildEarth** safari cams — 24/7 "LIVE at the Waterhole" with real ambient audio, multi-hour YouTube VOD archives (~$10/mo full archive).
- **explore.org** — most cams have sound (sanctuaries/private homes muted for privacy); African Wildlife/Africam run 24/7; archive clips tend to be short highlights (3–10 min).
- **To simulate a specific overnight event:** concatenate a MammalNet "vomit" or "fight" clip into an otherwise calm night VOD, run it through the pre-baked pipeline, and show the single high-signal alert firing against the calm baseline.

**Qualification checklist → evidence:**
- ✓ **Strands** — top-level Graph with deterministic `MultiAgentBase` nodes and constrained agents, `OpenAIResponsesModel`, explicit fan-in guards, and a day/night branch.
- ✓ **TwelveLabs** — direct Pegasus 1.5 schema segmentation and Marengo 3.0 embeddings, visible in the pipeline diagram and optionally in one tested short-clip call.
- ✓ **OpenAI** — GPT-5.6 Luna (`gpt-5.6-luna`) performing the constrained merge and alert phrasing on the Responses API. Production requests use `store=false`; Batch is limited to the consented/synthetic demo data path, and Zero Data Retention is not claimed until approved.
- ✓ **Neo4j** — Aura graph with vector index; morning report is a live GraphRAG query; cite the NICD 80%-more-truthful study as your rationale.

**Biggest technical risks & mitigations:**
1. **TwelveLabs has no documented animal capability, and its audio scope names only "musical tones, beeping, environmental sounds"** — it may miss animal-specific behaviors and non-speech vocalizations. *Mitigation:* frame animal-behavior/sound detection as an unverified extension validated in shadow mode; use labeled footage to measure hit rate and report the number honestly. An embedding-distance result is review context, not a rule-engine backstop.
2. **The Free-tier 600-minute pool** cannot sustain a live full night. *Mitigation:* pre-bake a short demo reel, use a documented paid tier or the enterprise contact route for production capacity, and keep Pegasus 1.5 on the direct API. Bedrock Pegasus 1.2 is not an equivalent segmentation fallback.
3. **Pegasus timestamp accuracy is not formally bounded.** *Mitigation:* keep clips attached to every alert so a human verifies in 10 seconds; don't over-trust sub-second offsets.
4. **Enclosure-mate confusion** (which animal is pacing). *Mitigation:* multimodal reference image per animal in the Pegasus prompt; one camera per animal where possible.
5. **Model-string drift** — `gpt-5.6` routes to Sol, not Luna. *Mitigation:* pin `gpt-5.6-luna` explicitly and log the model ID with each provider result.

---

## 7. What to reuse vs replace from `jpadams/video-context-graph`

**Reuse selectively:** the Strands+OpenAI wiring, SSE streaming, Neo4j vector client, ingest-pipeline shape, idempotent re-ingest behavior, constraints/vector-index pattern, and graph UI are useful starting points. Treat every provider wrapper and model default as code to inspect and test, not as production truth. Retain `MERGE` mechanics only after the ZooVision stable IDs and all constraints are defined (https://github.com/jpadams/video-context-graph).

**Replace:** the ontology (`data/ontology.yaml`), generic extraction schema, deterministic triage engine, day/night branch, baseline computation, alerting/acknowledgement/escalation, scheduled report, and current model configuration. Implement direct Pegasus 1.5 segmentation with `time_based_metadata`; do not attempt to configure Pegasus 1.5 into a TwelveLabs index. Set the OpenAI model to explicit `gpt-5.6-luna`, and implement embedding retrieval in Neo4j rather than through a provider video-search call.

**Where its schema differs from yours:** the repo's whole thesis is *cross-video entity MERGE* (same person/object collapses to one node across videos, keyed by normalized name). Yours is *per-animal temporal baselines* — you don't want cross-animal collapse; you want each Animal isolated with its own BaselineProfile, and Events chained to Shifts. Keep the MERGE-idempotency mechanic but re-key it on your `event_id`, not on normalized entity names.

---

## Recommendations

**Stage 1 (first 6 hours) - spine.** Fork `jpadams/video-context-graph` selectively. Replace the ontology and extraction schema; implement direct Pegasus 1.5 `time_based_metadata` with one segment definition; validate the returned contract; then send only validated evidence to `gpt-5.6-luna` and Neo4j. Test at least one labelled clip end-to-end before adding any live demo surface. **Benchmark that changes the plan:** if Pegasus does not reliably emit the required behavior evidence on animal clips, keep the feature in shadow mode and do not enable automatic pages. A Marengo distance score or an LLM reading sampled frames is not a substitute for deterministic evidence.

**Stage 2 (next 6 hours) — the differentiators.** Build the deterministic triage engine (§2.3), the daytime-only baseline computation with z-scores, the day/night Strands Graph branch, and the alert + 20-min escalation timer. This is what separates you from a generic video-Q&A demo — invest here.

**Stage 3 (next 4 hours) - the demo surface.** Build the morning briefing as a live GraphRAG Cypher query that includes every animal, a Slack alert with an authenticated clip link, acknowledgement state plus a pending EventBridge escalation, the trend view, and the loop-closing outcome entry. Pre-bake a calm night VOD with a spliced-in MammalNet fight/vomit clip only where its license permits this use.

**Stage 4 (final polish).** Use TwelveLabs' documented tier/enterprise contact route for capacity, install the AWS `aws-core` plugin to scaffold S3/Lambda/IAM cleanly, and add AgentCore Runtime only after a real deployment smoke test. Rehearse the 3-minute script with a visible distinction between pre-baked evidence and the components that run live.

**Thresholds that change recommendations:** if the 600-minute Free allocation is exhausted, use a curated pre-baked demo reel or a documented paid capacity path; do not substitute Bedrock Pegasus 1.2 for the Pegasus 1.5 segmentation contract. If Pegasus animal-behavior performance is inadequate on the labelled validation set, preserve the evidence and report the gap, but do not promote embeddings or a model-generated severity estimate into the rule engine.

## Caveats
- **TwelveLabs on animals is unverified.** There is *no* official TwelveLabs documentation or credible third-party example of animal-behavior detection or non-speech animal-sound classification; audio scope is documented only as "musical tones, beeping, environmental sounds" (https://docs.twelvelabs.io/docs/guides/create-embeddings/audio). Whether animal sounds fall under "environmental sounds" is an inference, not documented. Validate empirically; present hit rates honestly.
- **Pegasus timestamp accuracy is not formally published** — only that segments carry start/end times; observed precision is to hundredths of a second but no error bound is guaranteed (https://docs.twelvelabs.io/docs/guides/segment-videos).
- **Neo4j Free-tier limits show a documented source conflict** (FAQ: 200k/400k; some product pages have shown 50k/175k). Cited the FAQ; verify in-console before the demo.
- **Marengo embedding dimension:** Marengo 3.0 product page and the repo indicate 512-dim; older Embed API docs cite 1024-dim for Marengo 2.7. Auto-detect at ingest (repo does this) rather than hard-coding.
- **Luna availability, prices, and limits can change.** Pin `gpt-5.6-luna` explicitly and re-check the first-party model and pricing pages at build time. The stated $0.21 Batch estimate is illustrative, depends on the prompt/output assumptions, and is not a production privacy posture.
- **Batch and Files are not zero-data-retention eligible.** Restrict Batch to synthetic or explicitly consented demo footage. Use real-time `store=false` Responses calls for sensitive production data, and obtain Zero Data Retention approval before claiming that protection.
- **Free-plan minutes are a single 600-minute (10-hour) cumulative allowance, not competing values.** Confirm the account dashboard before scheduling any live work.
- **Pegasus 1.5 is direct-API only.** Bedrock hosts Pegasus 1.2 and Marengo 3.0, but Pegasus 1.2 lacks the `time_based_metadata` / segment-definition contract used here.
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

**OpenAI (GPT-5.6 Luna)**
- https://developers.openai.com/api/docs/models/gpt-5.6-luna
- https://developers.openai.com/api/docs/models
- https://openai.com/index/gpt-5-6/
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/compaction
- https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling
- https://developers.openai.com/api/docs/guides/conversation-state
- https://developers.openai.com/api/docs/guides/batch
- https://developers.openai.com/api/docs/guides/your-data
- https://developers.openai.com/api/reference/resources/batches/methods/create
- https://developers.openai.com/api/reference/resources/responses/methods/compact

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
