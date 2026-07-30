# OpenAI — ZooVision Sponsor Reference

> **Researched:** 2026-07-30 · **Verification status:** `gpt-5.6-terra` **VERIFIED REAL** on first-party docs (model page + models index both 200 OK). All 7 brief-claimed `developers.openai.com` URLs resolve. **However the brief's pricing is stale by one day** — OpenAI cut Terra 20% and Luna 80% on 2026-07-30 (today). Two sibling variants the brief never mentions (`gpt-5.6-sol`, `gpt-5.6-luna`) change ZooVision's cost architecture materially.
> **Role in ZooVision:** Schema-constrained merge of TwelveLabs Pegasus observations + Neo4j baseline context into a strict `events[]` contract; `{headline, why_unusual, action}` alert phrasing; morning GraphRAG briefing; multi-chunk overnight investigation. **Never decides severity** — deterministic Python owns that.

---

## 1. Snapshot

| | |
|---|---|
| **Model pinned** | `gpt-5.6-terra` — **confirmed real**, documented at `developers.openai.com/api/docs/models/gpt-5.6-terra` (HTTP 200) |
| **Bare alias** | `gpt-5.6` → **`gpt-5.6-sol`**, *not* Terra. Verbatim: *"The `gpt-5.6` alias routes requests to GPT-5.6 Sol."* Never ship the bare alias. |
| **Context** | 1,050,000 token context window · **max *input* 922,000** · max output 128,000 |
| **Pricing (as of today)** | **$2.00 / 1M input · $0.20 / 1M cached input · $12.00 / 1M output** (was $2.50/$15 until 2026-07-30) |
| **Long-context cliff** | Prompts **>272K input tokens** → *"2x input and 1.5x output for the full request"* = $4.00/$18.00 |
| **Knowledge cutoff** | Feb 16, 2026 (all three variants) |
| **API surface** | Chat Completions **+** Responses **+** Batch (all three supported first-party). Responses-only via AWS Bedrock. |
| **SDK** | `openai==2.51.0` (released 2026-07-30, requires Python ≥3.10) |
| **Key risk #1** | **272K long-context cliff** — the multi-chunk investigation agent can cross it and double the bill *for the entire request*. Mitigate with `context_management` compaction. |
| **Key risk #2** | **Batch API is NOT ZDR-eligible.** ZooVision's biggest cost win (50% off) directly conflicts with a zero-retention posture for sensitive animal-care footage. |
| **Key risk #3** | **Terra Tier-1 batch queue limit is 1.5M tokens** — smaller than one night of ZooVision chunks (~2M). Luna's Tier-1 limit is 5M. |

---

## 2. Model lineup & which one ZooVision should pin (as of July 2026)

The brief pinned Terra for everything. **That is the wrong call for the high-volume path.** There are three variants, all with identical 1.05M context / 128K output / Feb 16 2026 cutoff, differing only in price and capability:

| Model ID | Positioning (verbatim from models index) | Input | Cached in | Output | Long-ctx in/out |
|---|---|---|---|---|---|
| `gpt-5.6-sol` | *"Frontier model for complex professional work"* | $5.00 | $0.50 | $30.00 | $10.00 / $45.00 |
| `gpt-5.6-terra` | *"GPT-5.6 model that balances intelligence and cost"* | **$2.00** | **$0.20** | **$12.00** | $4.00 / $18.00 |
| `gpt-5.6-luna` | *"GPT-5.6 model optimized for cost-sensitive workloads"* | **$0.20** | **$0.02** | **$1.20** | $0.40 / $1.80 |

Aliases: `gpt-5.6` → Sol. Terra and Luna have **no alias** — you must name them explicitly. Each has exactly one snapshot, identical to the model ID (no dated snapshots like `-2026-07-09`).

OpenAI's own `latest-model` guidance page: Sol is *"the model for flagship capability"*, Terra *"strong performance at a lower price"*, Luna *"efficient, high-volume workloads."*

### Recommended split for ZooVision

| ZooVision agent | Model | Why |
|---|---|---|
| **Chunk merge** (Pegasus obs + Neo4j baseline → `events[]`) — ~288 calls/night | **`gpt-5.6-luna`** | 10× cheaper than Terra. The task is schema-filling over pre-extracted structured input, not open reasoning. Luna supports `structured_outputs` + `function_calling` + `image_input`. Set `reasoning.effort: "low"`. |
| **Alert phrasing** (`{headline, why_unusual, action}`) | **`gpt-5.6-luna`** | Tiny, latency-sensitive, no judgment (severity already assigned by Python). `reasoning.effort: "none"` or `"low"`. |
| **Overnight investigation** (dozens of chunks, multi-step) | **`gpt-5.6-terra`** | Needs real cross-chunk reasoning. `reasoning.effort: "high"` + compaction. |
| **06:00 GraphRAG morning briefing** | **`gpt-5.6-terra`** | Synthesis quality matters, runs once/night, cost irrelevant at 1×/day. |
| Escalate to `sol` | only if Terra demonstrably fails the investigation eval | 2.5× Terra's price for a once-a-night call is affordable but unnecessary until proven. |

> **Do not pin Terra for the 288-call merge path.** Luna at $0.20/$1.20 makes that entire stage cost ~$0.32/night under Batch. See §7.

---

## 3. Release timeline / what's new

| Date | Event | Source |
|---|---|---|
| **2026-06-26** | GPT-5.6 limited preview to ~20 government-approved orgs | third-party (Neowin) |
| **2026-07-09** | **GA of the GPT-5.6 family: Sol, Terra, Luna.** Launch pricing Sol $5/$30, **Terra $2.50/$15**, Luna $1/$6. Shipped alongside: Programmatic Tool Calling, explicit prompt-cache controls, persisted reasoning, Multi-agent orchestration (beta) in the Responses API, and image `detail: "original"`. | OpenAI changelog (first-party) + Simon Willison |
| **2026-07-13** | GPT-5.6 Sol/Terra/Luna GA **on Amazon Bedrock** via the `bedrock-mantle` endpoint | AWS model card + AWS What's New |
| **2026-07-30 (today)** | **Price cut: Luna −80%, Terra −20%. Sol unchanged.** Terra → $2.00/$12.00; Luna → $0.20/$1.20. Also: **"Fast mode"** introduced, replacing Priority Processing — *"up to 2.5× faster speeds than standard processing at twice the price."* | OpenAI changelog (first-party) — verbatim: *"GPT-5.6 Luna costs 80% less, while GPT-5.6 Terra costs 20% less."* |
| **2026-07-30** | `openai` Python SDK **2.51.0** released | PyPI JSON API |

**The brief was written against 2026-07-09 launch pricing.** It is one day stale. Every cost figure in the brief is 20% too high.

---

## 4. Responses API surface ZooVision calls

Confirmed top-level `POST /v1/responses` parameters (from the API reference): `input`, `include`, `background`, `context_management` (array of objects), `conversation`. Confirmed `include` enum verbatim:

```
"file_search_call.results", "web_search_call.results", "web_search_call.action.sources",
"message.input_image.image_url", "computer_call_output.output.image_url",
"code_interpreter_call.outputs", "reasoning.encrypted_content", "message.output_text.logprobs"
```

### 4.1 Structured-output merge call (the core ZooVision contract)

Strict structured outputs use `text.format` with `type: "json_schema"` — **not** the legacy `response_format`.

```python
from openai import OpenAI

client = OpenAI()

EVENTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["events"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                # strict:true requires EVERY property listed in `required`.
                "required": [
                    "animal_id", "behavior", "start_ts", "end_ts",
                    "confidence", "deviates_from_baseline", "baseline_note",
                ],
                "properties": {
                    "animal_id": {"type": "string"},
                    "behavior": {
                        "type": "string",
                        "enum": ["pacing", "lethargy", "not_visible", "aggression",
                                 "abnormal_gait", "vocalizing", "feeding", "resting"],
                    },
                    "start_ts": {"type": "number", "description": "seconds from segment start"},
                    "end_ts": {"type": "number"},
                    "confidence": {"type": "number"},
                    "deviates_from_baseline": {"type": "boolean"},
                    # Optional field pattern under strict:true -> nullable union, NOT omission.
                    "baseline_note": {"type": ["string", "null"]},
                },
            },
        }
    },
}

resp = client.responses.create(
    model="gpt-5.6-luna",                       # high-volume merge path
    instructions=SYSTEM_PROMPT,                 # STATIC -> cacheable prefix
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": pegasus_observations_json},
        {"type": "input_text", "text": neo4j_baseline_context_json},
    ]}],
    text={"format": {
        "type": "json_schema",
        "name": "zoovision_events",
        "schema": EVENTS_SCHEMA,
        "strict": True,
    }},
    reasoning={"effort": "low"},
    max_output_tokens=4096,
    prompt_cache_key="zoovision-merge-v1",      # improves cache hit rate
    store=False,                                # ZDR-friendly
)

events = resp.output_text  # JSON string matching EVENTS_SCHEMA
```

Typed alternative — `client.responses.parse(..., text_format=PydanticModel)` returns `.parsed` on each output content item, and surfaces refusals as a distinct `{"type": "refusal"}` content item.

### 4.2 Alert phrasing (severity already fixed by Python)

```python
resp = client.responses.create(
    model="gpt-5.6-luna",
    instructions=(
        "You phrase animal-welfare alerts for night keepers. "
        "You are given a severity that was assigned deterministically upstream. "
        "NEVER change, question, or re-derive the severity. Only phrase it."
    ),
    input=[{"role": "user", "content": json.dumps({
        "severity": severity_from_python,   # authoritative, do not let model touch
        "event": event,
        "baseline": baseline,
    })}],
    text={"format": {"type": "json_schema", "name": "alert", "strict": True, "schema": {
        "type": "object", "additionalProperties": False,
        "required": ["headline", "why_unusual", "action"],
        "properties": {
            "headline":    {"type": "string"},
            "why_unusual": {"type": "string"},
            "action":      {"type": "string"},
        },
    }}},
    reasoning={"effort": "none"},   # latency-critical night-shift path
    store=False,
)
```

### 4.3 Function calling (investigation agent → Neo4j / Marengo tools)

Note the Responses API flattens the tool shape (`name`/`parameters` at top level, no `function:` wrapper).

```python
tools = [{
    "type": "function",
    "name": "query_animal_baseline",
    "description": "Fetch daytime-only baseline stats for an animal from the Neo4j context graph.",
    "parameters": {
        "type": "object",
        "properties": {
            "animal_id": {"type": "string"},
            "behavior":  {"type": "string"},
        },
        "required": ["animal_id", "behavior"],
        "additionalProperties": False,
    },
    "strict": True,
}]

msgs = [{"role": "user", "content": "Investigate the pacing cluster in enclosure 4 last night."}]

r1 = client.responses.create(
    model="gpt-5.6-terra", tools=tools, input=msgs,
    reasoning={"effort": "high"}, store=False,
    include=["reasoning.encrypted_content"],   # required to replay reasoning when store=False
)

msgs.extend(r1.output)                          # preserve EVERY output item, incl. reasoning
for item in r1.output:
    if item.type == "function_call":
        args = json.loads(item.arguments)
        msgs.append({
            "type": "function_call_output",
            "call_id": item.call_id,
            "output": json.dumps(run_tool(item.name, args)),
        })

r2 = client.responses.create(
    model="gpt-5.6-terra", tools=tools, input=msgs,
    reasoning={"effort": "high", "context": "all_turns"}, store=False,
    include=["reasoning.encrypted_content"],
)
```

`tool_choice` accepts `"auto"` (default), `"required"`, `"none"`, `{"type":"function","name":...}`, and `{"type":"allowed_tools","mode":"auto","tools":[...]}`. `parallel_tool_calls` defaults to `true`. Prefer `allowed_tools` over mutating the `tools` array — it restricts the callable subset **without breaking your prompt cache prefix**.

### 4.4 Vision — attaching key frames

Limits confirmed on the images/vision guide: **up to 1,500 individual image inputs per request**, **512 MB total payload per request**, formats PNG / JPEG / WEBP / non-animated GIF. `detail` accepts `"low"`, `"high"`, `"original"`, `"auto"`. On GPT-5.6, `"auto"` (and omitting it) is **equivalent to `"original"`** — i.e. full native resolution, which is more expensive than you'd expect. **Pin `detail` explicitly for ZooVision frames.**

```python
import base64

def frame_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

resp = client.responses.create(
    model="gpt-5.6-terra",
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": "Which of these frames shows abnormal gait?"},
        *[{"type": "input_image",
           "image_url": f"data:image/jpeg;base64,{frame_b64(p)}",
           "detail": "low"}                     # explicit: cheap triage pass
          for p in keyframe_paths],
    ]}],
    store=False,
)
```

> ⚠️ GPT-5.6 image token accounting: the vision guide documents **patch-based** costing (32×32 px patches with a model-specific multiplier) for GPT-5.4/5.5 and **tile-based** for GPT-4o/4.1. It does **not** publish the exact per-patch multiplier for the 5.6 family. **Measure `usage.input_tokens` empirically on a real ZooVision frame before budgeting.** Labeled ⚠️ UNVERIFIED for 5.6 specifically.

---

## 5. Key API features mapped to ZooVision agents

| Feature | Status on Terra/Luna | ZooVision use |
|---|---|---|
| Structured outputs (`strict: true`) | ✅ documented on all three model pages | The `events[]` contract; the `{headline, why_unusual, action}` alert |
| Function calling | ✅ documented | Neo4j Cypher tools, Marengo similarity search, S3 clip fetch |
| Image input | ✅ documented | Key-frame attach for ambiguous behaviors |
| Prompt caching | ✅ documented | Static system prompt + schema + care protocols (see §7) |
| Streaming | ✅ documented | Not needed for batch chunk merge; useful for the morning briefing UI |
| `file_search` / `web_search` | ✅ documented (hosted tools) | Not needed — Neo4j is ZooVision's retrieval layer |
| Batch | ✅ endpoint supported | Pre-baked night of chunks (see §7) |
| Reasoning effort | ✅ `none`\|`minimal`\|`low`\|`medium`\|`high`\|`xhigh`\|`max` | `none`/`low` for merge+phrasing, `high` for investigation |
| **Fine-tuning** | ❌ **not supported** on any GPT-5.6 variant | Don't plan on fine-tuning a ZooVision behavior classifier |
| **Realtime / Assistants / Embeddings / Audio** | ❌ not supported | Use Marengo for embeddings, as already planned |

`reasoning.effort` guidance from OpenAI's own `latest-model` page: `low` for *"latency-sensitive workloads"*, `medium` *"a balanced starting point"*, `high`/`xhigh` *"when more reasoning produces a measured quality gain"*, `max` for *"the hardest quality-first workloads"*. Reasoning tokens are **billed as output tokens** and reported at `usage.output_tokens_details.reasoning_tokens` — budget for them.

---

## 6. Advanced agentic primitives mapped to ZooVision agents

### 6.1 Compaction (native, server-side) — ✅ confirmed

The exact shape is a **list of objects**, not a bare dict:

```python
resp = client.responses.create(
    model="gpt-5.6-terra",
    input=conversation_items,
    context_management=[{"type": "compaction", "compact_threshold": 200_000}],
    store=False,   # docs: "For server-side compaction, no data is retained when store='false'."
)
```

When the rendered token count crosses the threshold, *"the response stream includes the encrypted compaction item."* Append that item to your next input array. Compaction items are *"opaque and not intended to be human-interpretable."*

Standalone endpoint also confirmed — **`POST /v1/responses/compact`** (reference page HTTP 200):

```python
compacted = client.responses.compact(model="gpt-5.6-terra", input=long_input_items)
# -> returns a response object whose .output is the compacted context. Do NOT prune it.
```

Documented rules worth obeying: manual pruning is acceptable **with** server-side compaction but **not** with `previous_response_id` chaining; when using `/responses/compact`, *"do not prune"* the output.

> **This is ZooVision's single most important cost guard.** Set `compact_threshold` at ~200,000 so the investigation agent never crosses the **272K long-context cliff** that doubles input pricing for the whole request.

### 6.2 Programmatic Tool Calling — ✅ confirmed (with a correction)

Enabled by adding a hosted tool entry:

```python
tools = [
    {"type": "programmatic_tool_calling"},
    {"type": "function", "name": "get_chunk_observations", "parameters": {...},
     "strict": True, "allowed_callers": ["programmatic"]},
]
```

`allowed_callers` values: `["direct"]` (or omitted) = direct only; `["programmatic"]` = program only; `["direct","programmatic"]` = both. Eligible tool types: functions, custom, MCP, `apply_patch`, local and hosted shell, `code_interpreter`.

**Correction to the brief:** the model writes **JavaScript with top-level `await`**, executed in *"a fresh, isolated V8 runtime"* — **not** Python, and not a generic "in-runtime program." The runtime *"does not provide Node.js, package installation, direct network access, a general-purpose filesystem, subprocess execution, a console, or persistent JavaScript state between program executions."*

Response items: a `program` item (the generated code), nested `function_call` items whose `caller.caller_id` matches the program, and a `program_output` item with `result` (JSON string) and `status` (`"completed"` / `"incomplete"`).

**ZooVision fit — strong.** The investigation agent's natural shape is "fan out over 48 chunks, filter to the anomalous ones, return only those rows." That is exactly the batching case PTC exists for. Third-party reporting cites *"named-customer token reductions of 38% to 63.5%"* (⚠️ third-party, MarkTechPost — OpenAI's docs publish no numbers and explicitly advise *"compare both approaches on representative tasks"*).

> ⚠️ **Verify before relying on it:** the PTC guide says *"Check the model page before enabling Programmatic Tool Calling"* — and the `gpt-5.6-terra` model page's feature list reads exactly `streaming, structured_outputs, function_calling, file_search, image_input, web_search, prompt_caching`. **`programmatic_tool_calling` is not enumerated there.** Third-party coverage asserts Terra does support it. Treat as **⚠️ UNVERIFIED on Terra specifically** and smoke-test on day one; fall back to plain parallel function calling.

### 6.3 Persisted / encrypted reasoning — ✅ confirmed, with a default you should know

- `reasoning.encrypted_content` — confirmed; the Responses API *"returns encrypted reasoning items by default."* Request via `include=["reasoning.encrypted_content"]` (confirmed in the `include` enum).
- `reasoning.context` accepts `"auto"`, `"current_turn"`, `"all_turns"`.
- **`gpt-5.6` defaults to `all_turns`**; earlier models default to `current_turn`. The brief implies you must opt in — you actually have to opt *out* if you don't want cross-turn reasoning replay (and its token cost).
- With `store=False`, *"preserve every item in the response's `output` array"* — dropping reasoning items breaks multi-turn quality.
- Billing warning, verbatim: all previous input tokens in chained responses *"are billed as input tokens in the API,"* **even when using `previous_response_id`.** Server-side state is not free.

### 6.4 Multi-agent orchestration (beta) — 🆕 the brief missed this entirely

```python
resp = client.beta.responses.create(
    model="gpt-5.6-terra",
    input="Investigate all anomalies across enclosures 1-6 for last night.",
    tools=[...],
    multi_agent={"enabled": True, "max_concurrent_subagents": 3},   # default 3
    betas=["responses_multi_agent=v1"],
)
```

Available in beta on **all GPT-5.6 models**. Requires the `responses_multi_agent=v1` beta flag. New output item types: `multi_agent_call`, `multi_agent_call_output`, `agent_message` (encrypted, with `author`/`recipient`), each carrying an `agent.agent_name` hierarchical path like `/root/researcher`. No fixed bound on tree depth. **Server-side compaction applies independently to each agent's context** — which neatly solves per-subagent context bloat.

Docs caution: *"adding subagents can increase token usage."* For ZooVision, per-enclosure parallel investigation is a genuinely clean decomposition — but this is a **beta** dependency on demo day. Keep a sequential fallback.

### 6.5 Agents SDK / AgentKit vs Strands — complements, doesn't block

`openai-agents==0.19.1` (PyPI, 2026-07-29) is OpenAI's own orchestration framework: agents with instructions/tools/guardrails/handoffs, sessions, tracing. **AgentKit** is the broader build/deploy/optimize suite layered on the Responses API.

**Recommendation: do not adopt the Agents SDK.** ZooVision has already committed to Strands Agents (`strands-agents==1.50.2`, 2026-07-27), which is the AWS-native choice for an AWS hackathon and speaks the Responses API directly via `OpenAIResponsesModel`. Running both would duplicate the orchestration layer for no judging benefit. The one thing worth borrowing conceptually is guardrails.

### 6.6 Strands wiring (the actual integration point)

```python
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

model = OpenAIResponsesModel(
    model_id="gpt-5.6-terra",
    client_args={"api_key": OPENAI_API_KEY},
    params={"max_output_tokens": 4096},
    stateful=False,                 # keep history client-side -> ZDR-friendly
)
agent = Agent(model=model, tools=[query_neo4j_baseline, marengo_similar_clips])
```

Constructor signature (from the Strands API reference):

```python
OpenAIResponsesModel(
    client_args: dict | None = None,
    bedrock_mantle_config: BedrockMantleConfig | None = None,
    **model_config,   # model_id, params, stateful, use_native_token_count
)
```

`stateful=True` moves conversation state server-side and clears local messages each turn — smaller payloads, but it implies `store=True`, which **defeats ZDR**. Keep `stateful=False` for ZooVision.

**`bedrock_mantle_config` is a first-class Strands parameter** that *"routes requests through Amazon Bedrock's Mantle (OpenAI-compatible) endpoint"*, minting a fresh bearer token per request (and cannot be combined with a pre-built client). For an AWS-judged hackathon this is a strong demo beat — see §7.5.

---

## 7. Cost & limits engineering

### 7.1 Official rate card (verbatim from the pricing page, post-cut)

| Model | Standard in / cached / out | Batch in / cached / out | Fast in / cached / out | Long-ctx in / cached / out |
|---|---|---|---|---|
| `gpt-5.6-sol` | $5.00 / $0.50 / $30.00 | $2.50 / $0.25 / $15.00 | $10.00 / $1.00 / $60.00 | $10.00 / $1.00 / $45.00 |
| `gpt-5.6-terra` | **$2.00 / $0.20 / $12.00** | **$1.00 / $0.10 / $6.00** | $4.00 / $0.40 / $24.00 | $4.00 / $0.40 / $18.00 |
| `gpt-5.6-luna` | **$0.20 / $0.02 / $1.20** | **$0.10 / $0.01 / $0.60** | $0.40 / $0.04 / $2.40 | $0.40 / $0.04 / $1.80 |

`service_tier` values: `"auto"`, `"flex"`, `"fast"`. **`"fast"` replaces `"priority"`** as of 2026-07-30 and is backward compatible (*"requests tagged priority will automatically use Fast mode"*). The `priority-processing` guide now **404s**, consistent with that. Fast = 2× standard rate. ZooVision needs none of this — the night shift is inherently asynchronous.

### 7.2 A night of ZooVision chunks — worked math

Assumptions (state them in the demo): 12-hour night (18:00–06:00) × 15-min segments = **48 chunks/camera**; **6 enclosure cameras** = **288 merge calls/night**. Per call ≈ **4,500 static tokens** (system prompt + `events[]` schema + care protocols) + **2,500 dynamic tokens** (Pegasus observations + Neo4j baseline) = **7,000 input**, **~700 output**.

Totals: **2,016,000 input tokens**, **201,600 output tokens** per night.

| Configuration | Input cost | Output cost | **Night total** |
|---|---|---|---|
| Terra, no caching (what the brief implies, at *old* prices $2.50/$15) | $5.04 | $3.02 | **$8.06** |
| Terra, no caching (today's $2.00/$12) | $4.03 | $2.42 | **$6.45** |
| Terra + prompt caching | $1.71 | $2.42 | **$4.13** |
| Terra + caching + **Batch** | $0.86 | $1.21 | **$2.07** |
| **Luna + caching + Batch** | **$0.09** | **$0.12** | ****$0.21**** |

Caching detail for the Terra row: the 4,500-token static prefix uncached would cost 288 × 4,500 × $2/1M = **$2.59**. Cached: one write at 1.25× ($0.011) + 287 reads at $0.20/1M ($0.258) = **$0.27**. Dynamic 2,500 tokens stay full price ($1.44).

Add the once-nightly reasoning passes on Terra: morning GraphRAG briefing (~40K in / ~9K out incl. reasoning) ≈ **$0.19**; one deep investigation (~150K in / ~15K out) ≈ **$0.48**. Alert phrasing on Luna is **<$0.01** for ~10 alerts.

> **Headline: a full ZooVision night runs well under $1.00** with Luna-for-merge + Batch + caching, versus ~$8 as briefed — a **~20× reduction on the merge path** and roughly **10× overall**. The whole hackathon costs less than lunch.

### 7.3 Prompt caching — the rules that actually bite

- Triggers at **≥1,024 tokens**. ZooVision's static prefix must clear that bar — pad the schema/protocol block if needed.
- **Exact-prefix match only.** Static content (instructions, schema, care protocols) **first**; variable content (this chunk's observations) **last**. Any per-call timestamp or chunk ID near the top destroys every hit.
- **GPT-5.6 charges for cache writes: *"cache writes cost 1.25× the uncached input token rate"*** — applies to *"GPT-5.6 models and later model families."* This is new versus older models and the brief doesn't mention it. It's still hugely net-positive at 288 reads per write, but it means caching is *not* free on the first call.
- TTL: **`prompt_cache_options.ttl` must be `"30m"`** — *"the only supported value"*, and also the default. `prompt_cache_retention` is *"deprecated for GPT-5.6 models and later model families."*
- 15-min segments arriving every 15 min keep a 30-min cache continuously warm. ✅ Good news for the live path.
- Explicit breakpoints (new on 5.6): `"prompt_cache_breakpoint": {"mode": "explicit"}` on a content block, plus request-level `prompt_cache_options.mode = "explicit"` to *"disable the implicit breakpoint."*
- Set `prompt_cache_key` consistently, and keep traffic *"to approximately 15 requests per minute"* per key to avoid misses. **288 chunks fired at once through one key will thrash.** Shard the key per camera.
- **Images and tools are cacheable** and count toward the 1,024-token minimum.
- Read hits from `usage.input_tokens_details.cached_tokens` (Responses API).

### 7.4 Batch API — biggest single cost lever, with one blocker

- **50% discount**, `completion_window="24h"` (the only supported value).
- **`/v1/responses` IS a valid batch endpoint.** The batch *reference* enumerates `"/v1/responses"`, `"/v1/chat/completions"`, `"/v1/embeddings"`, `"/v1/completions"`, `"/v1/moderations"`, `"/v1/images/generations"`, `"/v1/images/edits"`, `"/v1/videos"`. ⚠️ Note: the batch **guide's** prose list omits `/v1/responses` — the guide is stale, the reference and the model pages agree it works. Smoke-test on day one.
- Limits: **50,000 requests per batch**, **200 MB** input file, 2,000 batches/hour. `output_expires_after` accepts `anchor: "created_at"` and `seconds` between 3,600 and 2,592,000.
- Output line order is not input order — **map by `custom_id`**.

```python
# One JSONL line per 15-min chunk
{"custom_id": "cam4-2026-07-29T23:15", "method": "POST", "url": "/v1/responses",
 "body": {"model": "gpt-5.6-luna", "instructions": SYSTEM_PROMPT, "input": [...],
          "text": {"format": {"type": "json_schema", "name": "zoovision_events",
                              "schema": EVENTS_SCHEMA, "strict": True}},
          "reasoning": {"effort": "low"}}}
```

```python
f = client.files.create(file=open("night.jsonl", "rb"), purpose="batch")
batch = client.batches.create(input_file_id=f.id, endpoint="/v1/responses",
                              completion_window="24h")
# poll
batch = client.batches.retrieve(batch.id)
results = client.files.content(batch.output_file_id)
```

> ❌ **Blocker: Batch is NOT ZDR-eligible** (nor are Files). See §8. ZooVision must choose: 50% off, or zero retention. **Recommendation: use Batch for the demo (synthetic/consented footage) and document the ZDR-safe production path as real-time `store=False` calls.** That tradeoff, stated explicitly, is a *credibility win* with judges rather than a weakness.

**Flex processing** (`service_tier: "flex"`) is the ZDR-compatible middle ground — *"Tokens are priced at Batch API rates"* without the Files/Batch objects. ⚠️ But it is *"in beta with limited model availability"* and the pricing page shows **no flex row for the GPT-5.6 family** (only Standard / Batch / Fast). **Assume flex is unavailable on 5.6 until tested.**

### 7.5 Rate limits — and the Tier-1 trap

`gpt-5.6-terra`:

| Tier | RPM | TPM | Batch queue |
|---|---|---|---|
| 1 | 500 | 500,000 | **1,500,000** |
| 2 | 5,000 | 1,000,000 | 3,000,000 |
| 3 | 5,000 | 2,000,000 | 100,000,000 |
| 4 | 10,000 | 4,000,000 | 200,000,000 |
| 5 | 15,000 | 40,000,000 | 15,000,000,000 |

`gpt-5.6-luna` (materially better at low tiers):

| Tier | RPM | TPM | Batch queue |
|---|---|---|---|
| 1 | 500 | 500,000 | **5,000,000** |
| 2 | 5,000 | 2,000,000 | 20,000,000 |
| 3 | 5,000 | 4,000,000 | 40,000,000 |
| 4 | 10,000 | 10,000,000 | 1,000,000,000 |
| 5 | 30,000 | 180,000,000 | 15,000,000,000 |

> ⚠️ **Concrete trap:** one ZooVision night is **~2.0M input tokens**. **Terra's Tier-1 batch queue limit is 1.5M — your night's batch will be rejected on a fresh account.** Luna's Tier-1 limit is 5M and fits comfortably. This is an *independent* argument for Luna on the merge path, on top of the 10× price advantage.
>
> Also: 288 concurrent 7K-token calls = 2.0M tokens instantaneously, versus a 500K TPM Tier-1 ceiling → guaranteed 429s. **Cap concurrency to ~8–10 in-flight requests** on the live path.

---

## 8. Data-handling / retention posture

Relevant because ZooVision handles sensitive animal-care footage and welfare findings that could carry institutional/reputational weight.

- **API data is not used for training by default** — opt-in only.
- **Default retention: 30 days** for abuse monitoring; Responses objects also stored 30 days by default.
- **`store=false`** on `/v1/responses` and `/v1/chat/completions` prevents application-state persistence. Under ZDR, `store` is *"always treated as `false` regardless of your request settings."*
- **ZDR eligibility** requires contacting OpenAI sales, prior approval, and accepting additional requirements; configurable at organization or project level. **Not self-serve — you will not have it by demo day.**
- **ZDR-eligible endpoints:** `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/moderations`, `/v1/images/*`, `/v1/audio/*`, `/v1/completions`, `/v1/realtime`.
- **❌ NOT ZDR-eligible: Batch, Files, Conversations, Assistants, Threads, Vector Stores, Fine-tuning, Videos.** This is the crux: ZooVision's cheapest path (Batch + Files) and its strictest privacy posture are mutually exclusive.
- **Compaction is ZDR-clean:** *"For server-side compaction, no data is retained when `store='false'`."*
- Caveat: image and file inputs are scanned for CSAM and retained for manual review if flagged, **even under ZDR**.
- ⚠️ Third-party report that `store=true` cannot be set in non-US regions — not confirmed on first-party docs; irrelevant for a San Francisco demo.

**Bedrock alternative posture** (often *better* for this use case): with `store=false`, *"Amazon Bedrock does not retain any data from the request or response."* With `store=true` (the default), data is retained 30 days **in the source region**, encrypted at rest, scoped to the calling account's Project, and *"stored solely to service your requests and is not used or retained for any other purpose."* Plus *"in-region data processing"* and *"hardware-enforced security with zero operator access at the chip."* **Note the default is `true` — you must explicitly set `store=false` on every request.**

---

## 9. Gotchas, model-string drift & deprecations

1. **Never ship the bare `gpt-5.6` alias.** It routes to **Sol** at $5/$30 — 2.5× Terra's input price and 2.5× its output price. A single careless string costs 2.5×.
2. **The 272K long-context cliff is a step function, not a ramp.** One token over 272K input re-prices the **entire request** at 2× input / 1.5× output. Guard with `context_management` compaction at ~200K.
3. **Context window ≠ max input.** 1,050,000 context but **max input 922,000** (confirmed on both Terra and Sol pages). You cannot fill the window with input.
4. **Cache writes now cost 1.25×** on GPT-5.6+. New behavior; changes break-even math for low-reuse prefixes.
5. **`prompt_cache_retention` is deprecated** on GPT-5.6+; use `prompt_cache_options.ttl = "30m"` (the only legal value).
6. **`service_tier: "priority"` is superseded by `"fast"`** as of 2026-07-30; the priority-processing guide **404s**. Old code still works (backward compatible) but is now billed as Fast.
7. **`reasoning.context` defaults to `"all_turns"` on GPT-5.6**, unlike earlier models. Silent extra input-token cost on multi-turn investigations if you don't set it to `"current_turn"`.
8. **With `store=false` you must replay the full `output` array**, including reasoning items, and pass `include=["reasoning.encrypted_content"]`. Dropping them degrades multi-turn quality.
9. **`previous_response_id` does not save tokens.** All prior input tokens *"are billed as input tokens"* regardless.
10. **Strict structured-output schema limits:** max 5,000 object properties, 10 nesting levels, 120,000 total chars across names/definitions/enums, 1,000 enum values total (a single enum >250 string values caps at 15,000 chars). Unsupported under `strict: true`: `allOf`, `not`, `dependentRequired`, `dependentSchemas`, `if`/`then`/`else`, and **root-level `anyOf`**. Every property must be in `required`, and every object needs `additionalProperties: false`. **Optional fields must be nullable unions (`["string","null"]`), not omitted.** ZooVision's `events[]` schema is well within limits but must follow the nullable pattern.
11. **Batch guide contradicts the Batch reference** on whether `/v1/responses` is supported. Reference + model pages say yes. Verify on day one.
12. **Image `detail` defaults to full native resolution on GPT-5.6** (`auto` ≡ `original`). Silently expensive for camera frames — pin `"low"` for triage.
13. **No fine-tuning** on any GPT-5.6 variant.
14. **Bedrock's Terra context window is 272K, not 1.05M** — see §10. If you demo through Bedrock, your context budget is ~4× smaller than first-party.
15. **Multi-agent is beta** and requires `betas=["responses_multi_agent=v1"]` plus `client.beta.responses.create`. Don't put a beta on the critical demo path without a fallback.

---

## 10. Corrections to the ZooVision brief

| # | Brief claim | Verdict | Reality | Source |
|---|---|---|---|---|
| 1a | `gpt-5.6-terra` exists | ✅ **confirmed** | Real, documented, HTTP 200. Single snapshot `gpt-5.6-terra`, no dated snapshots. | `developers.openai.com/api/docs/models/gpt-5.6-terra` |
| 1b | GA July 9 2026 | ✅ confirmed | Changelog Jul 9 entry; family GA that date. (Bedrock GA was **Jul 13**.) | OpenAI changelog; AWS model card |
| 1c | Bare `gpt-5.6` → "Sol", not Terra | ✅ **confirmed** | Verbatim: *"The `gpt-5.6` alias routes requests to GPT-5.6 Sol."* | Sol model page; models index |
| 2 | 1.05M context, 128K max output | ✅ confirmed **+ nuance** | 1,050,000 context, 128,000 output — but **max *input* is 922,000**, which the brief omits. | Terra model page |
| 3a | $2.50/1M in, $15/1M out | ❌ **WRONG — stale by one day** | **$2.00 in / $0.20 cached / $12.00 out.** OpenAI cut Terra 20% and Luna 80% on **2026-07-30**. $2.50/$15 was correct only Jul 9–29. | OpenAI changelog Jul 30; pricing page |
| 3b | >272K priced 2× in / 1.5× out | ✅ confirmed | Verbatim: *"Prompts with >272K input tokens are priced at 2x input and 1.5x output for the full request."* At new rates: $4.00/$18.00. | Terra model page; pricing page |
| 4a | Served on Responses API | ✅ confirmed | Yes. | Terra model page |
| 4b | "**not** Chat Completions" | ❌ **WRONG** | Terra supports **Chat Completions, Responses, AND Batch** first-party. (The claim is accidentally true *on Bedrock*, where the model card marks Chat Completions ✗ and Responses ✓.) | Terra model page; AWS Terra model card |
| 4c | `reasoning.effort` incl. `low` and `none` | ✅ confirmed **+ more** | Full set: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. | Reasoning guide |
| 5 | Knowledge cutoff Feb 16 2026 | ✅ confirmed | Feb 16, 2026 — all three variants. | All three model pages |
| 6 | Structured outputs, vision, function calling | ✅ confirmed | `structured_outputs`, `function_calling`, `image_input` all listed, on **all three** variants. | Model pages |
| 7a | Compaction native via `context_management` + `compact_threshold` | ✅ confirmed **+ shape correction** | Real, but it's an **array**: `context_management=[{"type": "compaction", "compact_threshold": 200000}]`. The brief implies a flat dict. | Compaction guide; Responses create reference |
| 7b | `/responses/compact` endpoint | ✅ confirmed | `POST /v1/responses/compact`, params `model` + `input`; SDK `client.responses.compact()`. | Compact method reference (HTTP 200) |
| 7c | ZDR-friendly with `store=false` | ✅ confirmed | Verbatim: *"For server-side compaction, no data is retained when `store='false'`."* | Compaction guide; your-data guide |
| 8 | Programmatic Tool Calling batches tool calls | ✅ mostly — ⚠️ **one correction + one caveat** | Real: `{"type": "programmatic_tool_calling"}` + `allowed_callers`. **Correction: the model writes JavaScript in an isolated V8 runtime**, not an unspecified "program". **Caveat: not enumerated in Terra's model-page feature list** — ⚠️ unverified on Terra specifically. | PTC guide; Terra model page |
| 9 | `reasoning.encrypted_content`, `reasoning.context: "all_turns"` | ✅ confirmed **+ nuance** | Both real; `reasoning.encrypted_content` is in the `include` enum. **Nuance: GPT-5.6 already defaults to `all_turns`** — it's opt-*out*, not opt-in. | Reasoning guide; conversation-state guide; Responses create reference |
| 10 | 7 doc URLs exist | ✅ **5 of 7 verified 200**; 2 unreadable | `models/gpt-5.6-terra` **200** · `models` **200** · `guides/compaction` **200** · `guides/tools-programmatic-tool-calling` **200** · `guides/conversation-state` **200** · `reference/.../compact` **200**. **`openai.com/index/gpt-5-6/` returns HTTP 403 to automated fetchers** — it is *not* a 404 (it appears in search results and is cited by Simon Willison), but **I could not read it**. Same for the Jul 30 price-cut post. | Direct `curl` status checks |
| 11 | Some numbers appear only on aggregators; do primary docs corroborate? | ❌ **primary docs REFUTE the aggregators** | `requesty.ai` shows **$2.50/$15, cache $0.25, "1.1M" context** — all stale/rounded. `coursiv.io` shows **$2.50/$15, cache write $3.125, cached read $0.25, long-ctx $5.00/$22.50** — all stale. **Primary docs say $2.00/$0.20/$12.00, long-ctx $4.00/$18.00, context exactly 1,050,000.** The brief was clearly written from aggregator data. | requesty.ai; coursiv.io; vs. pricing page |
| — | Bedrock "OpenAI-compatible Mantle endpoint" | ✅ **confirmed real** | `bedrock-mantle` is genuine. Terra model ID **`openai.gpt-5.6-terra`**, base URL **`https://bedrock-mantle.{region}.api.aws/openai/v1`** (note: `/openai/v1`, explicitly *"different from the `v1/responses` path used by other models"*). us-east-1 / us-east-2 / us-west-2, In-Region only. Pricing matches OpenAI first-party; cached input at **90% discount**, ≥30 min. Standard service tier only. | AWS Terra model card; `bedrock-mantle.html` |
| — | ⚠️ **Bedrock context window** | ⚠️ **DISCREPANCY** | AWS's Terra model card states **"Context window: 272K tokens"**, *not* 1.05M. Suspiciously equal to the first-party long-context threshold. **If ZooVision routes through Bedrock, budget 272K.** Verify empirically. | AWS Terra model card |

### What the brief missed entirely

- **`gpt-5.6-luna` at $0.20/$1.20** — 10× cheaper than Terra, same 1.05M context, same structured-outputs/function-calling/vision support. This is the correct model for the 288-call/night merge path and is the single biggest cost decision in the project.
- **`gpt-5.6-sol` at $5/$30** and the fact that the bare alias silently selects it.
- **Today's price cut** (Terra −20%, Luna −80%).
- **Batch API 50% discount on `/v1/responses`** — and that **Batch is not ZDR-eligible**.
- **Cache writes cost 1.25×** on GPT-5.6+; `prompt_cache_options.ttl="30m"` is the only legal TTL; `prompt_cache_retention` is deprecated.
- **Terra's Tier-1 batch queue limit (1.5M tokens) is smaller than one ZooVision night (~2M).**
- **Multi-agent orchestration beta** (`multi_agent.enabled`, `max_concurrent_subagents`) — a natural fit for per-enclosure parallel investigation.
- **Vision limits: 1,500 images/request, 512 MB payload**, and that `detail` defaults to full native resolution on 5.6.
- **Strands' `bedrock_mantle_config`** — first-class Bedrock Mantle routing, an easy AWS-judging win.
- **`service_tier: "fast"`** replacing `"priority"`.
- **No fine-tuning** on any 5.6 variant.

---

## 11. Open questions to resolve before demo day

1. **Does Terra actually accept `{"type": "programmatic_tool_calling"}`?** Its model-page feature list omits it while the PTC guide says to check that very page. **Smoke-test in the first hour.** Fallback: plain `parallel_tool_calls`.
2. **Is `/v1/responses` really accepted by `batches.create`?** Reference says yes, guide's prose omits it. One 3-line test settles it — and it's worth ~50% of the compute bill.
3. **Bedrock context window: 272K or 1.05M?** AWS's card says 272K. Send a ~300K-token request through `bedrock-mantle` and see whether it errors.
4. **Which account tier are we on?** Tier 1 Terra batch queue = 1.5M tokens < one night. Either shrink the demo night, switch the merge path to Luna (5M limit), or get the account upgraded.
5. **What do ZooVision frames actually cost in tokens?** GPT-5.6 patch multipliers aren't published. Measure `usage.input_tokens` on one real 1080p enclosure frame at `detail: "low"` vs `"original"` before committing to frame attachment.
6. **Does `gpt-5.6-luna` hold the strict `events[]` schema as reliably as Terra?** Run both over ~50 labeled chunks and compare schema-violation and false-negative rates. This is the highest-leverage eval in the project — it's a 10× cost decision.
7. **Batch (50% off, no ZDR) vs real-time `store=false` (ZDR-eligible)?** Decide and *say so on stage* — the tradeoff is a credibility asset.
8. **Is `service_tier: "flex"` available on 5.6?** Pricing page shows no flex row. If it works, it's Batch pricing without the non-ZDR Files/Batch objects — the best of both worlds.
9. **Do we route through Bedrock Mantle or OpenAI direct?** Mantle scores AWS-alignment points and gives in-region processing + 90% cache discount; OpenAI direct gives the full 1.05M context and Chat Completions. Consider Mantle for the demo, direct as fallback — Strands supports both via one config swap.
10. **Cache-key sharding:** docs advise ~15 RPM per `prompt_cache_key`. With 6 cameras, shard per camera and verify `cached_tokens` is actually non-zero in `usage`.
11. **Is `openai==2.51.0` (shipped today) stable?** Consider pinning `2.50.x` if 2.51.0 shows churn — but 2.51.0 is likely the release that carries the new pricing/Fast-mode surface.

---

## 12. Sources

### First-party — OpenAI docs (all fetched, HTTP 200 verified)

| URL | What it confirmed |
|---|---|
| `https://developers.openai.com/api/docs/models` | **Full model lineup**: `gpt-5.6-sol` (alias `gpt-5.6`), `gpt-5.6-terra`, `gpt-5.6-luna`, all 1.05M context; plus `gpt-image-2`, `gpt-realtime-2.1`, `gpt-transcribe` families. Post-cut pricing. |
| `https://developers.openai.com/api/docs/models/gpt-5.6-terra` | **Terra is real.** 1,050,000 context / 922,000 max input / 128,000 max output; $2/$0.20/$12; Feb 16 2026 cutoff; Chat Completions + Responses + Batch; feature list; full tier rate-limit table; verbatim 272K long-context wording. |
| `https://developers.openai.com/api/docs/models/gpt-5.6-sol` | `gpt-5.6` alias → Sol (verbatim); $5/$0.50/$30; same context/output; rate limits. |
| `https://developers.openai.com/api/docs/models/gpt-5.6-luna` | $0.20/$0.02/$1.20; same context/output; structured outputs + function calling + image input; **Tier-1 batch queue 5M**. |
| `https://developers.openai.com/api/docs/pricing` | **Authoritative rate card** incl. Batch (50% off), Fast (2×), and long-context rows for all three variants. |
| `https://developers.openai.com/api/docs/changelog` | **Jul 30 price cut** (Luna −80%, Terra −20%) and **Fast mode replacing Priority Processing**; Jul 9 family launch with PTC, explicit cache controls, persisted reasoning, multi-agent beta, image `original`/`auto`. |
| `https://developers.openai.com/api/docs/guides/compaction` | `context_management=[{"type":"compaction","compact_threshold":N}]`; `client.responses.compact()`; ZDR-clean with `store=false`; pruning rules; opaque compaction items. |
| `https://developers.openai.com/api/reference/resources/responses/methods/compact` | **`POST /v1/responses/compact` exists**; params `model` + `input`. |
| `https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling` | `{"type":"programmatic_tool_calling"}`; `allowed_callers` enum; **JavaScript in isolated V8**, no Node/network/filesystem; `program` / `function_call` / `program_output` items; "check the model page". |
| `https://developers.openai.com/api/docs/guides/conversation-state` | `previous_response_id`; Conversations API; `store=false`; 30-day default; `reasoning.context: "all_turns"`; **all prior input tokens still billed**. |
| `https://developers.openai.com/api/docs/guides/reasoning` | **`effort` enum: `none`\|`minimal`\|`low`\|`medium`\|`high`\|`xhigh`\|`max`**; `context` enum with GPT-5.6 defaulting to `all_turns`; reasoning billed as output; `usage.output_tokens_details.reasoning_tokens`. |
| `https://developers.openai.com/api/docs/guides/structured-outputs` | `text.format` shape; **all strict-mode schema limits** (5,000 props / 10 levels / 120,000 chars / 1,000 enums); unsupported keywords incl. root-level `anyOf`; nullable-union optional pattern; refusal item. |
| `https://developers.openai.com/api/docs/guides/function-calling` | Flattened Responses tool shape; `function_call_output` + `call_id`; `tool_choice` values; `parallel_tool_calls`; `allowed_tools` for cache preservation. |
| `https://developers.openai.com/api/docs/guides/prompt-caching` | 1,024-token minimum; **1.25× cache writes on GPT-5.6+**; `prompt_cache_options.ttl="30m"` only value; `prompt_cache_breakpoint`; `prompt_cache_key` + ~15 RPM advice; `prompt_cache_retention` deprecated; images/tools cacheable. |
| `https://developers.openai.com/api/docs/guides/batch` | 50% discount; 24h window; JSONL fields; 50,000 requests / 200 MB; map by `custom_id`. ⚠️ **prose endpoint list omits `/v1/responses` — contradicted by the reference.** |
| `https://developers.openai.com/api/reference/resources/batches/methods/create` | **`"/v1/responses"` IS in the endpoint enum**; `completion_window` only `"24h"`; `output_expires_after` bounds. |
| `https://developers.openai.com/api/docs/guides/images-vision` | `input_image` / `image_url` / `file_id` / `detail`; **`detail` enum incl. `"original"`, with `auto` ≡ `original` on GPT-5.6**; 1,500 images & 512 MB per request; formats; patch vs tile costing. |
| `https://developers.openai.com/api/docs/guides/your-data` | Not trained on by default; 30-day abuse logs; `store=false`; ZDR requires sales approval; **ZDR-eligible endpoint list — Batch/Files/Conversations NOT eligible**; compaction ZDR-clean. |
| `https://developers.openai.com/api/docs/guides/latest-model` | OpenAI's own Sol/Terra/Luna selection guidance; per-effort recommendations; `gpt-5.6` defaults to Sol; migration advice. |
| `https://developers.openai.com/api/docs/guides/responses-multi-agent` | `multi_agent.enabled`, `max_concurrent_subagents` (default 3); `betas=["responses_multi_agent=v1"]`; all GPT-5.6 models; `multi_agent_call` / `agent_message` items; per-agent compaction. |
| `https://developers.openai.com/api/reference/resources/responses/methods/create` | Confirmed `context_management` (array), `include`, `background`, `conversation`; **verbatim `include` enum containing `"reasoning.encrypted_content"`**. |
| `https://developers.openai.com/api/docs/guides/flex-processing` | `service_tier: "flex"`; *"priced at Batch API rates"*; beta with limited model availability; 408/429 behavior. |

### First-party — blocked or removed

| URL | Status |
|---|---|
| `https://openai.com/index/gpt-5-6/` | ⚠️ **HTTP 403** to automated fetchers (verified by direct `curl` and WebFetch). **Not a 404** — the page exists and is indexed/cited. Launch details sourced from OpenAI's own changelog + Simon Willison instead. |
| `https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/` | ⚠️ **HTTP 403**. The Jul 30 price-cut post. Content corroborated via OpenAI changelog (first-party) + CNBC/Axios/Yahoo. |
| `https://developers.openai.com/api/docs/guides/priority-processing` | ❌ **404** — consistent with the changelog's statement that Fast mode replaced Priority Processing on 2026-07-30. |
| `https://developers.openai.com/api/docs/guides/multi-agent` | ❌ **404** (my initial guess). Correct path is `guides/responses-multi-agent`. |

### First-party — AWS (Bedrock)

| URL | What it confirmed |
|---|---|
| `https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-terra.html` | Model ID **`openai.gpt-5.6-terra`**; base URL **`https://bedrock-mantle.{region}.api.aws/openai/v1`** (explicitly different from other models' `v1/`); **context window stated as 272K**; Responses ✓ / Chat Completions ✗; Standard tier only; In-Region only (us-east-1/2, us-west-2); Bedrock launch **Jul 13 2026**; runnable Python sample. |
| `https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html` | Mantle is real; `OPENAI_BASE_URL` / `OPENAI_API_KEY` env-var setup; Bedrock API key auth; **`store` semantics on Bedrock (default `true`, 30-day in-region retention; `false` = no retention)**; 14-region availability; separate quotas from `bedrock-runtime`. |
| `https://aws.amazon.com/blogs/machine-learning/openai-gpt-5-6-sol-terra-and-luna-are-now-generally-available-on-amazon-bedrock/` | Regions per variant; *"Pricing matches OpenAI first-party rates"*; **90% cached-input discount, ≥30 min**. |
| `https://aws.amazon.com/about-aws/whats-new/2026/07/openai-gpt-sol-terra/` | Posted **Jul 13 2026**; regions; 90% caching discount; counts toward AWS commitments. |

### First-party — SDKs

| Source | What it confirmed |
|---|---|
| `https://pypi.org/pypi/openai/json` (curl) | **`openai==2.51.0`**, uploaded **2026-07-30T17:43:24**, requires Python ≥3.10. |
| `https://pypi.org/pypi/openai-agents/json` (curl) | `openai-agents==0.19.1`, 2026-07-29. |
| `https://pypi.org/pypi/strands-agents/json` (curl) | `strands-agents==1.50.2`, 2026-07-27. |
| `https://pypi.org/project/openai/` (WebFetch) | ⚠️ Page rendered an error shell; version obtained via the JSON API instead. |

### First-party — Strands Agents (AWS)

| URL | What it confirmed |
|---|---|
| `https://strandsagents.com/docs/api/python/strands.models.openai_responses/` | `OpenAIResponsesModel` in `strands.models.openai_responses`; **constructor includes `bedrock_mantle_config: BedrockMantleConfig`**; config keys `model_id`, `params`, `stateful`, `use_native_token_count`; `structured_output()` supported. |
| `https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/` | Runnable examples for direct OpenAI and Bedrock Mantle routing; built-in tools via `params["tools"]`; `stateful=True` clears local history. |
| `https://strandsagents.com/docs/user-guide/concepts/model-providers/openai/` | `OpenAIModel` (Chat Completions) vs `OpenAIResponsesModel`; `pip install 'strands-agents[openai]'`; `client_args.base_url` override. |

### Third-party — used only for corroboration or to expose staleness

| URL | Role |
|---|---|
| `https://simonwillison.net/2026/Jul/9/gpt-5-6/` | Independent corroboration of **launch** pricing (*"Luna $1/$6, Terra $2.50/$15, Sol $5/$30"*), 1M context, 128K output, Feb 16 2026 cutoff; notes PTC, multi-agent, explicit cache breakpoints, original-resolution images; Claude Fable 5 beats all 5.6 variants on SWE-Bench Pro (80% vs 64.6%). |
| `https://www.marktechpost.com/2026/07/09/openai-releases-gpt-5-6-...` | Corroborates launch pricing and *"Programmatic Tool Calling runs model-written JavaScript in an isolated V8 runtime with no network access"*; cites 38–63.5% token reductions (⚠️ **not in OpenAI docs**). |
| CNBC / Axios / Yahoo / Unite.AI (Jul 30 2026) | Independent corroboration of the **price cut** and the exact new figures ($2/$12 Terra, $0.20/$1.20 Luna), Sol unchanged, Fast mode at 2× price. |
| Neowin / TechJournal | Jul 9 GA date; Jun 26 limited preview. |
| `https://requesty.ai/models/openai-responses/gpt-5.6-terra` | ⚠️ **Demonstrates the brief's error source.** Still shows **$2.50/$15, cache $0.25, "1.1M tokens"** — stale and rounded. **Primary docs do NOT corroborate.** |
| `https://coursiv.io/blog/gpt-5-6-terra` | ⚠️ **Stale.** $2.50/$15, cache write $3.125, cached read $0.25, long-ctx $5.00/$22.50. Correct on 1.05M context, 128K output, Feb 16 2026 cutoff, and the `none`…`max` effort enum. **Pricing refuted by the official rate card.** |
| `https://github.com/zed-industries/zed/pull/57412` | Independent evidence that `service_tier: "fast"` is a real Responses API value. |

**Not verifiable / explicitly flagged ⚠️ UNVERIFIED in this document:** GPT-5.6 image patch-token multipliers (not published); whether `programmatic_tool_calling` is accepted by `gpt-5.6-terra` specifically (absent from its model-page feature list); whether `service_tier: "flex"` works on 5.6 (no flex row on the pricing page); the true Bedrock Terra context window (AWS says 272K, OpenAI says 1.05M); and the PTC token-reduction percentages (third-party only).
