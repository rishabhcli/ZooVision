# AWS (Bedrock, AgentCore & Agent Toolkit) — ZooVision Sponsor Reference

> **Researched:** 2026-07-30 · **Verification status:** Every brief claim was live-fetched. **All 7 claim groups confirmed — including the "Mantle endpoint", which is real.** 6/6 disputed URLs returned HTTP 200. Corrections below are about *staleness and gaps*, not hallucination. Prices/quotas quoted from AWS pages fetched today; three items marked `⚠️ UNVERIFIED`.
> **Role in ZooVision:** AWS is the substrate — Bedrock hosts the TwelveLabs video models *and* the GPT-5.6 structuring model; AgentCore Runtime hosts the Strands orchestrator; S3/Lambda/EventBridge Scheduler/Secrets Manager/CloudWatch carry the segmenter→watcher→alert→briefing pipeline.

---

## 1. Snapshot

| Service | Status | ZooVision use | Cost | Risk |
|---|---|---|---|---|
| **Bedrock — TwelveLabs Pegasus 1.2** | GA (launched Feb 11 2025; on Bedrock Jul 2025) | Video→text welfare analysis of 15-min segments | ~$0.021–0.042/video-min `⚠️ UNVERIFIED` | **In-region only in us-east-1 + ap-northeast-2.** Must use `us.` geo profile elsewhere |
| **Bedrock — TwelveLabs Marengo Embed 3.0** | GA | Embeddings for "have we seen this behaviour before?" retrieval | See above `⚠️ UNVERIFIED` | Async-only for video (`StartAsyncInvoke`); 2.7 is being **deprecated** |
| **Bedrock Mantle (`bedrock-mantle`)** | GA | OpenAI-SDK-compatible access to **GPT-5.6 Terra** for structuring/phrasing | Per-token, model-dependent | Separate quota pool from `bedrock-runtime`; `store:true` retains data 30 days by default |
| **AgentCore Runtime** | **GA since Oct 2025** | Hosts the Strands orchestrator; 8-h ceiling, 100 MB payloads | $0.0895/vCPU-h + $0.00945/GB-h, idle free | **15-min idle timeout** kills sessions unless you return `HealthyBusy` |
| **AgentCore Memory** | GA | Per-animal behavioural baselines across nights | $0.25/1k events; $0.75/1k records/mo; $0.50/1k retrievals | Overlaps Neo4j — pick one as source of truth |
| **AgentCore Gateway** | GA | Wraps Neo4j/S3/notify Lambdas as MCP tools | $0.005/1k invocations | Adds a hop; optional for hackathon |
| **AgentCore Identity** | GA | Outbound creds for TwelveLabs/OpenAI/Neo4j | $0.010/1k tokens (free via Runtime/Gateway) | — |
| **AgentCore Observability** | GA | `rule_fired` audit trail, agent traces | CloudWatch rates | Requires **CloudWatch Transaction Search** enabled first |
| **AgentCore Policy (Cedar)** | **GA since Mar 2026** | ⭐ **The real "no actuator tools" guarantee** | $0.000025/request | Brief never mentions it — biggest missed win |
| **Agent Toolkit for AWS** | GA (announced **May 6 2026**) | Build-time accelerator in Claude Code | **Free** (pay only for resources) | Give it a scoped IAM role |
| **S3** | GA | 3 buckets + lifecycle | ~$0.023/GB-mo Standard | Lifecycle min 1 day; presigned URL life ≤ credential life |
| **Lambda** | GA | Watcher + ffmpeg clip cutter | Free tier 1M req/mo | 15-min hard ceiling; 250 MB zip → use layer or container |
| **EventBridge Scheduler** | GA | ⭐ 06:00 briefing **and** 20-min escalation | ~$1.00/1M invocations | One-time schedules count against quota unless `ActionAfterCompletion: DELETE` |
| **SNS SMS** | GA | ❌ **Not viable at a hackathon** | $0.00581/msg US | **Requires a registered origination number: 10DLC ≈ 4–7 weeks, toll-free ≤ 15 business days** |
| **S3 Vectors** | **GA since Dec 2025** | ⭐ Store Marengo embeddings, no vector DB | Up to 90% cheaper than vector DBs | Brief never mentions it |
| **Secrets Manager** | GA | TwelveLabs/OpenAI/Neo4j creds | $0.40/secret/mo + $0.05/10k calls | SSM Parameter Store Standard is **$0** — use it for the hackathon |

---

## 2. Amazon Bedrock: model access ZooVision needs

### 2.1 TwelveLabs on Bedrock — confirmed, with exact IDs

Three TwelveLabs models are fully managed on Bedrock ([model-parameters-twelvelabs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html)):

| Model | Model ID | API operations | Notes |
|---|---|---|---|
| Pegasus 1.2 | `twelvelabs.pegasus-1-2-v1:0` | `InvokeModel`, `InvokeModelWithResponseStream` | Video→text. Max **1 hour / <2 GB** via S3; **25 MB** via base64 |
| Marengo Embed 2.7 | `twelvelabs.marengo-embed-2-7-v1:0` | `StartAsyncInvoke` | ⚠️ **Being deprecated** |
| Marengo Embed 3.0 | `twelvelabs.marengo-embed-3-0-v1:0` | `InvokeModel` (text/image), `StartAsyncInvoke` (video/audio) | **4 h / 6 GB**; 512-dim (was 1024); 36 languages |

**Critical regional gotcha.** Pegasus 1.2's in-region availability is *narrow* — from the [Pegasus v1.2 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-twelvelabs-pegasus-v1-2.html):

- **In-Region:** only `us-east-1` and `ap-northeast-2` (Seoul).
- **Geo cross-region:** `us.twelvelabs.pegasus-1-2-v1:0` (US) / `eu.twelvelabs.pegasus-1-2-v1:0` (EU).
- **Global:** `global.twelvelabs.pegasus-1-2-v1:0` — works from ~30 regions.

So **`us-west-2` does NOT support the bare `twelvelabs.pegasus-1-2-v1:0` model ID.** If your Bedrock work is in Oregon (the AgentCore CLI default), you must use the `us.` or `global.` prefix. This is the single most likely cause of an `AccessDeniedException`/`ValidationException` on demo day.

Pegasus is `bedrock-runtime` only — **not** available on `bedrock-mantle`, and it does **not** support `Converse`. Use `InvokeModel`.

**Pegasus call (works from any US region):**

```python
import json, boto3

brt = boto3.client("bedrock-runtime", region_name="us-west-2")

resp = brt.invoke_model(
    modelId="us.twelvelabs.pegasus-1-2-v1:0",   # geo profile, NOT the bare ID
    body=json.dumps({
        "inputPrompt": (
            "You are an overnight animal-welfare observer. Describe abnormal "
            "behaviour only: stereotypy/pacing, lameness, prolonged recumbency, "
            "aggression, failure to rise, absence from frame."
        ),
        "mediaSource": {
            "s3Location": {
                "uri": "s3://welfare-raw/oakridge/enc07/2026/07/30/enc07_2026-07-30_0200.mp4",
                "bucketOwner": "123456789012",
            }
        },
        "temperature": 0,
        "maxOutputTokens": 2048,
        # Structured output — removes the need for a second LLM pass in many cases
        "responseFormat": {"jsonSchema": {
            "type": "object",
            "properties": {
                "observations": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "t_start_s":  {"type": "number"},
                        "t_end_s":    {"type": "number"},
                        "behaviour":  {"type": "string"},
                        "severity":   {"type": "string", "enum": ["none","low","medium","high"]},
                        "confidence": {"type": "number"},
                    },
                    "required": ["t_start_s","behaviour","severity"],
                }},
                "animals_visible": {"type": "integer"},
            },
            "required": ["observations"],
        }},
    }),
)
body = json.loads(resp["body"].read())
# NOTE: with responseFormat, `message` is a JSON *string* — parse it again.
findings = json.loads(body["message"])
```

> **Design note worth stealing:** `responseFormat.jsonSchema` is native to Pegasus on Bedrock. ZooVision's brief routes Pegasus prose → GPT-5.6 for structuring. You can collapse that to **one** call for the machine-readable triage payload, and keep GPT-5.6 only for the human-facing *phrasing* of the alert and the 06:00 briefing. Fewer hops, lower latency, fewer failure modes, and cheaper.

**Marengo 3.0 async embedding (for the "seen this before?" retrieval path):**

```python
inv = brt.start_async_invoke(
    modelId="twelvelabs.marengo-embed-3-0-v1:0",
    modelInput={
        "inputType": "video",
        "video": {                                   # ← 3.0 uses NESTED structure
            "mediaSource": {"s3Location": {
                "uri": "s3://welfare-clips/tiger_amara/evt_01J.mp4",
                "bucketOwner": "123456789012"}},
            "segmentation": {"method": "dynamic", "dynamic": {"minDurationSec": 4}},
            "embeddingOption": ["visual", "audio"],
            "embeddingScope": ["clip", "asset"],
        },
    },
    outputDataConfig={"s3OutputDataConfig": {"s3Uri": "s3://welfare-analysis/embeddings/"}},
)
# -> inv["invocationArn"]; poll get_async_invoke(); results land in S3 as JSON
```

**2.7 → 3.0 migration is breaking.** Input structure moved from flat to nested; `embeddingOption` values changed (`visual-text|visual-image|audio` → `visual|audio|transcription`); dimension dropped 1024→512; and **embeddings from 2.7 are not compatible with 3.0** — you must regenerate. Start on 3.0.

### 2.2 Does Bedrock beat the TwelveLabs free tier?

**Answer: they're not comparable, and that's the point.** TwelveLabs' direct free tier is a fixed 10-hour pool that runs out. Bedrock has **no free video pool at all** — it is pure pay-per-use — but it is also **not capped at 10 hours**. So Bedrock is a genuine *overflow* path, not a cheaper one.

`⚠️ UNVERIFIED — pricing:` The [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) has a TwelveLabs section but the tables did not render for me. Third-party/marketplace sources indicate Pegasus around **$0.042/min indexing + $0.021/min input video + $0.0075/1k output tokens**, and Marengo video input around **$0.0007/sec (~$0.042/min)**. Treat these as order-of-magnitude only. **Confirm in the Bedrock console before you rely on a budget number.** At ~$0.02–0.04/video-minute, one enclosure overnight (8 h) ≈ **$10–20/night/enclosure** — which is the dominant cost in this whole system and the reason the pre-filter in §6.2 matters.

`⚠️ UNVERIFIED — quotas:` TwelveLabs models are **not listed** in the [Bedrock quotas reference](https://docs.aws.amazon.com/general/latest/gr/bedrock.html); that page explicitly redirects you to the [Service Quotas console](https://console.aws.amazon.com/servicequotas/home/services/bedrock/quotas). Check `InvokeModel requests per minute for twelvelabs.pegasus-1-2-v1:0` there and request an increase *now*, not on demo night. Geo/global inference profiles raise effective throughput by spreading across regions.

### 2.3 Bedrock Mantle — the claim is **TRUE**

The brief's "OpenAI-compatible Mantle endpoint reachable with a Bedrock API key" smelled invented. **It is real and it is GA.** From [docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html):

> "Amazon Bedrock provides the OpenAI Responses API via the `bedrock-mantle` endpoint, powered by Mantle, a distributed inference engine for large-scale machine learning model serving."

```bash
export OPENAI_BASE_URL="https://bedrock-mantle.us-west-2.api.aws/v1"
export OPENAI_API_KEY="<your Bedrock API key>"   # NOT an OpenAI key
```

- **Regions (14):** us-east-1, us-east-2, us-west-2, ap-southeast-3, ap-south-1, ap-southeast-2, ap-northeast-1, eu-central-1, eu-west-1, eu-west-2, eu-south-1, eu-north-1, sa-east-1, us-gov-west-1.
- **APIs:** OpenAI **Responses**, OpenAI **Chat Completions**, and **Anthropic Messages**.
- **Auth:** Bedrock API key (required for the OpenAI SDK) or SigV4 for raw HTTP. Create one at Bedrock console → API keys.
- **Quotas are separate** from `bedrock-runtime` — see `quotas-mantle.md`.

**GPT-5.6 is on Bedrock.** [GPT-5.6 Sol/Terra/Luna went GA on Bedrock ~July 9 2026](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.html); Terra is positioned as "everyday production work at half the cost of GPT-5.5"; 272k-token context. Model IDs use the `openai.` prefix — the confirmed example form is `openai.gpt-5.6-sol`, served on `openai/v1/responses` on `bedrock-mantle`.

`⚠️ UNVERIFIED:` I confirmed the `openai.gpt-5.6-sol` ID form and that Terra exists and is GA, but did **not** fetch a page printing the literal string `openai.gpt-5.6-terra`. Resolve it at runtime rather than hardcoding:

```python
from openai import OpenAI
client = OpenAI()  # picks up OPENAI_BASE_URL + OPENAI_API_KEY
print([m.id for m in client.models.list().data if "5.6" in m.id])
```

**Two ZooVision consequences.** (1) You can serve *both* the video model and the text model from one AWS account, one credential, one bill, one CloudTrail — a materially better story for the host sponsor than half-on-AWS. (2) **Privacy:** Mantle's Responses API defaults to `store: true`, retaining input+output for **30 days**. Animal care records and keeper contact details are sensitive operational data. **Set `store=False` on every request.**

```python
resp = client.responses.create(
    model="openai.gpt-5.6-terra",
    input=[{"role": "user", "content": prompt}],
    store=False,          # ← REQUIRED for ZooVision: no 30-day retention
)
```

---

## 3. Bedrock AgentCore: Runtime, Memory, Gateway, Identity, Observability

AgentCore is **GA (since Oct 2025)** and is now far larger than the brief's four components. Per [what-is-bedrock-agentcore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) there are **13** services: Harness, Runtime, Memory, Gateway, Identity, Code Interpreter, Browser, Observability, Payments, Evaluations, Optimization, **Policy**, and **Registry**.

### 3.1 Runtime — every brief claim confirmed

From [agents-tools-runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html), verbatim:

- **"long-running workloads up to 8 hours"** ✅ exactly as the brief claims.
- **Session isolation:** each session in a dedicated **microVM**; on completion the microVM is terminated and memory sanitized.
- **Payloads:** **100 MB** — enough to pass video bytes inline if you ever need to.
- **Protocols:** HTTP, MCP, A2A, AG-UI; plus **WebSocket bidirectional streaming**.
- **Billing:** CPU billed only during active processing — **"typically eliminating charges during I/O wait periods when agents are primarily waiting for LLM responses."** ZooVision is almost entirely I/O wait on TwelveLabs. This is close to ideal.
- **Persistent filesystem** across session stop/resume; BYO filesystem from **S3 Files or EFS** (May 2026).
- **Architecture: ARM64 (Graviton) only.**

**The 8-hour number has a catch the brief omits.** From [runtime-long-run](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html):

> "A session in idle state (`"Healthy"`) for **15 minutes** gets automatically terminated. A session returning `"HealthyBusy"` remains alive beyond the idle timeout."

So 8 hours is a *ceiling*, not a grant. You get it only by actively reporting `HealthyBusy` via `/ping`. **This is why you must not implement the 20-minute escalation timer as "hold the agent session open and sleep" (see §6.3).** Also: don't block in `@app.entrypoint`, because that blocks the `/ping` thread and your session dies at 15 minutes.

**Quotas** (raised **July 1 2026**, [announcement](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-bedrock-agentcore-increases-default-runtime-quota-limits/)):

| Quota | Now | Was |
|---|---|---|
| Active concurrent sessions | **5,000** (us-east-1/us-west-2), 2,500 elsewhere | 1,000 / 500 |
| `InvokeAgentRuntime` rate | **200 TPS** per agent per account | 25 TPS |
| New sessions (container) | 400 TPM per endpoint | 100 TPM |
| New sessions (direct code) | 25 TPS per endpoint | — |

Vastly more than a hackathon needs. **No quota increase required.**

**Regions (~20):** us-east-1, us-east-2, us-west-2, ca-central-1, eu-central-1, eu-west-1/2/3, eu-north-1, eu-south-1/2, ap-south-1, ap-southeast-1/2, ap-northeast-1/2, ap-southeast-3 (Bangkok/Malaysia added Jul 2026), sa-east-1, and GovCloud (US-West).

> ⚠️ **Region-intersection trap for ZooVision.** AgentCore Runtime ✅ + `bedrock-mantle` ✅ + Pegasus **in-region** ✅ intersect cleanly in **`us-east-1`**. In `us-west-2` (the AgentCore CLI default) Pegasus is geo/global-only. **Recommendation: run everything in `us-east-1`** — Runtime, Mantle, Pegasus in-region, Marengo in-region, and the highest session quota. Keep S3 buckets there too so video never leaves the region.

### 3.2 Memory

[Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) gives short-term (turn-by-turn within a session) and long-term (extracted insights across sessions) memory, with strategies including `SEMANTIC`. April 2026 added **structured metadata filtering** on long-term memory; March 2026 added resource-based policies and record streaming.

**ZooVision recommendation: skip it for v1.** Neo4j Aura is already your graph of record for animals, enclosures, events and rules. Running AgentCore Memory in parallel gives you two sources of truth and a reconciliation bug at 02:00. If you want the AWS-depth points, use Memory for exactly one narrow thing: **per-animal behavioural baselines** ("Amara normally rises 3–4×/night") as `SEMANTIC` long-term records keyed by `actor_id = animal_id`. That is a genuinely memory-shaped problem and demos well.

### 3.3 Gateway

[Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) turns **OpenAPI, Smithy, and Lambda** into MCP tools behind one endpoint, with inbound *and* outbound auth, semantic tool search, and 1-click connectors (Slack, Jira, Salesforce…). 2026 additions: HTTP passthrough targets, inference targets (model routing), AgentCore Runtime targets (GA Jun 2026), MCP sessions, response streaming.

Two things make Gateway worth it for ZooVision despite the extra hop:

1. **It is the enforcement point for AgentCore Policy** (§6.5) — the no-actuator guarantee lives here, not in your prompt.
2. **The 1-click Slack connector** is your fastest real alert channel (§6.4).
3. You can **enforce that Runtime only accepts invocations originating from your Gateway** (`aws:SourceArn` for SigV4, `allowedWorkloadConfiguration` for JWT), so nothing can bypass policy.

### 3.4 Identity

[Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html) handles agent identity plus inbound (Cognito/Okta/Entra/Auth0) and outbound (OAuth + API key) auth. **June 2026: Credential Providers can now reference an existing AWS Secrets Manager secret ARN directly** — so ZooVision keeps its own KMS keys, rotation and tagging on the TwelveLabs/OpenAI/Neo4j secrets and just points Identity at the ARN. July 2026 added Private Key JWT where the private key never leaves KMS and every signing op is in CloudTrail.

Identity is **free when used through Runtime or Gateway** ($0.010/1k tokens standalone).

### 3.5 Observability

[Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) emits **OTEL-compatible** telemetry into **CloudWatch** — session count, latency, duration, token usage, error rates — plus a trace-visualization dashboard for Runtime. Confirms the brief's "CloudWatch + OTEL" claim.

**You must enable CloudWatch Transaction Search first**, or traces will not appear. This is the #1 "my observability is empty" cause.

---

## 4. Deploying the ZooVision orchestrator to AgentCore Runtime

### 4.1 ⚠️ The deploy toolchain changed — this is the brief's biggest staleness problem

The brief's programming model (`BedrockAgentCoreApp`, `@app.entrypoint`, `agent.stream_async`) is **still correct and still documented** — [response-streaming.html](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html) (HTTP 200) shows exactly it:

```python
from strands import Agent
from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
async def agent_invocation(payload):
    user_message = payload.get("prompt", "No prompt found in input...")
    stream = agent.stream_async(user_message)
    async for event in stream:
        yield event

if __name__ == "__main__":
    app.run()
```

**But the deployment CLI is different now.** The **AgentCore CLI went GA in March 2026** and is a **Node/npm package driving AWS CDK** — not the older Python `bedrock-agentcore-starter-toolkit` with `agentcore configure` / `agentcore launch`:

```bash
npm install -g @aws/agentcore     # Node.js 20+; repo: github.com/aws/agentcore-cli
agentcore --help
```

Commands: `create`, `dev`, `deploy`, `invoke`, `add`, `logs`, `traces`, `status`, `remove`, `evals`, `package`, `validate`.

### 4.2 Concrete ZooVision deploy path

```bash
# Prereqs: AWS creds, Node 20+, Python 3.10+, AWS CDK, `cdk bootstrap` done once.
export AWS_REGION=us-east-1        # see the region-intersection trap in §3.1

# 1. Scaffold. CodeZip = no Docker needed (big hackathon win).
agentcore create --name ZooVisionOrchestrator \
  --framework Strands --protocol HTTP \
  --model-provider Bedrock --memory none --build CodeZip

cd ZooVisionOrchestrator

# 2. Iterate locally with hot reload + a browser inspector on :8080
agentcore dev
agentcore dev "Triage enc07 segment 2026-07-30_0200"

# 3. Enable CloudWatch Transaction Search in the console FIRST, then deploy
agentcore deploy --dry-run
agentcore deploy -y

# 4. Test + observe
agentcore invoke --prompt "Triage enc07_2026-07-30_0200.mp4" --stream
agentcore logs
agentcore traces list
agentcore status                    # prints the Runtime ARN

# 5. Optional extras
agentcore add memory --name AnimalBaselines --strategies SEMANTIC
agentcore add credential --name TwelveLabsKey --type api-key --api-key "$TL_KEY"

# 6. Teardown (two steps — remove from config, then deploy the removal)
agentcore remove all && agentcore deploy
```

Generated layout:

```
ZooVisionOrchestrator/
  agentcore/
    agentcore.json      # project + agent config
    aws-targets.json    # account/region targets
    .env.local          # local env vars (gitignored)
  app/ZooVisionOrchestrator/
    main.py             # entrypoint
    pyproject.toml
```

**Build types.** `CodeZip` (default) zips code to S3 — **no Docker**, fastest path, use this. `Container` needs a Docker image and **must be ARM64** (Graviton). Don't reach for Container unless you need system libs (e.g. bundling ffmpeg into the agent itself — but don't; ffmpeg belongs in the Lambda of §6.2, not the agent).

**Invoking from your own code:**

```python
import boto3, json, uuid
c = boto3.client("bedrock-agentcore", region_name="us-east-1")
r = c.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/ZooVision-xxxx",
    runtimeSessionId=str(uuid.uuid4()),
    payload=json.dumps({"prompt": "..."}).encode(),
    qualifier="DEFAULT",
)
print(b"".join(chunk for chunk in r["response"]).decode())
```

Caller needs `bedrock-agentcore:InvokeAgentRuntime`. Logs land in `/aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT`.

**Common failures** (from the AWS troubleshooting list): model access not enabled in the Bedrock console; region mismatch between `aws configure` and `aws-targets.json`; CDK not bootstrapped; port 8080 already in use locally.

### 4.3 Should ZooVision even use AgentCore Runtime?

Honest answer: **the pipeline doesn't need it, but the sponsor story does — and the async pattern makes it genuinely correct.** A 15-min-segment triage is a ~1–3 minute job that Lambda or Fargate handles fine. What Runtime buys you: agent-native tracing, session isolation per enclosure, idle-free CPU billing during long TwelveLabs waits, and — with the async pattern below — the ability to answer the keeper's phone *immediately* while analysis continues.

Use the documented async task API so a long Pegasus call doesn't get you killed at 15 minutes:

```python
import threading
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@tool
def analyze_segment(s3_uri: str) -> str:
    """Kick off Pegasus analysis without blocking the /ping health thread."""
    task_id = app.add_async_task("pegasus_analysis", {"uri": s3_uri})

    def work():
        try:
            run_pegasus_and_triage(s3_uri)   # minutes of I/O wait
        finally:
            app.complete_async_task(task_id) # back to "Healthy"
    threading.Thread(target=work, daemon=True).start()
    return f"Analysis started for {s3_uri} (task {task_id})."

agent = Agent(tools=[analyze_segment])

@app.entrypoint
def main(payload):
    # MUST NOT BLOCK — blocking here blocks /ping and kills the session at 15 min
    return {"message": agent(payload.get("prompt", "")).message}

if __name__ == "__main__":
    app.run()
```

---

## 5. Agent Toolkit for AWS / AWS MCP servers (build-time accelerator)

**Every URL in the brief resolves. I curl'd all of them:**

| Claimed URL | HTTP |
|---|---|
| `aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/` | **200** ✅ |
| `github.com/aws/agent-toolkit-for-aws` | **200** ✅ |
| `aws.amazon.com/about-aws/whats-new/2026/05/agent-toolkit/` | **200** ✅ |
| `docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html` | **200** ✅ |
| `github.com/awslabs/agent-plugins` | **200** ✅ |
| `github.com/awslabs/mcp` | **200** ✅ |

Launch: **"Announcing Agent Toolkit for AWS — help AI coding agents build effectively on AWS," May 6 2026**, with **40+ skills**. There's now also a [full user guide](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/what-is-agent-toolkit.html) and, since June 2026, [AWS CLI support](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-cli-agent-toolkit/).

**Four components** (per the user guide): **AWS MCP Server** (managed, 300+ services, docs search needs no auth, API calls use your IAM creds, `run_script` for sandboxed Python); **Agent skills** (loaded on demand so they don't burn context — the brief's claim is correct); **Plugins** (single-install bundles for Claude Code and Codex); **Rules files** (project guardrails).

**Install for Claude Code:**

```bash
/plugin install aws-core@claude-plugins-official      # full-stack app dev on AWS
/plugin install aws-agents@claude-plugins-official    # ⭐ building agents on AgentCore
```

Other plugins: `aws-data-analytics`, `aws-agents-for-devsecops`. Non-plugin agents: `npx skills add aws/agent-toolkit-for-aws/skills`. Kiro connects to the MCP server directly with no plugin. Repo is Apache-2.0, ~2.2k stars.

**Pricing:** "You can use the Agent Toolkit for AWS at no additional charge. You pay only for the AWS resources your agent provisions or interacts with." The brief's claim is confirmed verbatim.

**For ZooVision specifically: install `aws-agents`, not just `aws-core`.** It targets exactly your problem (building production agents on AgentCore) and — decisively — the model writing your code has a **May 2026 cutoff**, which is *before* half of what's in this document. AgentCore Harness went GA in June 2026. The AgentCore CLI changed shape. GPT-5.6 landed in July. Without the toolkit your coding agent will confidently write the deprecated `agentcore configure/launch` commands.

**Two governance features worth knowing** (they matter in §6.5): the AWS MCP Server injects the condition keys **`aws:ViaAWSMCPService`** and **`aws:CalledViaAWSMCP`** on every request, so you can write IAM policy that treats agent-initiated calls differently from human ones; and all calls are in CloudTrail. There's also a dedicated **AWS Secrets Manager "safe secrets handling"** integration (June 2026) so the toolkit won't splash your TwelveLabs key into a transcript.

Also relevant: **`awslabs/mcp`** hosts the broader AWS MCP server collection, and an **AgentCore MCP Server** was added there in April 2026.

---

## 6. The supporting AWS architecture

### 6.1 S3 layout, lifecycle & encryption

Three buckets, three retentions. Put all of them in **us-east-1** with the compute.

```bash
for B in welfare-raw welfare-clips welfare-analysis; do
  aws s3api create-bucket --bucket $B --region us-east-1
  aws s3api put-public-access-block --bucket $B \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
  aws s3api put-bucket-encryption --bucket $B \
    --server-side-encryption-configuration '{
      "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms",
        "KMSMasterKeyID":"alias/zoovision"},"BucketKeyEnabled":true}]}'
done
```

**Lifecycle (7 / 90 / 30 days):**

```bash
aws s3api put-bucket-lifecycle-configuration --bucket welfare-raw \
  --lifecycle-configuration '{"Rules":[{
    "ID":"raw-7d","Status":"Enabled","Filter":{"Prefix":""},
    "Expiration":{"Days":7},
    "AbortIncompleteMultipartUpload":{"DaysAfterInitiation":1}}]}'

aws s3api put-bucket-lifecycle-configuration --bucket welfare-clips \
  --lifecycle-configuration '{"Rules":[{
    "ID":"clips-90d","Status":"Enabled","Filter":{"Prefix":""},
    "Expiration":{"Days":90}}]}'

aws s3api put-bucket-lifecycle-configuration --bucket welfare-analysis \
  --lifecycle-configuration '{"Rules":[{
    "ID":"analysis-30d","Status":"Enabled","Filter":{"Prefix":""},
    "Expiration":{"Days":30}}]}'
```

Lifecycle facts that bite people ([expire-general-considerations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html)):

- **Do NOT add a storage-class transition to these buckets.** Expiring an object out of Standard-IA/One Zone-IA before 30 days still bills 30 days; Glacier Flexible bills 90; Deep Archive bills 180. `welfare-raw` at 7 days and `welfare-analysis` at 30 days must stay in **S3 Standard** or the "cheap tier" costs you *more*.
- Expiration is **asynchronous** — objects vanish some time after the date. **You are not charged for expiration or for storage after expiry.**
- "An object is eligible for only one S3 Lifecycle action per day."
- **A bucket policy cannot stop lifecycle deletion** — "even if your bucket policy denies all actions for all principals, your S3 Lifecycle configuration still functions as normal." So lifecycle is not a place to encode retention *policy* you care about legally; it's a cost control.
- Rules apply to **existing** objects too, immediately.
- Add `AbortIncompleteMultipartUpload` — the segmenter uploading large MP4s will leave orphaned parts you'd otherwise pay for forever.

**Encryption: use SSE-KMS with a customer-managed key, and turn on S3 Bucket Keys.** SSE-S3 is free but gives you no key policy, no per-key CloudTrail, and no way to say "this key is for animal welfare footage." Footage plus care records plus staff contacts is exactly the sensitive-operational-data case where a judge asks "who could read this?" **`BucketKeyEnabled: true` is not optional** — without it KMS charges $0.03/10k requests *per object*, and 15-min segments across many enclosures means a lot of objects. Bucket Keys collapse that by up to 99%.

**Event notifications → Lambda vs EventBridge.** From [EventNotifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html): destinations are SNS, SQS, Lambda, and EventBridge; delivery is **at-least-once**, "typically in seconds but can sometimes take a minute or longer."

**Recommendation: enable EventBridge on `welfare-raw`, not a direct Lambda trigger.** Direct-to-Lambda is one fewer moving part, but S3 direct notifications can't overlap prefixes for the same event type, you get one destination per configuration, and you can't fan out or filter richly later. EventBridge gives you content-based filtering (e.g. only `.mp4`, only certain enclosures), multiple targets (watcher Lambda + audit archive), and free replay. It also unifies with the Scheduler work in §6.3.

```bash
aws s3api put-bucket-notification-configuration --bucket welfare-raw \
  --notification-configuration '{"EventBridgeConfiguration":{}}'

aws events put-rule --name zoovision-new-segment \
  --event-pattern '{
    "source":["aws.s3"],
    "detail-type":["Object Created"],
    "detail":{"bucket":{"name":["welfare-raw"]},
              "object":{"key":[{"suffix":".mp4"}]}}}'
```

⚠️ **Loop hazard, called out explicitly in the AWS docs:** if a notification writes back to the bucket that triggered it, the function triggers itself. ZooVision is safe *because* raw/clips/analysis are three separate buckets. Keep it that way — do not "simplify" to one bucket with prefixes.

**Presigned URLs for TwelveLabs' URL-upload path** — and a trap:

```python
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "welfare-clips", "Key": "tiger_amara/evt_01J.mp4"},
    ExpiresIn=3600,
)
```

From [using-presigned-url](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html): **"A presigned URL expires at either its configured expiration time or when its associated credentials expire, whichever occurs first."** IAM *user* keys give up to 7 days; **IAM role credentials — which is what Lambda and AgentCore Runtime have — expire with the role session.** So `ExpiresIn=604800` from a Lambda silently yields a URL that dies early. For ZooVision's short-lived TwelveLabs fetch, `ExpiresIn=3600` from the Lambda role is fine and correct. Never put a presigned URL in the SMS/Slack body expecting it to work tomorrow morning — regenerate on demand for the 06:00 briefing.

Because presigned URLs are bearer tokens over animal-welfare footage, add a signature-age cap to the bucket policy:

```json
{ "Sid": "DenyStalePresignedURLs", "Effect": "Deny", "Principal": {"AWS": "*"},
  "Action": "s3:GetObject", "Resource": "arn:aws:s3:::welfare-clips/*",
  "Condition": {"NumericGreaterThan": {"s3:signatureAge": "3600000"}} }
```

**⭐ Missed opportunity: S3 Vectors.** [GA since Dec 2025](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/), in **31 regions** as of March 2026, up to **2 billion vectors per index**, ~100 ms queries, and "up to 90% lower cost" than a dedicated vector DB. ZooVision already generates Marengo embeddings — S3 Vectors lets you do "has Amara done this before?" retrieval **with no vector database to run, in the bucket you already have.** Marengo 3.0's 512-dim output makes it cheaper still. This is a one-afternoon addition that turns a linear pipeline into something that learns, and the brief never mentions it.

### 6.2 The segmenter & watcher (Lambda vs Fargate vs MediaConvert)

**Segmenter — stays outside AWS, on-prem next to the cameras.** RTSP pulled across the internet to the cloud is the wrong shape: bandwidth, NAT, and a camera outage becoming an AWS problem. Run ffmpeg on a box (or Greengrass device) at the facility:

```bash
ffmpeg -rtsp_transport tcp -i "rtsp://cam-enc07/stream1" \
  -c copy -f segment -segment_time 900 -reset_timestamps 1 \
  -strftime 1 -movflags +faststart \
  "enc07_%Y-%m-%d_%H%M.mp4"
```

> **`-movflags +faststart` is load-bearing, not cosmetic.** It puts the `moov` atom at the front of the file. That is what makes the byte-range trick in the clip cutter below work. Without it, ffmpeg must read the *whole* 450 MB file to find the index, and your 30-second clip extraction goes from ~3 seconds to ~45 and may time out. Set it now.

Then `aws s3 cp --recursive` (or `s3 sync`) into `s3://welfare-raw/{facility}/{enclosure}/{yyyy}/{mm}/{dd}/`.

**Watcher — Lambda, no question.** EventBridge rule (§6.1) → Lambda that parses the key, writes a `segment_seen` row, and invokes the AgentCore Runtime. This is a ~200 ms function. 128 MB, 30 s timeout.

**Clip cutter — Lambda with an ffmpeg layer. Not MediaConvert, not Fargate.**

The job is: cut 30 seconds out of a 15-minute MP4. With `-c copy` this is a **stream copy** — no re-encode, no CPU to speak of, purely I/O. The decisive trick is that **ffmpeg can read directly from a presigned HTTPS URL**, and `-ss` *before* `-i` seeks rather than decodes, so it downloads only the bytes it needs:

```python
import os, subprocess, boto3
s3 = boto3.client("s3")

def cut_clip(src_bucket, src_key, start_s, dur_s, dst_bucket, dst_key):
    src_url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": src_bucket, "Key": src_key}, ExpiresIn=900)
    out = f"/tmp/{os.path.basename(dst_key)}"
    subprocess.run([
        "/opt/bin/ffmpeg", "-y",
        "-ss", str(max(0, start_s - 3)),   # 3 s of pre-roll context for the keeper
        "-i", src_url,                     # ← reads over HTTPS, ranged
        "-t", str(dur_s + 6),
        "-c", "copy", "-movflags", "+faststart",
        out,
    ], check=True, capture_output=True, timeout=120)
    s3.upload_file(out, dst_bucket, dst_key,
                   ExtraArgs={"ServerSideEncryption": "aws:kms",
                              "SSEKMSKeyId": "alias/zoovision"})
    os.remove(out)
    return f"s3://{dst_bucket}/{dst_key}"
```

**Config: 2048 MB memory, 120 s timeout, 512 MB `/tmp` (the default) is plenty** — a 30-second `-c copy` clip is single-digit MB. Lambda memory also scales network and CPU allocation, which is why 2048 MB beats 512 MB here even though the work is I/O-bound; you pay for fewer milliseconds so it's often cost-neutral.

**Layer vs container:** ffmpeg is ~70–80 MB, comfortably inside Lambda's 250 MB unzipped limit, so a **layer is the right call** — no ECR, no Docker, no ARM/x86 juggling. Use a container image only if you end up bundling more media tooling. Lambda supports up to 10 GB memory, 10 GB `/tmp`, 10 GB images, and a **hard 15-minute ceiling**.

**Why not MediaConvert:** it's a job-queue service with per-job submission latency in the tens of seconds and a minimum billing duration, priced per output minute. For a 30-second stream copy that's slower *and* more expensive than Lambda, with a much heavier API. MediaConvert earns its place for transcoding ladders and packaging — neither of which ZooVision does.

**Why not Fargate:** no cold-start advantage worth the ECS/ALB/task-definition overhead for a 3-second job, and you'd pay for idle.

> **⭐ The cost lever the brief is missing.** At ~$0.02–0.04/video-minute (§2.2), sending *every* 15-minute segment to Pegasus is the dominant cost — roughly $10–20 per enclosure per night. Put a **cheap motion pre-filter in the watcher Lambda** before you ever call Bedrock. `ffmpeg -vf "select='gt(scene,0.1)'"`, or the even cheaper trick of reading per-segment bitrate (a still, sleeping animal in a fixed-camera scene compresses dramatically better than a pacing one). Overnight footage of a sleeping tiger is mostly nothing. A pre-filter that drops 70% of segments cuts your single largest line item by 70% and costs nothing but a few lines in a function you're already running.

### 6.3 Scheduling: 06:00 briefing & the 20-minute escalation timer

**Recommendation: EventBridge Scheduler for both.** For the escalation timer specifically, this hinges on a parameter the brief doesn't mention.

**06:00 morning briefing** — cron schedule in the facility's local timezone (Scheduler uses the IANA tz database and handles DST automatically):

```bash
aws scheduler create-schedule --name zoovision-morning-briefing \
  --schedule-expression 'cron(0 6 * * ? *)' \
  --schedule-expression-timezone 'America/Los_Angeles' \
  --flexible-time-window '{"Mode":"OFF"}' \
  --target '{
    "Arn":"arn:aws:lambda:us-east-1:123456789012:function:zoovision-briefing",
    "RoleArn":"arn:aws:iam::123456789012:role/ZooVisionSchedulerRole",
    "Input":"{\"facility\":\"oakridge\"}",
    "RetryPolicy":{"MaximumRetryAttempts":3,"MaximumEventAgeInSeconds":3600},
    "DeadLetterConfig":{"Arn":"arn:aws:sqs:us-east-1:123456789012:zoovision-dlq"}}'
```

DST note from the docs: a spring-forward cron on a non-existent local time is **skipped**, and fall-back runs **once**. 06:00 is safely outside the 02:00 transition window — a briefing scheduled at 02:30 would silently skip a day each March.

**The 20-minute escalation timer** — a **one-time schedule with `ActionAfterCompletion: DELETE`**:

```python
import boto3, json
from datetime import datetime, timedelta, timezone

sch = boto3.client("scheduler")

def arm_escalation(event_id, primary_keeper, backup_contact):
    fire_at = (datetime.now(timezone.utc) + timedelta(minutes=20)) \
              .strftime("%Y-%m-%dT%H:%M:%S")
    sch.create_schedule(
        Name=f"escalate-{event_id}",
        GroupName="zoovision-escalations",
        ScheduleExpression=f"at({fire_at})",
        ScheduleExpressionTimezone="UTC",
        ActionAfterCompletion="DELETE",        # ⭐ self-cleaning; see below
        FlexibleTimeWindow={"Mode": "OFF"},    # fire on time, not "within N min"
        Target={
            "Arn": "arn:aws:lambda:us-east-1:123456789012:function:zoovision-escalate",
            "RoleArn": "arn:aws:iam::123456789012:role/ZooVisionSchedulerRole",
            "Input": json.dumps({"event_id": event_id,
                                 "primary": primary_keeper,
                                 "backup": backup_contact}),
            "RetryPolicy": {"MaximumRetryAttempts": 3},
            "DeadLetterConfig": {"Arn": "arn:aws:sqs:us-east-1:123456789012:zoovision-dlq"},
        },
        ClientToken=f"esc-{event_id}",         # idempotent: at-least-once S3 events
    )

def acknowledge(event_id):
    """Keeper tapped ACK — cancel the pending escalation."""
    try:
        sch.delete_schedule(Name=f"escalate-{event_id}", GroupName="zoovision-escalations")
    except sch.exceptions.ResourceNotFoundException:
        pass   # already fired, or already acked — both fine
```

The escalation Lambda re-checks the ack state in Neo4j/DynamoDB before paging the backup — belt and braces against a race between `delete_schedule` and the fire time.

**Why this wins.** From the [schedule-types docs](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html): *"A one-time schedule still counts against your account quota after it has completed running... We recommend deleting your one-time schedules after they've completed."* The naive version of this design slowly fills your account with dead schedules. **`ActionAfterCompletion: DELETE`** ([CreateSchedule API](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_CreateSchedule.html), valid values `NONE | DELETE`) makes it self-cleaning — AWS deletes the schedule after it fires. Combined with `delete_schedule()` on ack, you never accumulate garbage in either branch. Precision is **60 seconds**, which is irrelevant for a 20-minute human timer.

**Compared against the alternatives:**

| Option | Verdict |
|---|---|
| **EventBridge Scheduler one-time + `ActionAfterCompletion: DELETE`** | ⭐ **Recommended.** ~15 lines. Cancel = one API call. Self-cleaning. Built-in retry + DLQ. No polling, no idle compute, effectively free. Trivially auditable — a pending escalation is a *listable resource*, which is exactly what "every alert must be auditable" wants. |
| Step Functions `Wait` state | Technically excellent — a `Wait` plus `TaskToken` callback is the textbook pattern, and gives you a visual execution history judges like. But it means authoring a state machine, IAM for it, and Standard-workflow state-transition costs, to model *one timer*. Reach for it only if escalation grows to 3+ tiers with branching. |
| DynamoDB TTL | ❌ **Wrong tool.** TTL deletion is explicitly best-effort and commonly lags **up to 48 hours**. A welfare escalation that might fire two days late is worse than no escalation. Do not use TTL as a timer. |
| Hold the AgentCore session open and sleep 20 min | ❌ Actively harmful. Burns a session against quota, and per §3.1 you'd have to keep returning `HealthyBusy` to avoid the 15-minute idle kill — paying for CPU and risking the whole triage dying because a *notification* is pending. Timers do not belong in agents. |

Use a dedicated **schedule group** (`zoovision-escalations`) so escalations are listable and auditable separately from the briefing, and so cleanup is one call.

### 6.4 Alert delivery to a keeper's phone

**This is the part of the brief most likely to fail on demo day, and it's an AWS-specific trap.**

**Amazon SNS SMS will not work for you in time.** Two independent blockers:

1. **US destinations require a registered origination identity** — sender ID, short code, **10DLC**, or **toll-free**. Without one you get `no origination identity available`. Registration timelines from the [AWS End User Messaging docs](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-10dlc.html): 10DLC brand 1–2 business days (up to 3 weeks non-US), vetting 1–2 days (up to 3 weeks), **campaign up to 4 weeks**, number up to 10 days. Toll-free: **"It can take up to 15 business days for your registration to be processed."** Carriers block unregistered toll-free SMS. **A hackathon does not have 4 weeks.**
2. **New accounts are in the SMS sandbox**: **$1/month** spend limit, **10** verified destination numbers, verified-only recipients, and production access needs an AWS Support case (~24 h initial response).

**Amazon Pinpoint is being retired — do not build on it.** [End of support **October 30 2026**](https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html); new customers blocked since May 20 2025. The brief's instinct to check this was right. Nuance: the **transactional SMS/push/voice APIs live on as AWS End User Messaging** and need no migration; what's dying is the engagement layer (campaigns, journeys, segments, templates, analytics). ZooVision only wants transactional, so **AWS End User Messaging is the correct long-term AWS service** — it just can't be provisioned fast enough for this weekend.

**AWS End User Messaging push (APNs/FCM)** would be lovely for "push alert with a clip," but it requires you to ship and sign a real mobile app. Not happening this weekend.

**Recommendation: a two-channel `notify()` port. Slack for the demo, Twilio for the real phone. Keep both behind one interface.**

```python
# zoovision/notify.py — one port, swappable adapters. Ship this shape.
from typing import Protocol

class Notifier(Protocol):
    def send(self, *, to: str, title: str, body: str, clip_url: str | None) -> str: ...

class SlackNotifier:      # ⭐ demo channel: instant, free, renders the clip inline
    def __init__(self, webhook_url): self.url = webhook_url
    def send(self, *, to, title, body, clip_url):
        import json, urllib.request
        payload = {"text": f"*{title}*\n{body}" + (f"\n<{clip_url}|▶ watch clip>" if clip_url else "")}
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req).read().decode()

class TwilioNotifier:     # real phone: number provisioned in minutes, MMS carries the clip
    def __init__(self, sid, token, from_): ...
    def send(self, *, to, title, body, clip_url): ...

class EndUserMessagingNotifier:  # the AWS-native path, once registration completes
    def send(self, *, to, title, body, clip_url):
        import boto3
        return boto3.client("pinpoint-sms-voice-v2").send_text_message(
            DestinationPhoneNumber=to,
            OriginationIdentity="arn:aws:sms-voice:...:phone-number/...",
            MessageBody=f"{title}: {body} {clip_url or ''}",
            MessageType="TRANSACTIONAL",
        )["MessageId"]
```

Why Slack is the *right* demo channel, not a cop-out: it renders the clip inline (SMS can't), it gives you a threaded audit trail for free, and **interactive buttons give you the ACK path** the 20-minute escalation needs — an "Acknowledge" button posts to a Lambda URL that calls `delete_schedule()`. Building that over SMS means parsing inbound replies and a two-way number. AgentCore Gateway also has a **1-click Slack connector**, so this doubles as sponsor depth.

**Always publish every alert to an SNS topic too** — with email and an HTTPS subscription — as the durable audit fan-out. SNS *email* has none of the SMS registration problems. That satisfies "every alert must be auditable" independent of which phone channel works.

⚠️ **Do not put a raw presigned URL in an SMS/Slack message and assume it lasts.** Per §6.1 it dies with the Lambda role session. Send a short link to a tiny authenticated Lambda Function URL that redirects to a *freshly minted* presigned URL. That also gives you a click log — who opened the clip, when — which is real auditability.

### 6.5 Secrets, IAM & the no-actuator guarantee

**Secrets: use SSM Parameter Store `SecureString` for the hackathon, Secrets Manager for production.**

Secrets Manager is **$0.40/secret/month + $0.05/10k API calls**. Parameter Store **Standard tier is $0.00** and does KMS encryption via `SecureString`. For three credentials (TwelveLabs, OpenAI/Bedrock, Neo4j) that's $1.20/mo vs $0 — trivial in absolute terms, but Parameter Store is also *less* setup. Secrets Manager earns its price when you need **automatic rotation**, cross-account resource policies, or the AgentCore Identity integration; Neo4j Aura credentials in a real deployment want rotation, so plan to graduate.

```bash
aws ssm put-parameter --name /zoovision/twelvelabs/api_key --type SecureString \
  --key-id alias/zoovision --value "$TL_KEY"
aws ssm put-parameter --name /zoovision/neo4j/uri --type SecureString --value "$NEO4J_URI"
aws ssm put-parameter --name /zoovision/neo4j/password --type SecureString --value "$NEO4J_PW"
```

```python
import boto3, functools
ssm = boto3.client("ssm")

@functools.lru_cache(maxsize=None)          # cache: you pay per API call
def secret(name: str) -> str:
    return ssm.get_parameter(Name=f"/zoovision/{name}",
                             WithDecryption=True)["Parameter"]["Value"]
```

Never bake keys into the AgentCore CodeZip. Use `agentcore add credential` or AgentCore Identity referencing a Secrets Manager ARN (June 2026 feature) so the agent never sees a literal.

**IAM: least privilege per role.** Four roles, each doing one job.

*Watcher Lambda:*

```json
{ "Version": "2012-10-17", "Statement": [
  { "Sid": "ReadRawSegmentsOnly", "Effect": "Allow",
    "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::welfare-raw/*" },
  { "Sid": "WriteClipsAndAnalysis", "Effect": "Allow",
    "Action": ["s3:PutObject"],
    "Resource": ["arn:aws:s3:::welfare-clips/*","arn:aws:s3:::welfare-analysis/*"] },
  { "Sid": "NoDeletesAnywhere", "Effect": "Deny",
    "Action": ["s3:DeleteObject","s3:DeleteObjectVersion","s3:PutBucketLifecycleConfiguration"],
    "Resource": "*" },
  { "Sid": "InvokeOrchestrator", "Effect": "Allow",
    "Action": ["bedrock-agentcore:InvokeAgentRuntime"],
    "Resource": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/ZooVision*" },
  { "Sid": "ReadOwnSecrets", "Effect": "Allow",
    "Action": ["ssm:GetParameter","ssm:GetParameters"],
    "Resource": "arn:aws:ssm:us-east-1:123456789012:parameter/zoovision/*" },
  { "Sid": "UseZooVisionKey", "Effect": "Allow",
    "Action": ["kms:Decrypt","kms:GenerateDataKey"],
    "Resource": "arn:aws:kms:us-east-1:123456789012:key/KEY-ID" }
]}
```

*Agent execution role — Bedrock scoped to exactly three models, including the geo profiles:*

```json
{ "Version": "2012-10-17", "Statement": [
  { "Sid": "OnlyTheThreeModelsWeUse", "Effect": "Allow",
    "Action": ["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream",
               "bedrock:StartAsyncInvoke","bedrock:GetAsyncInvoke"],
    "Resource": [
      "arn:aws:bedrock:us-east-1::foundation-model/twelvelabs.pegasus-1-2-v1:0",
      "arn:aws:bedrock:us-east-1::foundation-model/twelvelabs.marengo-embed-3-0-v1:0",
      "arn:aws:bedrock:*::foundation-model/openai.gpt-5.6-*",
      "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.twelvelabs.pegasus-1-2-v1:0"
    ]}
]}
```

> ⚠️ **Easy-to-miss IAM detail:** when you invoke via a **geo/global inference profile** you need permission on the **inference-profile ARN** *and* on the underlying foundation-model ARNs in every destination region the profile can route to. An IAM policy that only names `foundation-model/twelvelabs.pegasus-1-2-v1:0` in `us-east-1` will `AccessDenied` the moment the `us.` profile routes your request to Ohio. This is the second most likely demo-night failure after the region trap in §2.1.

**The "no actuator tools" guarantee — defend it in three layers.**

Layer 1 — **there are no actuator APIs in the account.** Attach a **permissions boundary** to every ZooVision role with an explicit `Deny` on the whole class of things that move physical objects or reach devices:

```json
{ "Version": "2012-10-17", "Statement": [
  { "Sid": "ZooVisionIsObserveOnly", "Effect": "Deny",
    "Action": ["iot:*","iotdata:*","iotevents:*","greengrass:*",
               "ssm:SendCommand","ssm:StartSession","ssmmessages:*",
               "ec2:RunInstances","ec2:TerminateInstances",
               "iam:*","organizations:*","kms:ScheduleKeyDeletion"],
    "Resource": "*" }
]}
```

A boundary cannot be escaped by any policy attached later, including one an agent might try to attach. This is the layer that makes the claim *structurally* true rather than merely intended.

Layer 2 — ⭐ **AgentCore Policy (Cedar).** This is the brief's biggest missed win. [Policy went **GA in March 2026**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) and does precisely what ZooVision promises: every tool call routes through Gateway and is evaluated against Cedar policy **before** execution, and — critically — the docs are explicit that enforcement happens **"at the boundary outside of agent's code — ensuring consistent, deterministic enforcement that remains reliable regardless of how the agent is implemented."** No prompt injection can talk its way past it, because the policy engine never reads the prompt. Every decision is logged to CloudWatch. You can author in Cedar or in natural language (which is then validated against the tool schema with automated reasoning that flags overly-permissive policies).

Default-deny with an explicit read-only allowlist:

```cedar
// Default deny is implicit in Cedar. Enumerate the ONLY permitted tools.
permit (
  principal == AgentCore::Agent::"ZooVisionOrchestrator",
  action    in [AgentCore::Action::"analyze_segment",
                AgentCore::Action::"cut_clip",
                AgentCore::Action::"query_graph",
                AgentCore::Action::"send_alert",
                AgentCore::Action::"read_animal_record"],
  resource
);

// Belt and braces: even if a write-shaped tool is ever registered, forbid it.
forbid (
  principal == AgentCore::Agent::"ZooVisionOrchestrator",
  action    in [AgentCore::Action::"open_gate",
                AgentCore::Action::"actuate_door",
                AgentCore::Action::"dispense_feed",
                AgentCore::Action::"set_temperature"],
  resource
);
```

`forbid` beats `permit` in Cedar, so the second block is unconditional. **This is a far stronger claim than "we didn't give the agent any actuator tools" — it's "the enforcement point is outside the agent, is deterministic, and every decision is audited."** Say that to judges.

June 2026 added **Bedrock Guardrails inside Policy**, evaluating gateway inputs/outputs for prompt injection, harmful content and sensitive-data exposure — again at the gateway layer "where the agent cannot reason around them." For a system holding staff contact details, PII-blocking Guardrails on tool outputs is close to free.

Layer 3 — **provenance.** The Agent Toolkit's MCP server stamps `aws:ViaAWSMCPService` / `aws:CalledViaAWSMCP` on every request, and March 2026 added extra IAM condition keys for Runtime. Use these to separate "the agent did this" from "a human did this" in policy and in CloudTrail.

### 6.6 Observability & the audit trail

**Enable CloudWatch Transaction Search before you deploy** or your traces will be empty. Then `agentcore logs` and `agentcore traces list` work, and the CloudWatch console gives you the Runtime trace/trajectory dashboard.

**`rule_fired` — emit it as a structured EMF log line, not a print.** One line gives you a queryable audit record *and* a free CloudWatch metric:

```python
import json, time, logging
log = logging.getLogger()

def audit_rule_fired(*, event_id, animal_id, enclosure_id, rule, severity,
                     inputs, decision, model_ids, clip_uri):
    log.info(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "ZooVision",
                "Dimensions": [["rule", "severity"], ["enclosure_id"]],
                "Metrics": [{"Name": "rule_fired", "Unit": "Count"}],
            }],
        },
        "rule_fired": 1,
        "event_id": event_id, "animal_id": animal_id,
        "enclosure_id": enclosure_id, "rule": rule, "severity": severity,
        "decision": decision,            # "alert" | "suppress" | "escalate"
        "inputs": inputs,                # the deterministic triage inputs
        "model_ids": model_ids,          # provenance: which models produced this
        "clip_uri": clip_uri,
        "schema_version": 1,
    }))
```

Then the audit query is one Logs Insights statement:

```
fields @timestamp, event_id, animal_id, rule, severity, decision, clip_uri
| filter rule_fired = 1
| filter severity in ["high","medium"]
| sort @timestamp desc
```

**Recording `model_ids` is the detail that makes this a real audit trail.** Six months from now "why did we wake a keeper at 03:00?" must be answerable, and the answer depends on *which* Pegasus and *which* GPT-5.6 produced the finding. Version-pin and log it.

Four things to add, cheaply:

- **CloudWatch alarm on `rule_fired` == 0 for 3 hours during night shift.** A silent pipeline looks identical to a peaceful night. This is the alarm that actually protects animals.
- **A second alarm on escalations fired** — if the backup contact is being paged often, triage is miscalibrated.
- **CloudTrail data events on the three buckets** — who read the footage. For sensitive operational data this is the access log you'll be asked for.
- **AgentCore Evaluations** (GA March 2026) if you have time: scores agent trajectories against a dataset. Being able to say "our triage agent scores X on a labelled set of welfare events" is a strong judging answer, and it works on Strands traces.

---

## 7. Cost model for a hackathon and for one facility

**Hackathon (2 days, 1–2 enclosures, heavy iteration).** New AWS accounts get **$100 in credits immediately, up to $200 total** over 6 months ([aws.amazon.com/free](https://aws.amazon.com/free/)); AgentCore's pricing page also references up to $200 in Free Tier credits for new customers. **30+ services are always-free within monthly limits.**

⚠️ **Read this before you sign up for a fresh account:** the AWS Free plan **"closes on its own 6 months after you open it or when your credits run out, whichever comes first."** Do not put a project you want to keep on a throwaway Free-plan account.

| Item | Estimate |
|---|---|
| AgentCore Runtime | ~$0.30 — a few hundred invocations × ~1 vCPU-min; **idle/I-O-wait is free**, and ZooVision is mostly waiting |
| Pegasus on Bedrock | **$5–30** — the entire budget. ~10–20 test segments × 15 min × ~$0.02–0.04/min `⚠️ UNVERIFIED` |
| Marengo embeddings | ~$1–3 |
| GPT-5.6 Terra via Mantle | <$1 |
| Lambda | **$0** (1M free requests/mo) |
| S3 | **$0.10** (a few GB for 2 days) |
| EventBridge Scheduler | **~$0** (~$1.00/1M invocations) |
| SSM Parameter Store | **$0** (Standard tier) |
| CloudWatch | ~$1 (logs + Transaction Search) |
| Secrets Manager (if used) | $1.20 |
| Agent Toolkit | **$0** |
| **Total** | **≈ $10–40 — comfortably inside $100 of credits** |

**The only real risk is re-running Pegasus over the same long segments while debugging.** Two mitigations, both cheap: cache analysis JSON in `welfare-analysis/` keyed by content hash and short-circuit on hit; and debug against 30-second clips, not 15-minute segments. Set an **AWS Budgets alert at $25** on day one.

**One facility, steady state — 12 enclosures, 10 h/night, 30 nights:**

| Item | Monthly |
|---|---|
| Pegasus, **no pre-filter** (12 × 10 h × 30 = 3,600 h = 216,000 min) | **$4,300–8,600** `⚠️ UNVERIFIED` |
| Pegasus, **with a 70%-effective motion pre-filter** (§6.2) | **$1,300–2,600** |
| S3 `welfare-raw` (7-day rolling, ~12 × 10 h × 7 × ~1.8 GB/h ≈ 1.5 TB) | ~$35 |
| S3 `welfare-clips` + `welfare-analysis` | ~$5 |
| AgentCore Runtime (~8,600 sessions) | ~$20–50 |
| AgentCore Memory (baselines) | ~$5 |
| Lambda + EventBridge + CloudWatch | ~$15 |
| GPT-5.6 Terra | ~$20–40 |
| S3 Vectors (if adopted) | ~$5 |
| End User Messaging SMS (~500 alerts + $2 TFN lease) | ~$5 |
| **Total** | **≈ $1,400–2,800/mo with pre-filter; $4,400–8,800 without** |

**The headline finding: video model inference is ~95% of the run cost, and everything else is rounding error.** The motion pre-filter is not an optimization — it's the difference between a system a sanctuary can afford and one it can't. Say this in the pitch; it shows you thought past the demo.

---

## 8. Gotchas, deprecations & region gaps

1. **Pegasus 1.2 is in-region only in `us-east-1` and `ap-northeast-2`.** In `us-west-2` (the AgentCore CLI default region!) you must use `us.` or `global.` prefixes. **Most likely demo-night failure.**
2. **Inference-profile IAM.** Geo/global profiles need permission on the profile ARN *and* the foundation-model ARNs in every destination region. Second most likely failure.
3. **Run everything in `us-east-1`.** Only there do AgentCore Runtime + `bedrock-mantle` + Pegasus in-region + Marengo in-region + the highest session quota all intersect.
4. **AgentCore's 8 hours requires `HealthyBusy`.** Idle sessions die at **15 minutes**. Never block in `@app.entrypoint` — it blocks `/ping`.
5. **Marengo Embed 2.7 is deprecating,** and its embeddings are **not compatible** with 3.0. Start on 3.0 (nested request structure, new `embeddingOption` values, 512-dim).
6. **Amazon Pinpoint: end of support October 30 2026.** Use **AWS End User Messaging** for transactional SMS.
7. **SNS/EUM SMS needs a registered origination number.** 10DLC ≈ 4–7 weeks; toll-free **up to 15 business days**. Plus SMS-sandbox limits ($1/mo, 10 verified numbers). **Not achievable this weekend.**
8. **Bedrock Mantle defaults to `store: true`, retaining data 30 days.** Set `store=False` for ZooVision.
9. **Mantle has separate quotas** from `bedrock-runtime`. Being fine on one says nothing about the other.
10. **One-time schedules count against quota after firing.** Always set `ActionAfterCompletion: DELETE`.
11. **DynamoDB TTL is not a timer** — deletion can lag up to 48 h.
12. **Don't add storage-class transitions** to 7-day or 30-day buckets: IA bills a 30-day minimum, Glacier 90, Deep Archive 180.
13. **Presigned URLs die with their credentials.** From Lambda/Runtime (role creds), `ExpiresIn=7 days` silently doesn't work.
14. **`-movflags +faststart` in the segmenter** or ranged clip extraction degenerates into full-file downloads.
15. **S3 events are at-least-once and can take "a minute or longer."** Make the watcher idempotent (`ClientToken`, content-hash dedupe).
16. **A bucket policy cannot block lifecycle deletion.**
17. **SSE-KMS without `BucketKeyEnabled: true`** charges KMS per object — expensive at 15-min segment granularity.
18. **CloudWatch Transaction Search must be enabled** before AgentCore traces appear.
19. **AgentCore Runtime is ARM64 only.** Container builds must be `linux/arm64`.
20. **The AgentCore CLI is npm, not pip** (`npm install -g @aws/agentcore`), and needs Node 20+ **and** the AWS CDK bootstrapped. The old `agentcore configure`/`launch` commands are gone.
21. **A new AWS Free-plan account auto-closes** at 6 months or when credits run out.
22. **AgentCore is SOC 1/2/3 compliant** (June 2026) — worth saying out loud given sensitive footage.

---

## 9. Corrections to the ZooVision brief

**Headline: the brief is accurate. All 7 claim groups verified, all 6 disputed URLs return 200, and the "invented-smelling" Mantle endpoint is real.** The corrections below are staleness and omissions.

| Brief claim | Verdict | Reality | Source |
|---|---|---|---|
| AgentCore Runtime with `BedrockAgentCoreApp`, `@app.entrypoint`, `agent.stream_async`, **8 hours**, managed containers/scaling | ✅ **confirmed** | Verbatim: "long-running workloads up to **8 hours**". GA since Oct 2025. Also 100 MB payloads, microVM isolation, ARM64, WebSocket streaming. **Caveat: sessions idle 15 min are terminated** — 8 h needs `HealthyBusy`. | [agents-tools-runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html), [runtime-long-run](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html) |
| Memory, Gateway, Identity, Observability + CloudWatch/OTEL | ✅ **confirmed, and understated** | All four exist and are GA. There are now **13** services — the brief misses **Policy**, Harness, Evaluations, Optimization, Registry, Payments, Browser, Code Interpreter. Observability is explicitly OTEL→CloudWatch. | [what-is-bedrock-agentcore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) |
| Agent Toolkit exists at 3 URLs; `aws-core` plugin; MCP server + skills; 300+ services; lazy skill loading; free | ✅ **confirmed on every point** | All 3 URLs **HTTP 200**. Launched **May 6 2026** with 40+ skills. `/plugin install aws-core@claude-plugins-official`. "No additional charge." Lazy loading confirmed verbatim. | [product page](https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/), [user guide](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/what-is-agent-toolkit.html), [repo](https://github.com/aws/agent-toolkit-for-aws) |
| TwelveLabs Marengo + Pegasus on Bedrock | ✅ **confirmed** | `twelvelabs.pegasus-1-2-v1:0` (`InvokeModel`), `twelvelabs.marengo-embed-2-7-v1:0` + `-3-0-v1:0` (`StartAsyncInvoke`). | [model-parameters-twelvelabs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html) |
| **"OpenAI-compatible Mantle endpoint with a Bedrock API key"** — flagged as probably invented | ✅ **confirmed — the brief was right and the suspicion was wrong** | `bedrock-mantle.{region}.api.aws/v1` is **real and GA**, in 14 regions, serving OpenAI Responses + Chat Completions + Anthropic Messages with a Bedrock API key. **GPT-5.6 Sol/Terra/Luna GA on Bedrock ~Jul 9 2026.** | [bedrock-mantle](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html), [GPT-5.6 Sol card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.html) |
| `response-streaming.html` exists | ✅ **confirmed** | HTTP 200; contains the exact Strands + `BedrockAgentCoreApp` + `stream_async` example. | [response-streaming](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html) |
| Two AWS ML blog URLs | ✅ **both confirmed** | "Strands Agents SDK: A technical deep dive…" (Jin Tan Ruan, **Jul 31 2025**); "Multi-Agent collaboration patterns with Strands Agents and Amazon Nova" (**Nov 11 2025**). | [1](https://aws.amazon.com/blogs/machine-learning/strands-agents-sdk-a-technical-deep-dive-into-agent-architectures-and-observability/), [2](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/) |
| *(implied)* deploy via `bedrock-agentcore-starter-toolkit`, `agentcore configure` / `launch` | ⚠️ **stale** | AgentCore CLI **GA Mar 2026**, now **npm**: `npm install -g @aws/agentcore`; commands are `create` / `dev` / `deploy` / `invoke`; CDK-based; needs Node 20+ and `cdk bootstrap`. | [runtime-get-started-cli](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) |
| *(implied)* Pegasus callable from any region with the bare model ID | ❌ **wrong** | In-region only `us-east-1` + `ap-northeast-2`. Elsewhere use `us.`/`eu.`/`global.` profiles. | [Pegasus v1.2 card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-twelvelabs-pegasus-v1-2.html) |
| "Bedrock quotas beat the TwelveLabs free 10-hour pool" | ⚠️ **half right** | Bedrock has **no free video tier** — it's pure pay-per-use, so not *cheaper*, but genuinely **uncapped** vs a 10-h pool. Valid overflow, not a discount. TwelveLabs quotas aren't in the quotas doc; check Service Quotas console. | [pricing](https://aws.amazon.com/bedrock/pricing/), [quotas](https://docs.aws.amazon.com/general/latest/gr/bedrock.html) |
| *(implied)* SMS to a keeper's phone via AWS | ❌ **won't work in hackathon timeframe** | US SMS needs a registered origination identity: 10DLC ≈ 4–7 weeks, toll-free ≤ 15 business days; new accounts are sandboxed ($1/mo, 10 verified numbers). Use Slack + Twilio. | [10DLC](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-10dlc.html), [TFN](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-tfn.html) |
| *(brief flags)* "Pinpoint undergoing EOL changes" | ✅ **confirmed** | End of support **Oct 30 2026**; new customers blocked since May 20 2025. Transactional SMS/push/voice continue as **AWS End User Messaging**; campaigns/journeys/segments are retired. | [Pinpoint EOS](https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html) |
| *(missing)* the no-actuator guarantee | ⚠️ **under-specified** | **AgentCore Policy (Cedar), GA Mar 2026**, intercepts every Gateway tool call and enforces "outside of agent's code… deterministic… regardless of how the agent is implemented," with CloudWatch audit logs. Far stronger than "we gave it no actuator tools." | [policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) |
| *(missing)* embedding storage | ⚠️ **gap** | **S3 Vectors GA Dec 2025**, 31 regions, 2B vectors/index, ~90% cheaper than a vector DB. Natural home for Marengo output; no DB to run. | [S3 Vectors GA](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/) |
| *(missing)* Pegasus structured output | ⚠️ **gap** | Pegasus supports `responseFormat.jsonSchema` natively — collapses the Pegasus→GPT-5.6 structuring hop for the machine-readable payload. | [model-parameters-pegasus](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-pegasus.html) |
| *(missing)* video-inference cost dominance | ⚠️ **gap** | Video inference is ~95% of run cost (~$4.3–8.6k/mo for 12 enclosures unfiltered). A motion pre-filter in the watcher is the single highest-leverage design decision. | §7 |

---

## 10. Open questions to resolve before demo day

1. **Confirm TwelveLabs-on-Bedrock pricing** in the Bedrock console. Everything in §7 rests on ~$0.02–0.04/video-minute, which I could not verify from an AWS page.
2. **Confirm the exact GPT-5.6 Terra model ID** via `client.models.list()` against `bedrock-mantle`. I verified the `openai.gpt-5.6-sol` form, not the literal Terra string.
3. **Check `InvokeModel` RPM for Pegasus** in Service Quotas and request an increase now. Not in the quotas doc.
4. **Decide Neo4j vs AgentCore Memory** as source of truth. Recommendation: Neo4j for facts/rules/events, Memory only for per-animal baselines.
5. **Verify a 15-min 1080p segment actually lands under Pegasus's limits** (1 h / <2 GB) and measure end-to-end latency — that number sets whether "night-shift alert" is credible.
6. **Pick and test the phone channel end-to-end tonight, not on demo day.** Including the ACK round-trip that calls `delete_schedule()`.
7. **Enable CloudWatch Transaction Search** before the first deploy.
8. **Measure the motion pre-filter's false-negative rate.** A filter that drops a real welfare event is worse than no filter. Tune for high recall, accept poor precision.
9. **Decide whether Gateway is in the demo path.** It's required for AgentCore Policy; if you skip Gateway you lose the strongest no-actuator argument.
10. **Set an AWS Budgets alert at $25** and confirm which account/credits you're on (remember Free-plan accounts auto-close).
11. **Confirm `cdk bootstrap` has run** in the target account/region — the most common `agentcore deploy` failure.
12. **Version-pin every model ID and log it** in `rule_fired`. Retroactive auditability depends on it.

---

## 11. Sources

**All URLs below were fetched on 2026-07-30. Nothing 404'd.** The six URLs the brief specifically asked me to test were additionally verified with `curl -sIL` — **all returned HTTP 200.**

### Brief-claim verification (all confirmed)
- [aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/](https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/) — **200.** Agent Toolkit exists; MCP server, skills, plugins, free, Claude Code/Codex/Kiro/Cursor.
- [github.com/aws/agent-toolkit-for-aws](https://github.com/aws/agent-toolkit-for-aws) — **200.** `aws-core` plugin confirmed; Apache-2.0; ~2.2k stars.
- [aws.amazon.com/about-aws/whats-new/2026/05/agent-toolkit/](https://aws.amazon.com/about-aws/whats-new/2026/05/agent-toolkit/) — **200.** Launch **May 6 2026**, 40+ skills, 3 plugins, no additional charge.
- [docs.aws.amazon.com/.../response-streaming.html](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/response-streaming.html) — **200.** Exact `BedrockAgentCoreApp` / `@app.entrypoint` / `stream_async` example.
- [github.com/awslabs/agent-plugins](https://github.com/awslabs/agent-plugins) — **200.**
- [github.com/awslabs/mcp](https://github.com/awslabs/mcp) — **200.** AWS MCP server collection.
- [Strands deep-dive blog](https://aws.amazon.com/blogs/machine-learning/strands-agents-sdk-a-technical-deep-dive-into-agent-architectures-and-observability/) — exists; Jin Tan Ruan, Jul 31 2025.
- [Multi-agent + Nova blog](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/) — exists; Nov 11 2025.

### Bedrock models
- [model-parameters-twelvelabs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html) — three models; which APIs each supports.
- [model-parameters-pegasus](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-pegasus.html) — `twelvelabs.pegasus-1-2-v1:0`; 1 h/<2 GB S3, 25 MB base64; full schema incl. `responseFormat.jsonSchema`.
- [Pegasus v1.2 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-twelvelabs-pegasus-v1-2.html) — **the region gap**: in-region only us-east-1 + ap-northeast-2; `us.`/`eu.`/`global.` profile IDs; `bedrock-runtime` only, not Mantle; boto3 sample.
- [model-parameters-marengo-3](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-marengo-3.html) — `twelvelabs.marengo-embed-3-0-v1:0`; 4 h/6 GB; 512-dim; **2.7 deprecation + incompatible embeddings**; nested request structure; `StartAsyncInvoke` + `s3OutputDataConfig`.
- [bedrock-mantle](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html) — **Mantle is real**; base URL, Bedrock API key, 14 regions, separate quotas, `store` 30-day retention.
- [GPT-5.6 Sol model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.html) — GPT-5.6 Sol/Terra/Luna GA on Bedrock (~Jul 9 2026), `openai.` prefix, 272k context.
- [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) — `gpt-oss` prices captured; **TwelveLabs and Nova tables did not render** → the `⚠️ UNVERIFIED` pricing labels.
- [Bedrock quotas reference](https://docs.aws.amazon.com/general/latest/gr/bedrock.html) — **TwelveLabs models absent**; redirects to Service Quotas console.

### AgentCore
- [what-is-bedrock-agentcore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) — all **13** services; consumption pricing.
- [agents-tools-runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html) — **8-hour** claim verbatim; 100 MB payloads; microVM; idle-free CPU billing.
- [runtime-long-run](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-long-run.html) — **15-min idle termination**; `/ping` `Healthy`/`HealthyBusy`; `add_async_task`; don't block the entrypoint.
- [runtime-getting-started](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-getting-started.html) + [runtime-get-started-cli](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-cli.html) — `npm install -g @aws/agentcore`; full command set; CodeZip vs Container; **ARM64**; CDK prereqs; log group paths; common failures.
- [github.com/aws/agentcore-cli](https://github.com/aws/agentcore-cli) — CLI repo; Node 20+; CDK-based.
- [memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) — short vs long term; strategies.
- [gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) — OpenAPI/Smithy/Lambda targets; semantic tool selection; Slack connector; in/out auth.
- [policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) — ⭐ Cedar; enforcement outside agent code; CloudWatch audit; natural-language authoring.
- [observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) — OTEL → CloudWatch; metrics list; dashboards.
- [AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/) — $0.0895/vCPU-h, $0.00945/GB-h; Memory $0.25/1k events, $0.75/1k records/mo, $0.50/1k retrievals; Gateway $0.005/1k; Identity $0.010/1k; Policy $0.000025/req; up to $200 new-customer credits.
- [AgentCore release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html) — GA dates: Policy + Evaluations + CLI (Mar 2026), Harness (Jun 2026), Registry preview (Apr 2026), Payments preview (May 2026), Guardrails-in-Policy + SOC compliance + Secrets Manager ARN references + Step Functions integration (Jun 2026), BYO filesystem S3/EFS (May 2026).
- [Runtime quota increase, Jul 1 2026](https://aws.amazon.com/about-aws/whats-new/2026/07/amazon-bedrock-agentcore-increases-default-runtime-quota-limits/) — 5,000/2,500 sessions; 200 TPS; before/after numbers.
- [agent-toolkit user guide](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/what-is-agent-toolkit.html) — 4 components; `aws:ViaAWSMCPService` / `aws:CalledViaAWSMCP`; pricing.
- ⚠️ [agentcore-regions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html) — page did not render for me; region list assembled from What's New posts instead (≈20 regions + GovCloud US-West).

### Supporting AWS services
- [S3 EventNotifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html) — destinations; at-least-once; "a minute or longer"; self-trigger loop warning.
- [S3 lifecycle expiration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html) — minimum-duration charges (30/90/180); one action per object per day; bucket policy can't block lifecycle; no charge after expiry.
- [S3 presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html) — **expiry bounded by credential lifetime**; 7 days max (IAM user) / role-session (Lambda); `s3:signatureAge`; FAQ on `ExpiredToken`.
- [EventBridge Scheduler schedule types](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html) — `at()`/`rate()`/`cron()`; 60 s precision; **one-time schedules count against quota after completion**; DST behaviour.
- [Scheduler CreateSchedule API](https://docs.aws.amazon.com/scheduler/latest/APIReference/API_CreateSchedule.html) — ⭐ **`ActionAfterCompletion: NONE | DELETE`**; RetryPolicy; DeadLetterConfig; ClientToken; KmsKeyArn.
- [10DLC registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-10dlc.html) — brand/vetting/campaign/number timelines (campaign up to 4 weeks).
- [Toll-free registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-tfn.html) — **"up to 15 business days"**; per-use-case restriction; revocation.
- [Pinpoint end of support](https://docs.aws.amazon.com/pinpoint/latest/userguide/migrate.html) — **Oct 30 2026**; new customers blocked May 20 2025; transactional → End User Messaging.
- [SNS SMS sandbox](https://docs.aws.amazon.com/sns/latest/dg/sns-sms-sandbox.html) — $1/mo, 10 verified numbers, production access via Support.
- [S3 Vectors GA](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/) + [17-region expansion](https://aws.amazon.com/about-aws/whats-new/2026/03/s3-vectors-expands-17-regions) — GA Dec 2025; 2B vectors/index; 31 regions.
- [AWS Free Tier](https://aws.amazon.com/free/) — $100 immediate + up to $200; **Free-plan accounts auto-close at 6 months**; 30+ always-free services.
- [Lambda ephemeral storage](https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html) — 512 MB–10,240 MB `/tmp`; 10 GB memory/image; 15-min ceiling.

### Marked `⚠️ UNVERIFIED`
1. **TwelveLabs pricing on Bedrock** — AWS pricing page tables didn't render; figures are third-party/marketplace. Searched: Bedrock pricing page, TwelveLabs pricing pages, AWS Marketplace listing.
2. **The literal `openai.gpt-5.6-terra` model ID** — confirmed Terra exists, is GA on Bedrock, and that IDs take the `openai.gpt-5.6-*` form; did not fetch a page printing the Terra string. Searched: GPT-5.6 model cards, OpenAI-on-Bedrock blog, `model-parameters-openai`.
3. **Per-model Bedrock quotas for TwelveLabs** — absent from the quotas reference, which redirects to the Service Quotas console (account-specific, not web-fetchable). Searched: `general/latest/gr/bedrock.html`, Bedrock quotas docs.
