# Strands Agents — ZooVision Sponsor Reference

> **Researched:** 2026-07-30 · **Verified against:** strands-agents v1.50.2 (PyPI, 2026-07-27T20:38:46Z) / strands-agents-tools v0.8.5 (PyPI, 2026-07-21T20:06:14Z)
> **Role in ZooVision:** Top-level orchestrator — owns the tool list, the day/night branch, the audit trail, and the overnight session; it never assigns severity.

---

## 0. Read this first — four things that changed since the brief was written

1. **The GitHub repo moved.** `strands-agents/sdk-python` is now **`strands-agents/harness-sdk`** — a monorepo containing `strands-py/` (Python) and `strands-ts/` (TypeScript). `strands-agents/sdk-typescript`, `strands-agents/docs`, `strands-agents/agent-builder`, and `strands-agents/mcp-server` are all **archived**. The PyPI package name is unchanged (`strands-agents`).
2. **`agent.structured_output()` is DEPRECATED.** It emits a `DeprecationWarning` in v1.50.2. The current API is `structured_output_model=<PydanticModel>` on the `Agent(...)` constructor or per invocation, read back off `result.structured_output`. **The brief's plan for `analyze_tool` uses the deprecated call.** See §4.
3. **`strandsagents.com/latest/…` is dead (404).** The docs moved to `strandsagents.com/docs/…`. Every URL the brief listed under the new scheme resolves — see §14.
4. **"Mantle" is real, not invented.** Amazon Bedrock ships an OpenAI-compatible endpoint at `https://bedrock-mantle.{region}.api.aws`, and `OpenAIResponsesModel` has a **first-class `bedrock_mantle_config=` kwarg** that mints AWS bearer tokens for you. This kwarg is in the v1.50.2 source but is **not** in the published docs. See §6.

---

## 1. Snapshot

| | |
|---|---|
| **What it is** | AWS's open-source, model-agnostic agent SDK ("agent harness"). Apache 2.0. Model-driven loop: you give it a model + tools + prompt; it runs the tool-use loop. Python **≥3.10** (tested to 3.14). |
| **Current version** | `strands-agents==1.50.2` (2026-07-27). `strands-agents-tools==0.8.5` (2026-07-21). SDK hit 1.0 on **2025-07-15**; ~50 minor releases in 12 months. Release cadence is roughly weekly. |
| **How ZooVision uses it** | Single `Graph` orchestrator per enclosure-night. Deterministic nodes (`ingest`, `triage`, `index`, `report`) are `MultiAgentBase` subclasses wrapping plain Python. LLM nodes (`analyze`, `alert`) are `Agent`s with `structured_output_model=`. Day/night is a **conditional edge** keyed on `invocation_state`. Audit trail comes from `AfterToolCallEvent` + `AfterNodeCallEvent` hooks. Overnight continuity comes from `GraphBuilder.set_session_manager()`. |
| **Key risk** | **Python `Graph` uses OR semantics on incoming edges** — a node fires when *any* dependency completes, not all. Every fan-in in ZooVision (e.g. `analyze` waiting on both Pegasus and Marengo) must carry an explicit AND condition or it will fire early with partial evidence. This is the single most likely silent bug. See §5 and §11. |
| **Secondary risk** | The SDK is on a ~weekly release train and the versioning policy explicitly permits "pay-for-play" breaking changes in minor versions. **Pin `strands-agents==1.50.2`.** |

**Install for ZooVision:**
```bash
pip install 'strands-agents==1.50.2' \
            'strands-agents-tools[twelvelabs]==0.8.5' \
            'strands-agents[openai]==1.50.2' \
            'openai>=2.0.0'          # NOT optional — see §11 gotcha #1
```

---

## 2. Core concepts & the agent loop

Top-level exports, copied from `strands-py/src/strands/__init__.py` @ `python/v1.50.2`:

```python
from strands import (
    Agent, AgentBase, AgentSkills, InterventionHandler, ModelRetryStrategy,
    MultiAgentPlugin, Plugin, PosixShellSandbox, Sandbox, Skill, Snapshot,
    tool, ToolContext,
)
from strands import agent, models, storage, telemetry, types
```

`Agent.__init__` — real signature, verbatim from `strands-py/src/strands/agent/agent.py:161`:

```python
def __init__(
    self,
    model: Model | str | None = None,
    messages: Messages | None = None,
    tools: list[Union[str, dict[str, str], "ToolProvider", Any]] | None = None,
    system_prompt: str | list[SystemContentBlock] | None = None,
    structured_output_model: type[BaseModel] | None = None,
    callback_handler: Callable[..., Any] | _DefaultCallbackHandlerSentinel | None = _DEFAULT_CALLBACK_HANDLER,
    conversation_manager: ConversationManager | None = None,
    record_direct_tool_call: bool = True,
    load_tools_from_directory: bool = False,
    trace_attributes: Mapping[str, AttributeValue] | None = None,
    *,
    agent_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    state: AgentState | dict | None = None,
    context_manager: ContextManagerStrategy | None = None,
    plugins: list[Plugin] | None = None,
    hooks: list[HookProvider | HookCallback] | None = None,
    interventions: list[InterventionHandler] | None = None,
    session_manager: SessionManager | None = None,
    memory_manager: MemoryManager | MemoryManagerConfig | None = None,
    structured_output_prompt: str | None = None,
    tool_executor: ToolExecutor | None = None,
    retry_strategy: ModelRetryStrategy | _DefaultRetryStrategySentinel | None = _DEFAULT_RETRY_STRATEGY,
    concurrent_invocation_mode: ConcurrentInvocationMode = ConcurrentInvocationMode.THROW,
    checkpointing: bool = False,
    sandbox: Sandbox | None = None,
): ...
```

Note: `model` accepts a **bare string**, which is interpreted as a **Bedrock** model id (`self.model = BedrockModel() if not model else BedrockModel(model_id=model) if isinstance(model, str) else model`). Passing `"gpt-5.6-terra"` as a string will silently build a `BedrockModel`, not an OpenAI one. Always pass a model *object* for ZooVision.

### Invocation surface

`__call__`, `invoke_async`, and `stream_async` all take the same keyword set (`agent.py:704`, `:786`, `:1071`):

```python
result = agent(prompt, *, invocation_state=None, structured_output_model=None,
               structured_output_prompt=None, idempotency_token=None, limits=None)
result = await agent.invoke_async(...)          # same kwargs
async for event in agent.stream_async(...):     # same kwargs, yields dict events
    ...   # final event is {"result": AgentResult}; text deltas arrive as event["data"]
```

`AgentResult` (`agent/agent_result.py`) is a dataclass:

```python
stop_reason: StopReason
message: Message
metrics: EventLoopMetrics
state: Any
interrupts: Sequence[Interrupt] | None = None
structured_output: BaseModel | None = None      # <-- ZooVision reads this
checkpoint: Checkpoint | None = None
```

`__str__` priority is: interrupts → `structured_output.model_dump_json()` → concatenated text blocks. So `str(result)` on a structured-output agent gives you JSON, which is handy but easy to mistake for prose.

### Per-invocation budget caps (`strands.types.agent.Limits`)

Real and very useful for ZooVision cost control on a 12-hour night:

```python
from strands.types.agent import Limits

result = agent(prompt, limits=Limits(turns=6, total_tokens=120_000))
# stop_reason becomes "limit_turns" / "limit_total_tokens" / "limit_output_tokens".
# No exception is raised. Token caps are SOFT — checked at turn boundaries.
```

### Retries

Default is on: `ModelRetryStrategy(max_attempts=6, initial_delay=4, max_delay=240)` → 4s → 8s → 16s → 32s → 64s. It is itself a `HookProvider`. Pass `retry_strategy=None` to disable, or subclass and override `is_retryable(exception)`.

---

## 3. Tools: `@tool` functions, tool specs, agents-as-tools

### `@tool` decorator — real signature (`strands-py/src/strands/tools/decorator.py:736`)

```python
def tool(
    func: Callable[P, R] | None = None,
    description: str | None = None,
    inputSchema: JSONSchema | None = None,
    name: str | None = None,
    context: bool | str = False,
) -> DecoratedFunctionTool[P, R] | Callable[[Callable[P, R]], DecoratedFunctionTool[P, R]]: ...
```

Behaviour verified from source + `docs/user-guide/concepts/tools/custom-tools/`:

- Metadata comes from the **function signature, type hints, and docstring** (`docstring-parser` is a hard dependency). Docstring → tool `description`; param docs → property descriptions.
- Both `@tool` and `@tool(...)` forms work.
- The decorated object is still callable as a normal Python function.
- Inputs are validated against a generated Pydantic model before your function runs (`self._metadata.validate_input(tool_input)`).
- `async def` tools are supported and **run concurrently**.
- `context=True` injects a `ToolContext` into a `tool_context` param (`context="ctx"` to rename it), giving access to the invoking agent, the `tool_use`, and `invocation_state`.
- Module-level `TOOL_SPEC` dicts are the alternative (older) style — this is what `strands_tools.chat_video` uses.

**Tool names must match `^[a-zA-Z0-9_\-]{1,}$`, max 64 chars** (`tools/tools.py:66`, enforced in `event_loop/streaming.py:79` via `validate_tool_use_name`).

### ZooVision's deterministic tools

```python
import json
from strands import tool

@tool
def triage_tool(events_json: str) -> dict:
    """Assign a severity tier to observed animal-welfare events using fixed rules.

    Args:
        events_json: JSON array of observation objects from analyze_tool.
    """
    events = json.loads(events_json)
    tier, rule = _run_rules(events)          # pure Python. No LLM. Ever.
    return {
        "status": "success",
        "content": [{"json": {"tier": tier, "rule_fired": rule, "event_count": len(events)}}],
    }
```

Returning the explicit `{"status", "content"}` dict is the documented `ToolResult` shape and is what you want for `triage_tool` — it makes `rule_fired` a first-class JSON field in the transcript rather than a stringified blob, which is exactly what the audit hook in §7 will pick up. (Returning a plain `str`/`dict` also works; Strands wraps it.)

### Agents-as-tools — **the brief is correct** ✅

`docs/user-guide/concepts/multi-agent/agents-as-tools/` documents **three** ways, and direct passing is listed as "the simplest way":

```python
# 1. Direct passing — the SDK auto-wraps via agent.as_tool() with defaults
orchestrator = Agent(
    system_prompt="Route queries to the right specialist.",
    tools=[research_agent, product_agent, travel_agent],
)

# 2. Explicit .as_tool() when you need to control the name/description/context
orchestrator = Agent(
    tools=[research_agent.as_tool(
        name="research_assistant",
        description="Answers research questions requiring factual information.",
    )],
)

# 3. @tool wrapper for full control (multiple params, pre/post-processing)
@tool
def research_assistant(query: str) -> str:
    """Process and respond to research-related queries."""
    agent = Agent(system_prompt=RESEARCH_ASSISTANT_PROMPT, tools=[retrieve, http_request])
    return str(agent(query))
```

`Agent.as_tool()` real signature (`agent/agent.py:958`):

```python
def as_tool(self, *, name: str | None = None, description: str | None = None,
            preserve_context: bool = False) -> AgentTool: ...
```

**Four gotchas the brief does not mention**, all read out of `agent/_agent_as_tool.py`:

1. **The generated tool has exactly one parameter: `input: str`.** The `tool_spec` is hard-coded to `{"input": {"type": "string"}}`. If `alert_tool` needs the tier *and* the clip URI *and* the enclosure id as separate args, direct passing cannot express that — use form 3 (`@tool` wrapper) or serialise into one JSON string.
2. **`name` defaults to `agent.name`, which defaults to the literal string `"Strands Agents"`** (`agent.py:123`, `_DEFAULT_AGENT_NAME`). That contains a space and therefore violates the tool-name pattern. **Always set `Agent(name="analyze_agent", description="…")`.**
3. **`preserve_context=False` (the default) raises `ValueError` if the sub-agent has a `session_manager`.** Verbatim: *"preserve_context=False cannot be used with an agent that has a session manager."* If ZooVision's sub-agents need overnight persistence, you must pass `preserve_context=True`.
4. **If the sub-agent has `structured_output_model`, the tool result is emitted as `{"json": result.structured_output.model_dump()}`** instead of text. This is excellent for ZooVision — the orchestrator receives `analyze_tool`'s `events[]` as real JSON, not a prose paraphrase.

Sub-agent interrupts propagate up to the parent via `ToolInterruptEvent` and are resumed automatically — relevant if you use interventions for the 20-minute escalation.

### Ready-made TwelveLabs tools — the brief missed these entirely

`strands-agents-tools` 0.8.5 ships first-party TwelveLabs tools:

| Tool | Model | Import |
|---|---|---|
| `chat_video` | **Pegasus** — natural-language Q&A over video | `from strands_tools import chat_video` |
| `search_video` | **Marengo** — semantic clip search, relevance 0.0–1.0 | `from strands_tools import search_video` |

`chat_video` params: `prompt` (required), then `oneOf` `video_id` / `video_path`, plus `index_id`, `temperature` (0.0–1.0), `engine_options: ["visual","audio"]`. It SHA-256-hashes uploads and caches them in a module-level `VIDEO_CACHE` to avoid re-uploading. `search_video` params: `query`, `index_id`, `group_by` (`video`|`clip`), `threshold` (`high`|`medium`|`low`|`none`), `page_limit`.

Env vars: **`TWELVELABS_API_KEY`** (required) and **`TWELVELABS_PEGASUS_INDEX_ID`** (fallback for `index_id`). Extra: `pip install 'strands-agents-tools[twelvelabs]'` → pulls `twelvelabs>=0.4.0,<1.0.0`.

⚠️ **Caveat for ZooVision:** these tools return *free-text* answers. They do **not** enforce a timestamped schema. ZooVision's schema-constrained Pegasus contract still needs either a raw `twelvelabs` SDK call inside your own `@tool` (recommended — you control the prompt and the response_format) or a post-hoc structured-output pass. Use `chat_video`/`search_video` as a fast demo path and a reference implementation, not as the production `ingest_tool`.

---

## 4. Structured output (how ZooVision enforces its JSON contracts)

### ❌ The brief's `agent.structured_output()` is deprecated

Verbatim from `agent/agent.py:856` (v1.50.2):

```python
warnings.warn(
    "Agent.structured_output method is deprecated."
    " You should pass in `structured_output_model` directly into the agent invocation."
    " see: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/",
    category=DeprecationWarning, stacklevel=2,
)
```

Both `structured_output()` and `structured_output_async()` are deprecated. The docs page confirms it in prose. It still *works* in 1.50.2, but do not build on it.

### ✅ The current API

```python
from pydantic import BaseModel, Field
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

class Observation(BaseModel):
    t_start_s: float = Field(description="Seconds from segment start")
    t_end_s: float
    animal_id: str | None = Field(default=None, description="Tag/collar id if identifiable")
    behavior: str = Field(description="Controlled-vocabulary behavior label")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(description="What in the frame supports this")

class AnalysisResult(BaseModel):
    enclosure_id: str
    segment_uri: str
    events: list[Observation]

analyze_agent = Agent(
    name="analyze_agent",
    description="Merges Pegasus observations and Marengo hits into a structured event list.",
    model=OpenAIResponsesModel(model_id="gpt-5.6-terra", client_args={"api_key": OPENAI_KEY}),
    system_prompt=ANALYZE_PROMPT,
    structured_output_model=AnalysisResult,        # <-- default for every call
)

result = analyze_agent(evidence_blob)
analysis: AnalysisResult = result.structured_output   # already validated
```

Per-invocation override and streaming both work:

```python
result = agent("…", structured_output_model=AnalysisResult)   # overrides the default

async for event in agent.stream_async("…", structured_output_model=AnalysisResult):
    if "result" in event:
        analysis = event["result"].structured_output
```

Also available: `structured_output_prompt=` (constructor or per-call) customises the nudge message Strands sends when the model *doesn't* spontaneously call the output tool. Default text: `"You must format the previous response as structured output."` Worth overriding for `analyze_tool` so the retry prompt mentions the timestamp contract.

Under the hood: `strands.tools.structured_output.convert_pydantic_to_tool_spec` turns your Pydantic model into a tool spec; `Model.structured_output(output_model, prompt, system_prompt)` is an abstract async generator each provider implements. `strands/models/_strict_schema.py` exists specifically to coerce schemas into OpenAI strict-mode form — so `OpenAIResponsesModel` + Pydantic is a well-trodden path, not a shim.

**ZooVision recommendation:** put `structured_output_model=` on the `analyze_agent` *constructor*. Then wrap it with `.as_tool(name="analyze_tool", …)` — the agent-as-tool adapter will emit `{"json": …}` (§3 gotcha 4), so the orchestrator gets the validated `events[]` contract with zero extra parsing and zero extra tokens.

---

## 5. Multi-agent primitives: Graph vs Swarm vs Workflow

### What actually exists — `strands-py/src/strands/multiagent/__init__.py` verbatim

```python
from .base import MultiAgentBase, MultiAgentResult, Status
from .graph import EdgeCondition, EdgeConditionWithContext, GraphBuilder, GraphResult
from .swarm import Swarm, SwarmResult

__all__ = ["EdgeCondition", "EdgeConditionWithContext", "GraphBuilder", "GraphResult",
           "MultiAgentBase", "MultiAgentResult", "Status", "Swarm", "SwarmResult"]
```

⚠️ **`Graph` and `GraphState` are NOT exported from `strands.multiagent`.** You must import them from the submodule:

```python
from strands.multiagent import GraphBuilder, Swarm, MultiAgentBase, MultiAgentResult, Status
from strands.multiagent.graph import Graph, GraphState        # <-- submodule
from strands.multiagent.base import NodeResult
```

| | **Graph** | **Swarm** | **Workflow** |
|---|---|---|---|
| Where | `strands.multiagent` (SDK) | `strands.multiagent` (SDK) | **`strands_tools.workflow`** — a *tool*, not an SDK class |
| Core concept | Developer-defined flowchart | Dynamic collaborative team, autonomous handoffs | Pre-defined task DAG run as one non-conversational tool |
| Execution | "Controlled but dynamic" | "Sequential & autonomous" | "Deterministic & parallel" |
| Cycles | Yes | Yes | No |
| Error handling | Controllable | Agent-driven | Systemic |

The brief's characterisation of all three is **correct**, including that `Workflow` lives in `strands-agents-tools`. Usage is `agent.tool.workflow(action="create"|"start"|"status", workflow_id=..., tasks=[...])`. **ZooVision should not use it** — it is an LLM-facing tool for agents that build their own pipelines, which is the opposite of the auditability ZooVision needs.

Swarm, for completeness (`from strands.multiagent import Swarm`): kwargs `entry_point`, `max_handoffs=20`, `max_iterations=20`, `execution_timeout=900`, `node_timeout=300`; agents hand off by calling an injected `handoff_to_agent()` tool. **The brief's "use Graph, not Swarm" call is right** — Swarm's routing is model-decided and therefore not auditable.

### `GraphBuilder` — real API (`multiagent/graph.py:301`+)

```python
class GraphBuilder:
    def add_node(self, executor: AgentBase | MultiAgentBase, node_id: str | None = None) -> GraphNode
    def add_edge(self, from_node: str | GraphNode, to_node: str | GraphNode,
                 condition: EdgeCondition | None = None) -> GraphEdge
    def set_entry_point(self, node_id: str) -> "GraphBuilder"
    def reset_on_revisit(self, enabled: bool = True) -> "GraphBuilder"
    def set_max_node_executions(self, max_executions: int) -> "GraphBuilder"
    def set_execution_timeout(self, timeout: float) -> "GraphBuilder"     # seconds
    def set_node_timeout(self, timeout: float) -> "GraphBuilder"          # seconds
    def set_graph_id(self, graph_id: str) -> "GraphBuilder"
    def set_session_manager(self, session_manager: SessionManager) -> "GraphBuilder"
    def set_hook_providers(self, hooks: list[HookProvider]) -> "GraphBuilder"
    def set_plugins(self, plugins: list[MultiAgentPlugin]) -> "GraphBuilder"
    def build(self) -> "Graph"
```

Note both timeouts are documented as **seconds** in the source docstrings. (One published docs page describes `set_node_timeout` in *milliseconds*; the source says `timeout: Individual node timeout in seconds`. Trust the source.)

If you don't call `set_entry_point`, `build()` auto-detects entry points as all nodes with no dependencies, and raises `ValueError("No entry points found - all nodes have dependencies")` if there are none. `build()` also logs a warning if neither `set_max_node_executions` nor `set_execution_timeout` is set.

### Conditional edges — **the brief is correct** ✅, and there are two signatures

```python
# multiagent/graph.py:66
class EdgeConditionWithContext(Protocol):
    def __call__(self, state: "GraphState", *, invocation_state: dict[str, Any], **kwargs: Any) -> bool: ...

LegacyEdgeCondition = Callable[["GraphState"], bool]
EdgeCondition = LegacyEdgeCondition | EdgeConditionWithContext
```

Dispatch is by **parameter name**: `_is_context_condition()` does `inspect.signature(condition)` and checks whether a parameter literally named `invocation_state` exists. Name it anything else and you silently get the legacy call. `invocation_state` is passed at invoke time:

```python
result = graph("task", invocation_state={"role": "admin", "enable_experimental": True})
```

**Verified in source:** the graph stores the caller's dict as `self._current_invocation_state` (`graph.py:641`) and passes *that same object* both to node executors (`graph.py:1017`, `:1042`) and to `edge.should_traverse(self.state, invocation_state=self._current_invocation_state)` (`graph.py:965`, `:1204`). So in-place mutation by a node is visible to downstream conditions within one invocation. ⚠️ Across interrupt/resume the docs say `invocation_state` is persisted with the checkpoint, but a source comment (`graph.py:1418-1422`) says resume evaluation uses "the invocation_state the caller passes on the resume invocation." **Don't rely on mutation for the day/night decision** — compute it deterministically at the call site and pass it in. That is also more auditable.

### ⚠️ OR semantics — the trap

> *"In Python, the default behavior is OR semantics — a target node fires when **any** incoming edge's source completes. Use conditional edges to explicitly wait for all dependencies."* — `graph.mdx`

The documented AND workaround, verbatim:

```python
from strands.multiagent.graph import GraphState
from strands.multiagent.base import Status

def all_dependencies_complete(required_nodes: list[str]):
    def check_all_complete(state: GraphState) -> bool:
        return all(
            node_id in state.results and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )
    return check_all_complete

builder.add_edge("A", "Z", condition=all_dependencies_complete(["A", "B", "C"]))
builder.add_edge("B", "Z", condition=all_dependencies_complete(["A", "B", "C"]))
builder.add_edge("C", "Z", condition=all_dependencies_complete(["A", "B", "C"]))
```

### ⚠️ Plain functions CANNOT be Graph nodes

`add_node(executor: AgentBase | MultiAgentBase, …)`. A `@tool`-decorated function is neither. To make ZooVision's `triage_tool` / `index_tool` / `report_tool` graph nodes, subclass `MultiAgentBase`. The docs sketch this as `FunctionNode` but the sample elides the metrics/timing fields with `# ...`. Here is a complete, working version built from the real dataclass definitions:

```python
import json, time
from typing import Any, Callable
from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.event_loop import Metrics, Usage


class FunctionNode(MultiAgentBase):
    """Run a deterministic Python callable as a Graph node. No LLM, no tokens."""

    def __init__(self, func: Callable[[str, dict[str, Any]], dict], node_id: str):
        super().__init__()
        self.id = node_id                     # add_node() reads .id for the default node_id
        self.func = func

    async def invoke_async(self, task, invocation_state=None, **kwargs) -> MultiAgentResult:
        started = time.time()
        payload = self.func(task if isinstance(task, str) else str(task), invocation_state or {})
        elapsed_ms = int((time.time() - started) * 1000)

        agent_result = AgentResult(
            stop_reason="end_turn",
            message={"role": "assistant", "content": [{"text": json.dumps(payload)}]},
            metrics=EventLoopMetrics(),
            state={},
        )
        return MultiAgentResult(
            status=Status.COMPLETED,
            results={self.id: NodeResult(
                result=agent_result, status=Status.COMPLETED, execution_time=elapsed_ms,
                accumulated_usage=Usage(inputTokens=0, outputTokens=0, totalTokens=0),
                accumulated_metrics=Metrics(latencyMs=elapsed_ms),
                execution_count=1,
            )},
            execution_count=1,
            execution_time=elapsed_ms,
        )
```

You only need `invoke_async` — `MultiAgentBase.stream_async` has a default implementation that awaits it and yields `{"result": result}`, which is exactly what `Graph._execute_node` looks for.

⚠️ **Reading a `MultiAgentBase` node's output in an edge condition is awkward.** `Graph` wraps the node's `MultiAgentResult` as `NodeResult(result=multi_agent_result, …)`, so `state.results["triage"].result` is a `MultiAgentResult`, not text — you'd have to call `.get_agent_results()[0].message` to dig out the payload. **Have `FunctionNode` write its verdict into `invocation_state` and read that in the condition.** Cleaner, cheaper, and auditable.

### Results

```python
result: GraphResult = graph("task")                      # or: await graph.invoke_async(...)
result.status                                            # Status.COMPLETED / FAILED / INTERRUPTED
result.execution_order                                   # list[GraphNode]  -> [n.node_id for n in ...]
result.results["triage"].result                          # AgentResult | MultiAgentResult | Exception
result.results["triage"].status
result.execution_time                                    # ms
result.accumulated_usage                                 # Usage across all nodes
result.total_nodes / completed_nodes / failed_nodes / interrupted_nodes
```

Streaming: `async for event in graph.stream_async(task, invocation_state=...)`. Event dicts include `{"type": "multiagent_node_start", "node_id", "node_type"}`, `{"type": "multiagent_node_stop", "node_id", "node_result"}`, and wrapped inner agent events — a ready-made source for the demo timeline UI.

`Graph.serialize_state()` / `deserialize_state(payload)` exist for manual checkpointing.

---

## 6. Model providers (pointing Strands at OpenAI + Bedrock)

`strands/models/__init__.py` eagerly exports only `BedrockModel`, `Model`, `BaseModelConfig`, `CacheConfig`, `CacheToolsConfig`; everything else is lazy-loaded via `__getattr__`. Available: `AnthropicModel`, `GeminiModel`, `LiteLLMModel`, `LlamaAPIModel`, `LlamaCppModel`, `MistralModel`, `OllamaModel`, `OpenAIModel`, `OpenAIResponsesModel`, `SageMakerAIModel`, `WriterModel`.

### `OpenAIResponsesModel` — **the brief is correct** ✅

Module path and class name are exactly as the brief claims. Real signature (`strands-py/src/strands/models/openai_responses.py:158`):

```python
from strands.models.openai_responses import OpenAIResponsesModel

class OpenAIResponsesModel(Model):
    class OpenAIResponsesConfig(BaseModelConfig, total=False):
        model_id: str
        params: dict[str, Any] | None
        stateful: bool
        use_native_token_count: bool
        # inherited from BaseModelConfig:
        context_window_limit: int | None

    def __init__(
        self,
        client_args: dict[str, Any] | None = None,
        bedrock_mantle_config: BedrockMantleConfig | None = None,
        **model_config: Unpack[OpenAIResponsesConfig],
    ) -> None: ...
```

So: **`model_id` ✅, `client_args` ✅, `params` ✅** — all three brief claims confirmed. Plus two the brief missed:
- `stateful=True` → server-side conversation state; **`agent.messages` stays empty** and the server holds history.
- `use_native_token_count=True` → calls OpenAI's `responses.input_tokens.count` for exact counts instead of the local estimator (silently falls back to estimation on error).

ZooVision:
```python
from strands.models.openai_responses import OpenAIResponsesModel

terra = OpenAIResponsesModel(
    model_id="gpt-5.6-terra",
    client_args={"api_key": os.environ["OPENAI_API_KEY"]},
    params={"max_output_tokens": 4096, "temperature": 0.2},
)
```
`gpt-5.6-terra` is a real model (OpenAI's mid-tier of the GPT-5.6 Luna/Terra/Sol family, released 2026-07-09; $1.25/$7.50 per Mtok as of 2026-07-30). It is also on Bedrock as `openai.gpt-5.6-terra`.

### `OpenAIModel` vs `OpenAIResponsesModel`

Two separate providers, two separate files:

| | `strands.models.openai.OpenAIModel` | `strands.models.openai_responses.OpenAIResponsesModel` |
|---|---|---|
| API | Chat Completions | **Responses** |
| openai SDK floor | `>=1.68.0` | **`>=2.0.0`, enforced at import time** |
| Server-side state | No | Yes (`stateful=True`) |
| OpenAI built-in tools | No | Yes via `params={"tools": [...]}` |

Module header verbatim: *"a superset of the Chat Completions API, with additional support for built-in tools, server-side conversation state management, and multi-modal inputs."*

Built-in tool support matrix, copied from the module docstring — **read this before promising anything in a demo**:

> - `web_search` (supported): Full support including URL citations.
> - `file_search` (partial): File citation annotations not emitted.
> - `code_interpreter` (partial): Executed code and stdout/stderr not surfaced.
> - `mcp` (partial): Approval flow and `mcp_list_tools`/`mcp_call` events not surfaced.
> - `shell` (partial): Local (client-executed) mode not supported.
> - `tool_search` (not supported): Requires `defer_loading` on function tools.
> - `image_generation` (not supported): Requires image content block delta support in the event loop.
> - `computer_use_preview` (not supported): Requires a developer-managed screenshot/action loop.

### Bedrock "Mantle" — **the brief is CONFIRMED, and it's better than claimed** ✅

Mantle is genuinely an AWS product name. From AWS docs (`bedrock-mantle.html`): *"Amazon Bedrock provides the OpenAI Responses API via the `bedrock-mantle` endpoint, powered by Mantle, a distributed inference engine."* Auth is a **Bedrock API key** as `OPENAI_API_KEY` with `OPENAI_BASE_URL=https://bedrock-mantle.<region>.api.aws/v1`. 14 regions inc. `us-east-1`, `us-east-2`, `us-west-2`. Separate token quotas from `bedrock-runtime`. Responses are stored 30 days by default (`store=true`) — **set `store=false` if zoo footage metadata shouldn't be retained.**

The published Strands docs show only the manual approach:

```python
region = "us-east-1"
model = OpenAIResponsesModel(
    model_id="openai.gpt-oss-120b",
    client_args={"api_key": "<BEDROCK_API_KEY>",
                 "base_url": f"https://bedrock-mantle.{region}.api.aws/v1"},
)
```

But v1.50.2 source has an **undocumented first-class kwarg** that is strictly better for an overnight run, because it **mints a fresh bearer token on every request** (`models/_openai_bedrock.py`):

```python
class BedrockMantleConfig(TypedDict, total=False):
    region: str                                  # else resolved from boto_session / boto3 chain
    boto_session: boto3.Session
    credentials_provider: CredentialProvider
    expiry: timedelta

# usage
model = OpenAIResponsesModel(
    model_id="openai.gpt-5.6-terra",
    bedrock_mantle_config={"region": "us-east-1"},
)
```

Module docstring, verbatim: *"Tokens are minted on demand via `aws_bedrock_token_generator.provide_token` so long-running agents survive the bearer token's maximum lifetime."* **This is the correct choice for ZooVision's 12-hour night** — a hard-coded Bedrock API key in `client_args` can expire mid-shift.

Two details from the source:
- **Base-path routing:** `_OPENAI_PATH_MODEL_PREFIXES = ("openai.gpt-5.",)`. Model ids starting `openai.gpt-5.` are served from **`/openai/v1`**; everything else (e.g. `openai.gpt-oss-*`) from **`/v1`**. The SDK picks this automatically from `model_id`. If you hand-roll `base_url` for `openai.gpt-5.6-terra` and use `/v1`, it will fail.
- Passing `api_key` or `base_url` in `client_args` *together with* `bedrock_mantle_config` raises `ValueError` at `__init__` (fail-fast).
- Requires `aws-bedrock-token-generator>=1.1.0`, which is in the `strands-agents[openai]` extra.

### Guardrails

Bedrock-native, via the model provider (not a separate Strands abstraction):

```python
from strands.models import BedrockModel
bedrock_model = BedrockModel(guardrail_id="…", guardrail_version="1", guardrail_trace="enabled")
agent = Agent(model=bedrock_model)
if response.stop_reason == "guardrail_intervened":
    ...   # conversation context is overwritten
```
There is **no** provider-agnostic guardrail layer. For OpenAI-backed nodes, ZooVision's safety story is the deterministic triage engine plus `interventions` (see §7), not Strands guardrails.

---

## 7. State, sessions, hooks & observability

### Agent state (in-process, JSON-serialisable, not sent to the LLM)

```python
agent = Agent(state={"enclosure_id": "E-07", "segments_seen": 0})
agent.state.get("enclosure_id")
agent.state.get()                    # whole dict
agent.state.set("last_tier", "amber")
agent.state.delete("last_tier")
# non-JSON-serialisable values raise ValueError
```

### Sessions (`strands.session`)

```python
from strands.session import FileSessionManager, S3SessionManager, RepositorySessionManager, SessionManager

agent = Agent(session_manager=FileSessionManager(session_id="E07-2026-07-30",
                                                 storage_dir="/var/zoovision/sessions"))

agent = Agent(session_manager=S3SessionManager(session_id="E07-2026-07-30",
                                               bucket="zoovision-sessions",
                                               prefix="production/"))
```
Messages **and** `agent.state` are persisted automatically. `RepositorySessionManager(session_id=..., session_repository=...)` lets you back it with your own store — for ZooVision that could be Neo4j itself, implementing `SessionRepository` (`create_session/read_session/create_agent/read_agent/update_agent/create_message/read_message/update_message/list_messages`).

For the graph:
```python
builder.set_session_manager(FileSessionManager(session_id="E07-2026-07-30"))
```

⚠️ **Two hard constraints, both verified in source:**
1. `_validate_node_executor` raises `ValueError("Session persistence is not supported for Graph agents yet.")` if any **`Agent` node** has its own `session_manager` (`graph.py:295-298`). Persistence lives on the **graph**, not on the nodes.
2. `add_node` raises `ValueError("Duplicate node instance detected. Each node must have a unique object instance.")` — you cannot reuse the same `Agent` object at two node ids.

⚠️ **Documentation bug:** `session-management.mdx` shows `Graph(agents={"researcher": agent1, ...}, session_manager=...)`. **`Graph.__init__` has no `agents=` parameter** — it takes `nodes`, `edges`, `entry_points`, …. Use `GraphBuilder(...).set_session_manager(...).build()`.

Also available: `checkpointing=True` on `Agent` (pauses at cycle boundaries with `stop_reason="checkpoint"`, resume by passing `{"checkpointResume": {"checkpoint": ...}}`), and `agent.take_snapshot()` / `agent.load_snapshot()`.

### Hooks — how ZooVision gets `rule_fired` into every alert trace

Exported from `strands.hooks` (v1.50.2) — **exactly these 12 event classes**:

`AgentInitializedEvent`, `BeforeInvocationEvent`, `AfterInvocationEvent`, `MessageAddedEvent`, `BeforeModelCallEvent`, `AfterModelCallEvent`, `BeforeToolCallEvent`, `AfterToolCallEvent`, `MultiAgentInitializedEvent`, `BeforeMultiAgentInvocationEvent`, `AfterMultiAgentInvocationEvent`, `BeforeNodeCallEvent`, `AfterNodeCallEvent`.

⚠️ The published hooks page also names `ModelStreamUpdateEvent`, `BeforeToolsEvent`, `AfterToolsEvent`, `ToolResultEvent`, `AgentResultEvent`, `NodeStreamUpdateEvent`, `NodeResultEvent`, `InterruptEvent`, `MultiAgentHandoffEvent`. Those are **either TypeScript-only or private `TypedEvent`s in `strands.types._events`** — not importable from `strands.hooks` in Python. Stick to the 12.

Key field sets (from `hooks/events.py`):

```python
@dataclass
class BeforeToolCallEvent(HookEvent, _Interruptible):
    selected_tool: AgentTool | None      # writable — swap the tool
    tool_use: ToolUse                    # writable
    invocation_state: dict[str, Any]
    cancel_tool: bool | str = False      # writable — set a string to cancel with that message

@dataclass
class AfterToolCallEvent(HookEvent):
    selected_tool: AgentTool | None
    tool_use: ToolUse
    invocation_state: dict[str, Any]
    result: ToolResult                   # writable
    exception: Exception | None = None
    cancel_message: str | None = None
    retry: bool = False                  # writable — True re-runs the tool
    # callbacks fire in REVERSE registration order

@dataclass
class BeforeNodeCallEvent(BaseHookEvent, _Interruptible):
    source: MultiAgentBase
    node_id: str
    invocation_state: dict[str, Any] | None = None
    cancel_node: bool | str = False       # writable
```

ZooVision audit provider:

```python
from strands.hooks import HookProvider, HookRegistry, AfterToolCallEvent, AfterNodeCallEvent

class ZooVisionAudit(HookProvider):
    def __init__(self, sink): self.sink = sink

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self.on_tool)
        registry.add_callback(AfterNodeCallEvent, self.on_node)

    def on_tool(self, event: AfterToolCallEvent) -> None:
        self.sink.write({
            "kind": "tool",
            "tool": event.tool_use["name"],
            "tool_use_id": event.tool_use["toolUseId"],
            "input": event.tool_use.get("input"),
            "status": event.result.get("status"),
            "content": event.result.get("content"),   # contains {"json": {"rule_fired": ...}}
            "error": repr(event.exception) if event.exception else None,
        })

    def on_node(self, event: AfterNodeCallEvent) -> None:
        self.sink.write({"kind": "node", "node_id": event.node_id})
```

Registration — three ways, all real:
```python
agent = Agent(hooks=[ZooVisionAudit(sink)])                    # constructor
agent.add_hook(my_callback, BeforeToolCallEvent)               # explicit
agent.add_hook(my_callback)                                    # event type INFERRED from type hint
builder.set_hook_providers([ZooVisionAudit(sink)])             # graph-level
graph.add_hook(cb, AfterNodeCallEvent, order=HookOrder.DEFAULT)
```

`Plugin` (`from strands.plugins import Plugin, hook`) bundles hooks with config and tools using an `@hook` method decorator:
```python
class LoggingPlugin(Plugin):
    name = "logging-plugin"
    @hook
    def log_after(self, event: AfterToolCallEvent) -> None: ...
agent = Agent(plugins=[LoggingPlugin()])
```

`interventions=[InterventionHandler(...)]` is a separate, newer axis: handlers evaluated in registration order at each lifecycle event, where Deny short-circuits and Guide feedback accumulates. Ships with Cedar authorization, human-in-the-loop, and steering variants. **This is the natural home for ZooVision's "night-shift human must ack within 20 minutes" gate** — see the human-in-the-loop interventions doc.

### Observability

```python
from strands.telemetry import StrandsTelemetry

StrandsTelemetry().setup_otlp_exporter().setup_console_exporter()
StrandsTelemetry().setup_meter(enable_console_exporter=True, enable_otlp_exporter=True)
# or reuse yours: StrandsTelemetry(tracer_provider=my_provider)

agent = Agent(trace_attributes={"session.id": "E07-2026-07-30",
                                "user.id": "nightshift@zoo.org",
                                "tags": ["zoovision", "enclosure-E07"]})
```
`opentelemetry-api>=1.30.0` is a hard dependency; the OTLP HTTP exporter is in the `otel` extra. Env vars are stock OTel: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER` / `OTEL_TRACES_SAMPLER_ARG`, plus `OTEL_SEMCONV_STABILITY_OPT_IN="gen_ai_latest_experimental,gen_ai_tool_definitions"`. For CloudWatch, enable **Transaction Search** in CloudWatch. `Graph` also accepts `trace_attributes` and each node gets its own span. Metrics: `strands.telemetry.EventLoopMetrics`, `metrics_to_string()`, `result.metrics.latest_context_size`, `result.projected_context_size`.

### Context window management

- Default: `SlidingWindowConversationManager(window_size=…)`.
- `SummarizingConversationManager(summary_ratio=…, compression_threshold=…)`.
- **`context_manager="auto"`** on `Agent` composes a `ContextOffloader` plugin (`max_result_tokens=1500`, `preview_tokens=750`) with `SummarizingConversationManager(summary_ratio=0.3, compression_threshold=0.85)`. ⚠️ Source warning: *"The offloader uses in-memory storage that does not persist across process restarts. For agents using `session_manager`, provide an explicit `ContextOffloader` with durable storage via the `plugins` parameter."* **Directly relevant to ZooVision** — dozens of 15-minute segments will blow the window, and the naive `"auto"` setting will lose offloaded content if the process restarts mid-night.

---

## 8. MCP client support (Neo4j read-only access)

```python
from strands.tools.mcp import MCPClient, MCPServerConfig, ToolFilters, MCPTransport, MCPAgentTool
```

Real `__init__` (`tools/mcp/mcp_client.py:223`):

```python
def __init__(
    self,
    transport_callable: Callable[[], MCPTransport],
    *,
    startup_timeout: int = 30,
    tool_filters: ToolFilters | None = None,
    prefix: str | None = None,
    application_name: str | None = None,
    application_version: str | None = None,
    continue_on_error: bool = False,
    elicitation_callback: ElicitationFnT | None = None,
    progress_callback: ProgressFnT | None = None,
    tasks_config: TasksConfig | None = None,
) -> None: ...
```

`MCPClient` is a `ToolProvider`, so you can pass it straight into `tools=[]` and lifecycle is managed for you:

```python
from mcp import stdio_client, StdioServerParameters
from strands import Agent
from strands.tools.mcp import MCPClient

mcp_client = MCPClient(lambda: stdio_client(StdioServerParameters(command="uvx", args=["…"])))
agent = Agent(tools=[mcp_client])          # lifecycle managed automatically
```
Or manage it manually — but then **every agent call must be inside the `with` block**:
```python
with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(tools=tools)
    agent("…")            # must be within context
```
Also: `mcp_client.start()` / `.stop()`, `await mcp_client.load_tools()`, `call_tool_sync()` / `await call_tool_async()`, `list_prompts_sync`, `list_resources_sync`, `read_resource`, `list_resource_templates`. Transports: `stdio_client`, `streamablehttp_client("http://…/mcp")`, SSE.

### Read-only Neo4j — `tool_filters` is exactly the mechanism

```python
class ToolFilters(TypedDict, total=False):
    allowed: list[_ToolMatcher]      # applied FIRST
    rejected: list[_ToolMatcher]     # then excluded
```
Matchers are **exact strings or compiled regexes**.

```python
import re
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

neo4j_ro = MCPClient(
    lambda: streamablehttp_client(NEO4J_MCP_URL),
    prefix="neo4j",                                    # -> neo4j_get_schema, neo4j_read_cypher
    tool_filters={
        "allowed": [re.compile(r"^(read|get|list|match|schema).*")],
        "rejected": [re.compile(r"(write|create|merge|delete|set|drop|remove)")],
    },
    startup_timeout=30,
    continue_on_error=True,      # a dead Neo4j doesn't kill the whole night
)
graphrag_agent = Agent(name="report_agent", tools=[neo4j_ro])
```

⚠️ `tool_filters` is **defence in depth, not a security boundary** — it filters which tools are *loaded into the agent*. The MCP server must also be configured read-only (or use a read-only Neo4j role). ZooVision's `index_tool` should do its idempotent `MERGE` writes through the **Neo4j Python driver directly**, not through MCP, so the write path is never LLM-reachable.

`prefix=` prevents name collisions if you also mount, say, a filesystem MCP server. `MCPServerConfig` (TypedDict: `command/args/env/cwd/url/headers/transport/disabled/continue_on_error/prefix/tool_filters/startup_timeout/…`) supports declarative multi-server config with `${VAR}` / `${env:VAR}` interpolation.

---

## 9. Deployment: local → Lambda → Bedrock AgentCore

Documented targets: AgentCore, Lambda, Fargate, App Runner, EC2, EKS, Kubernetes, Docker, Terraform, Nx-plugin-for-AWS. CDK examples live in `site/docs/examples/cdk/`.

### AgentCore — **the brief is correct** ✅

```bash
pip install bedrock-agentcore
```

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
def invoke(payload):
    user_message = payload.get("prompt", "Hello")
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
```

Streaming entrypoint — **exactly the pattern ZooVision wants** (`agent.stream_async` inside an async generator entrypoint):

```python
@app.entrypoint
async def agent_invocation(payload):
    stream = agent.stream_async(payload.get("prompt", ""))
    async for event in stream:
        yield (event)
```

CLI (recommended path in the docs — note it's an **npm** package):
```bash
npm install -g @aws/agentcore
agentcore create && agentcore dev && agentcore deploy && agentcore invoke
```
Local test: `curl -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' -d '{"prompt":"…"}'`.
Programmatic: `boto3.client('bedrock-agentcore-control').create_agent_runtime(...)` and `boto3.client('bedrock-agentcore').invoke_agent_runtime(...)`.

**The 8-hour claim: ✅ true, but it is an AgentCore property, not a Strands one.** The Strands docs never mention it. From AWS's `runtime-sessions.html`: *"AgentCore supports isolated sessions backed by ephemeral computes lasting up to 8 hours per lifecycle."* Sessions stop on **inactivity (default 15 min)**, **max compute lifetime (default 8 h)**, explicit `StopRuntimeSession`, or failed health checks. A stopped session **transitions back to Active on the next invocation with a fresh compute and another up-to-8-hour lifetime**, and the session ID stays valid until the runtime ARN is deleted.

⚠️ **ZooVision implications:**
- A 12-hour night **exceeds one compute lifetime.** You get a new microVM mid-night. All in-memory state is lost. **The overnight investigation therefore MUST be backed by `S3SessionManager` (or Neo4j via `RepositorySessionManager`), not agent memory.**
- The **15-minute idle timeout is shorter than ZooVision's 20-minute escalation timer.** A session idling while waiting for a keeper to acknowledge will be reaped. Either report `"HealthyBusy"` in pings (AgentCore's documented mechanism for background work), raise `idleRuntimeSessionTimeout` via lifecycle config, or — much simpler — **keep the escalation timer outside the agent** (EventBridge Scheduler one-time schedule + DynamoDB ack flag).
- `runtimeSessionId` must be **≥33 characters**. Header: `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` (HTTP/A2A) or `Mcp-Session-Id` (MCP). Payloads up to 100 MB.
- Configure **session storage** (`runtime-filesystem-configurations`) if you want ffmpeg segment files to survive stop/resume.

### Scheduling the 06:00 briefing — **Strands has no scheduler**

Confirmed: nothing in `strands-agents` 1.50.2 schedules anything. Two real options:

1. **Production: EventBridge Scheduler → target.** AWS now labels EventBridge *scheduled rules* legacy and recommends **EventBridge Scheduler** (cron/rate/one-time expressions, timezone support, flexible time windows, retry limits, DLQ). Target a Lambda that invokes your AgentCore runtime, or invoke `bedrock-agentcore:InvokeAgentRuntime` directly. `cron(0 6 * * ? *)` with a timezone gets you 06:00 local, DST included.
2. **Local demo: `strands_tools.cron`.** A real tool in 0.8.5 that manages the *system crontab* via `subprocess` (`crontab -l` / `crontab -`), with a built-in consent prompt bypassed by `BYPASS_TOOL_CONSENT=true`. Fine for a laptop demo; do not ship it.

`strands_tools.sleep` and a `stop` tool also exist (v1.50.0 added them; the stop tool moved to experimental in v1.50.1).

---

## 10. The ZooVision orchestrator, sketched

Verified APIs only, `strands-agents==1.50.2`. Day/night is a conditional edge on `invocation_state`; severity is assigned by a `FunctionNode` that no LLM can influence.

```python
"""ZooVision overnight orchestrator. strands-agents==1.50.2 / strands-agents-tools==0.8.5."""
from __future__ import annotations

import json, os, re, time
from datetime import datetime, time as dtime
from typing import Any, Callable

from pydantic import BaseModel, Field

from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.hooks import AfterNodeCallEvent, AfterToolCallEvent, HookProvider, HookRegistry
from strands.models.openai_responses import OpenAIResponsesModel
from strands.multiagent import GraphBuilder, MultiAgentBase, MultiAgentResult, Status
from strands.multiagent.base import NodeResult
from strands.multiagent.graph import GraphState
from strands.session import S3SessionManager
from strands.telemetry import StrandsTelemetry
from strands.telemetry.metrics import EventLoopMetrics
from strands.tools.mcp import MCPClient
from strands.types.event_loop import Metrics, Usage

from mcp.client.streamable_http import streamablehttp_client

from zoovision import ingest, triage, neo4j_index, briefing   # your deterministic modules

NIGHT_START, NIGHT_END = dtime(19, 0), dtime(6, 0)


# ── 1. Contracts ───────────────────────────────────────────────────────────────
class Observation(BaseModel):
    t_start_s: float = Field(description="Seconds from segment start")
    t_end_s: float
    animal_id: str | None = None
    behavior: str = Field(description="Controlled-vocabulary behavior label")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str

class AnalysisResult(BaseModel):
    enclosure_id: str
    segment_uri: str
    events: list[Observation]

class AlertCopy(BaseModel):
    headline: str = Field(max_length=90)
    body: str
    clip_uri: str
    tier: str = Field(description="ECHOED from triage. Never chosen by the model.")


# ── 2. Deterministic node wrapper (plain functions can NOT be Graph nodes) ─────
class FunctionNode(MultiAgentBase):
    def __init__(self, func: Callable[[str, dict[str, Any]], dict], node_id: str):
        super().__init__()
        self.id, self.func = node_id, func

    async def invoke_async(self, task, invocation_state=None, **kwargs) -> MultiAgentResult:
        started = time.time()
        payload = self.func(task if isinstance(task, str) else str(task), invocation_state or {})
        ms = int((time.time() - started) * 1000)
        res = AgentResult(stop_reason="end_turn", metrics=EventLoopMetrics(), state={},
                          message={"role": "assistant", "content": [{"text": json.dumps(payload)}]})
        return MultiAgentResult(
            status=Status.COMPLETED, execution_count=1, execution_time=ms,
            results={self.id: NodeResult(result=res, status=Status.COMPLETED, execution_time=ms,
                                         accumulated_usage=Usage(inputTokens=0, outputTokens=0, totalTokens=0),
                                         accumulated_metrics=Metrics(latencyMs=ms), execution_count=1)},
        )


# ── 3. Deterministic bodies. These mutate invocation_state so edges can read them.
def do_ingest(task: str, st: dict[str, Any]) -> dict:
    ev = ingest.pegasus_and_marengo(st["segment_uri"], st["enclosure_id"])   # no LLM
    st["evidence"] = ev
    return ev

def do_triage(task: str, st: dict[str, Any]) -> dict:
    """THE ONLY place severity is assigned. Pure Python. No model in the call stack."""
    tier, rule = triage.classify(st["analysis"]["events"], baseline=st.get("baseline", {}))
    st["tier"], st["rule_fired"] = tier, rule
    return {"tier": tier, "rule_fired": rule}

def do_index(task: str, st: dict[str, Any]) -> dict:
    return neo4j_index.merge_idempotent(st["enclosure_id"], st["analysis"], st.get("tier"))

def do_baseline(task: str, st: dict[str, Any]) -> dict:
    return neo4j_index.update_baseline(st["enclosure_id"], st["analysis"])

def do_report(task: str, st: dict[str, Any]) -> dict:
    return briefing.render(st["enclosure_id"], st["shift_date"])


# ── 4. Edge conditions. Param MUST be named `invocation_state` (dispatch is by name).
def is_night(state: GraphState, *, invocation_state: dict, **kwargs) -> bool:
    return bool(invocation_state.get("is_night"))

def is_day(state: GraphState, *, invocation_state: dict, **kwargs) -> bool:
    return not invocation_state.get("is_night")

def tier_is_actionable(state: GraphState, *, invocation_state: dict, **kwargs) -> bool:
    return invocation_state.get("tier") in {"amber", "red"}

def both_ready(required: list[str]):
    """Python Graph defaults to OR semantics on fan-in. This restores AND."""
    def check(state: GraphState) -> bool:
        return all(n in state.results and state.results[n].status == Status.COMPLETED
                   for n in required)
    return check


# ── 5. Audit hook: every alert trace carries rule_fired.
class ZooVisionAudit(HookProvider):
    def __init__(self, sink): self.sink = sink
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._tool)
        registry.add_callback(AfterNodeCallEvent, self._node)
    def _tool(self, e: AfterToolCallEvent) -> None:
        self.sink.write({"kind": "tool", "tool": e.tool_use["name"],
                         "tool_use_id": e.tool_use["toolUseId"],
                         "status": e.result.get("status"), "content": e.result.get("content")})
    def _node(self, e: AfterNodeCallEvent) -> None:
        self.sink.write({"kind": "node", "node_id": e.node_id,
                         "tier": (e.invocation_state or {}).get("tier"),
                         "rule_fired": (e.invocation_state or {}).get("rule_fired")})


# ── 6. Build the graph.
def build_graph(sink, session_id: str):
    StrandsTelemetry().setup_otlp_exporter()

    terra = OpenAIResponsesModel(                      # or: bedrock_mantle_config={"region": "us-east-1"}
        model_id="gpt-5.6-terra",
        client_args={"api_key": os.environ["OPENAI_API_KEY"]},
        params={"max_output_tokens": 4096, "temperature": 0.2},
    )

    analyze_agent = Agent(                             # name must match ^[a-zA-Z0-9_\-]+$
        name="analyze_agent", model=terra,
        description="Structures Pegasus + Marengo evidence into timestamped events.",
        system_prompt=("Merge the evidence into events[]. Report only what the evidence supports. "
                       "You do NOT assign severity."),
        structured_output_model=AnalysisResult,        # NOT the deprecated agent.structured_output()
    )
    alert_agent = Agent(
        name="alert_agent", model=terra,
        description="Phrases a night-shift alert. The tier is already decided.",
        system_prompt=("Write the alert. The tier is given; echo it verbatim. "
                       "Never upgrade, downgrade, or reinterpret it."),
        structured_output_model=AlertCopy,
    )
    neo4j_ro = MCPClient(
        lambda: streamablehttp_client(os.environ["NEO4J_MCP_URL"]),
        prefix="neo4j", continue_on_error=True,
        tool_filters={"allowed": [re.compile(r"^(read|get|list|match|schema).*")],
                      "rejected": [re.compile(r"(write|create|merge|delete|set|drop)")]},
    )
    report_agent = Agent(name="report_agent", model=terra, tools=[neo4j_ro],
                         description="GraphRAG morning briefing.")

    b = GraphBuilder()
    b.add_node(FunctionNode(do_ingest,   "ingest"),   "ingest")
    b.add_node(analyze_agent,                          "analyze")
    b.add_node(FunctionNode(do_triage,   "triage"),   "triage")
    b.add_node(FunctionNode(do_index,    "index"),    "index")
    b.add_node(alert_agent,                            "alert")
    b.add_node(FunctionNode(do_baseline, "baseline"), "baseline")
    b.add_node(FunctionNode(do_report,   "report"),   "report")

    b.add_edge("ingest", "analyze")
    b.add_edge("analyze", "triage",   condition=is_night)     # ← the day/night branch
    b.add_edge("analyze", "baseline", condition=is_day)
    b.add_edge("triage", "index")
    b.add_edge("triage", "alert", condition=tier_is_actionable)
    b.add_edge("index",  "report", condition=both_ready(["index", "alert"]))   # AND, not OR
    b.add_edge("alert",  "report", condition=both_ready(["index", "alert"]))

    b.set_entry_point("ingest")
    b.set_execution_timeout(900).set_node_timeout(300).set_max_node_executions(24)
    b.set_session_manager(S3SessionManager(session_id=session_id,
                                           bucket=os.environ["ZOOVISION_BUCKET"],
                                           prefix="nights/"))
    b.set_hook_providers([ZooVisionAudit(sink)])
    return b.build()


# ── 7. Run one 15-minute segment.
async def run_segment(graph, *, enclosure_id: str, segment_uri: str, now: datetime) -> dict:
    is_night_now = now.time() >= NIGHT_START or now.time() < NIGHT_END   # decided HERE, not by an LLM
    inv: dict[str, Any] = {"enclosure_id": enclosure_id, "segment_uri": segment_uri,
                           "shift_date": now.date().isoformat(), "is_night": is_night_now}

    result = await graph.invoke_async(f"Assess enclosure {enclosure_id} segment {segment_uri}",
                                      invocation_state=inv)

    analysis = result.results["analyze"].result.structured_output    # AnalysisResult | None
    return {"status": result.status.value,
            "path": [n.node_id for n in result.execution_order],
            "tier": inv.get("tier"), "rule_fired": inv.get("rule_fired"),
            "events": analysis.events if analysis else [],
            "tokens": result.accumulated_usage, "ms": result.execution_time}
```

⚠️ **Two things to wire up before this runs:** (a) `do_triage` reads `st["analysis"]`, which `analyze` (an `Agent` node) does not write — either add an `AfterNodeCallEvent` hook that copies `analyze`'s `structured_output` into `invocation_state`, or read it out of `state.results["analyze"].result.structured_output` inside `do_triage` (you'd need to pass the graph state in, so the hook is cleaner). (b) `report` is inside the same graph but should really be a separate 06:00 EventBridge Scheduler invocation — keep the node for the demo, split it for production.

---

## 11. Gotchas, version drift & deprecations

1. **`openai>=2.0.0` is a hard requirement of `OpenAIResponsesModel`, but the extra only pins `>=1.68.0`.** `openai_responses.py` runs a version check *at import time* and raises `ImportError: OpenAIResponsesModel requires openai>=2.0.0 (found …). … For older SDKs, use OpenAIModel (Chat Completions).` `pip install 'strands-agents[openai]'` can legally resolve `openai==1.99` and then blow up at import. **Pin `openai>=2.0.0` explicitly.**
2. **Python `Graph` fan-in is OR, not AND.** Guard every fan-in with an explicit AND condition (§5).
3. **Edge-condition dispatch is by parameter *name*.** `inspect.signature(condition)` looks for a parameter literally named `invocation_state`. Call it `inv_state` and you silently fall back to the legacy `(state)` signature — and get a `TypeError` at traversal time.
4. **`agent.structured_output()` / `structured_output_async()` are deprecated.** Use `structured_output_model=`.
5. **Agent nodes in a Graph must not have their own `session_manager`** → `ValueError`. Persistence goes on the graph.
6. **`add_node` rejects duplicate object instances.** Deep-copy or construct separate `Agent`s.
7. **Default `Agent.name` is `"Strands Agents"`** — contains a space, fails the tool-name regex. Always set `name=`.
8. **`as_tool(preserve_context=False)` + `session_manager` → `ValueError`.**
9. **Agents-as-tools exposes exactly one `input: str` parameter.** Multi-arg sub-agents need a `@tool` wrapper.
10. **`Agent(model="…")` with a bare string means Bedrock.** Pass model objects.
11. **Mantle base path differs by model family:** `openai.gpt-5.*` → `/openai/v1`; others → `/v1`. Prefer `bedrock_mantle_config=` and let the SDK decide.
12. **Bedrock Mantle stores responses for 30 days by default** (`store=true`). Set `store=false` for footage-derived content if retention matters.
13. **`stateful=True` on `OpenAIResponsesModel` empties `agent.messages`** — history lives on the server. Your audit log must not depend on `agent.messages` in that mode.
14. **`context_manager="auto"` offloads to in-memory storage that does not survive a restart.** With `session_manager`, supply an explicit `ContextOffloader` with durable storage via `plugins=`.
15. **The published hooks page lists Python-unavailable event names.** Only the 12 exported from `strands.hooks` are importable.
16. **Docs bug:** `session-management` shows `Graph(agents={…})`; no such parameter exists. Use `GraphBuilder`.
17. **Docs/source disagreement on `set_node_timeout` units** (docs page says ms; source docstring says seconds). Source wins.
18. **Repo/URL drift:** `sdk-python` → `harness-sdk`; `strandsagents.com/latest/**` 404s; `docs`, `sdk-typescript`, `agent-builder`, `mcp-server` repos archived. Any bookmark or LLM-memorised URL from before ~mid-2026 is suspect.
19. **`AfterToolCallEvent` callbacks fire in reverse registration order** and can set `retry=True`. If you register two audit providers, the last one registered logs first.
20. **Versioning policy explicitly allows "pay-for-play" breaking changes in minor releases**, and `strands.experimental` is outside semver entirely. `strands.experimental.checkpoint` (used by `checkpointing=True`) is one such module. **Pin exact versions.**
21. **`Graph`/`Swarm` `**kwargs` is deprecating** — `MultiAgentBase.__call__` warns *"`**kwargs` parameter is deprecating, use `invocation_state` instead."*
22. **v1.50.1 moved the `stop` tool to experimental**; v1.50.x deprecated legacy file storage in favour of unified storage. Both are recent churn in areas ZooVision may touch.

---

## 12. Corrections to the ZooVision brief

| # | Brief claim | Verdict | Reality | Source |
|---|---|---|---|---|
| 1 | Agents-as-tools: pass a sub-agent object directly in `tools=[]` and the SDK converts it | ✅ **confirmed** | Documented as "the simplest way". Auto-wrapped via `agent.as_tool()` with defaults. `@tool` wrapping is one of three documented options, not a requirement. **But**: the generated tool has a single `input: str` param; tool name defaults to `agent.name` which defaults to `"Strands Agents"` (invalid); `preserve_context=False` + `session_manager` raises. | `docs/…/multi-agent/agents-as-tools/`; `agent/agent.py:958`; `agent/_agent_as_tool.py` |
| 2a | `Graph` via `GraphBuilder`, deterministic directed orchestration | ✅ **confirmed** | Exactly as described. `GraphBuilder` exported from `strands.multiagent`. | `multiagent/graph.py:301` |
| 2b | `Graph` supports **conditional edges** | ✅ **confirmed** | `add_edge(..., condition=fn)`; two signatures — legacy `(state)` and `EdgeConditionWithContext(state, *, invocation_state, **kwargs)`. Dispatch by param name. Day/night branch is viable. | `multiagent/graph.py:66-102`, `:339` |
| 2c | `Swarm` = autonomous handoffs | ✅ confirmed | `from strands.multiagent import Swarm`; `entry_point`, `max_handoffs=20`, `max_iterations=20`, `execution_timeout=900`, `node_timeout=300`; `handoff_to_agent()` tool. | `docs/…/multi-agent/swarm/` |
| 2d | `Workflow` = task pipeline shipped in `strands-agents-tools` | ✅ confirmed | It is the `workflow` **tool**, not an SDK class. `agent.tool.workflow(action=…)`. Not appropriate for ZooVision. | `docs/…/multi-agent/workflow/`; `strands_tools/workflow.py` |
| 2e | (implied) a plain Python function can be a Graph node | ❌ **wrong** | `add_node(executor: AgentBase \| MultiAgentBase)`. Plain functions and `@tool` functions are rejected. You must subclass `MultiAgentBase` (see the `FunctionNode` in §5/§10). **This materially changes the build.** | `multiagent/graph.py:326`; `graph.mdx` "Custom Node Types" |
| 2f | (unstated) fan-in waits for all dependencies | ❌ **wrong** | Python `Graph` uses **OR** semantics — a node fires when *any* incoming edge completes. Needs an explicit AND condition. | `graph.mdx` "Waiting for All Dependencies" |
| 3a | Module `strands.models.openai_responses`, class `OpenAIResponsesModel` | ✅ **confirmed** | Exact. | `models/openai_responses.py:158`; `docs/api/python/strands.models.openai_responses/` |
| 3b | Constructor kwargs `model_id`, `client_args`, `params` | ✅ **confirmed** | All three real. Plus `stateful`, `use_native_token_count`, `context_window_limit`, and `bedrock_mantle_config`. `client_args` is positional-or-keyword; the config keys go through `**model_config`. | `models/openai_responses.py:136-200` |
| 3c | Separate `OpenAIModel` (Chat Completions) provider exists | ✅ confirmed | `strands.models.openai.OpenAIModel`. Responses is a superset: built-in tools, server-side state, multi-modal. Responses needs `openai>=2.0.0`; Chat Completions works from 1.68.0. | `models/openai.py`; `models/openai_responses.py:37-53` |
| 3d | Points at `gpt-5.6-terra` on the Responses API | ✅ confirmed | Real model, GPT-5.6 mid-tier (Luna/Terra/Sol), released 2026-07-09. On Bedrock as `openai.gpt-5.6-terra`. | OpenAI API docs; AWS Bedrock model card |
| 4 | `OpenAIResponsesModel` can also target Bedrock's OpenAI-compatible **"Mantle"** endpoint with a Bedrock API key | ✅ **confirmed — Mantle is a real AWS name** | `https://bedrock-mantle.{region}.api.aws{path}`, 14 regions, Bedrock API key as bearer. **Better than the brief says**: the SDK has a first-class `bedrock_mantle_config={"region": …}` kwarg that mints fresh AWS bearer tokens per request (needed for overnight runs). ⚠️ This kwarg is **undocumented** on the website. ⚠️ Path is `/openai/v1` for `openai.gpt-5.*`, `/v1` otherwise. | `models/_openai_bedrock.py`; AWS `bedrock-mantle.html`; `docs/…/model-providers/openai-responses/` |
| 5a | `BedrockAgentCoreApp`, `@app.entrypoint`, `agent.stream_async` | ✅ **confirmed** | `pip install bedrock-agentcore`; `from bedrock_agentcore.runtime import BedrockAgentCoreApp`; `app.run()`; async-generator entrypoint yielding `stream_async` events. CLI is `npm i -g @aws/agentcore`. | `docs/…/deploy_to_bedrock_agentcore/python/` |
| 5b | Long-running tasks **up to 8 hours** | ⚠️ **true but mis-attributed, and a trap for ZooVision** | 8 h is the AgentCore **max compute lifetime**; the Strands docs never state it. Also: **15-minute default idle timeout** (shorter than ZooVision's 20-min escalation timer) and a fresh microVM after a stop — so a 12-hour night crosses at least one compute boundary. Requires durable sessions. | AWS `runtime-sessions.html` |
| 6a | Docs exist for agents-as-tools, multi-agent-patterns, graph, swarm, model-providers/openai-responses | ✅ **all 5 exist** under `strandsagents.com/docs/user-guide/concepts/...` | Fetched, all HTTP 200. | §14 |
| 6b | Python API ref `strands.models.openai_responses` | ✅ **exists** | `strandsagents.com/docs/api/python/strands.models.openai_responses/` — HTTP 200, correct signature. | §14 |
| 6c | (implied) `strandsagents.com/latest/…` scheme | ❌ **404** | Old mkdocs scheme is gone. `strandsagents.com/latest/` returns 404. Use `/docs/…`. Also `/docs/user-guide/concepts/agents/state-sessions/` **404s** — it split into `.../state/` and `.../session-management/`. | fetched |
| 7 | Structured output via `agent.structured_output()` with Pydantic enforces `analyze_tool`'s `events[]` | ❌ **deprecated API** | Emits `DeprecationWarning` in 1.50.2. Use `structured_output_model=` on the constructor or per-call; read `result.structured_output`. Bonus: a sub-agent with `structured_output_model` returns `{"json": …}` through the agent-as-tool adapter. | `agent/agent.py:856,887`; `docs/…/agents/structured-output/` |
| 8 | (missing from brief) TwelveLabs integration must be hand-rolled | ⚠️ **partly unnecessary** | `strands-agents-tools[twelvelabs]` 0.8.5 ships `chat_video` (Pegasus) and `search_video` (Marengo), with `TWELVELABS_API_KEY` / `TWELVELABS_PEGASUS_INDEX_ID`. They return free text, so ZooVision's schema-constrained contract still needs a custom `@tool` — but these are a working reference and a fast demo path. | `strands_tools/chat_video.py`, `search_video.py` @ v0.8.5 |
| 9 | (missing from brief) how to schedule 06:00 | ✅ resolved | Strands has **no scheduler**. Use **EventBridge Scheduler** (AWS now calls scheduled *rules* legacy) → Lambda / `InvokeAgentRuntime`. `strands_tools.cron` manages the system crontab for local demos only. | AWS EventBridge docs; `strands_tools/cron.py` |

---

## 13. Open questions to resolve before demo day

1. **How does `analyze`'s `structured_output` reach `triage`?** Options: an `AfterNodeCallEvent` hook that copies `result.structured_output` into `invocation_state`, or digging it out of `state.results["analyze"]`. Pick one and make it the only path. ⚠️ Unresolved in §10.
2. **Does mutating `invocation_state` survive interrupt/resume?** Docs say `invocation_state` is "persisted across interrupt/resume cycles (serialized with the graph checkpoint)"; a source comment (`graph.py:1418-1422`) says resume uses the caller-supplied `invocation_state`. **Test it.** Until then, derive day/night at the call site and pass it in — never mutate it for the branch decision.
3. **12-hour night vs 8-hour AgentCore compute lifetime.** Confirm the crossing is graceful with `S3SessionManager`, or split the night into two runtime sessions on purpose. Also decide how to handle the 15-min idle timeout vs the 20-min escalation timer (`HealthyBusy` pings vs external EventBridge one-time schedule — the latter is much less risky).
4. **Terra via OpenAI direct or via Bedrock Mantle?** Direct = `gpt-5.6-terra` + `client_args={"api_key": …}`. Mantle = `openai.gpt-5.6-terra` + `bedrock_mantle_config={"region": …}`, gets you IAM + rotating tokens + AWS-native quotas, and reads better to AWS judges. Mantle costs you the `/openai/v1` path subtlety and a separate quota pool. **Recommend Mantle for the primary path, direct OpenAI as the fallback** — the model object is the only thing that changes.
5. **Does `bedrock_mantle_config` actually work end-to-end with `openai.gpt-5.6-terra`?** It is present in v1.50.2 source and undocumented on the site, so it is comparatively untested in public. Smoke-test on day one; the documented `client_args` + `base_url` form is the fallback.
6. **One graph per segment, or one long-lived graph per night?** Per-segment (as sketched) is simpler, bounded, and restart-safe. Per-night gives cross-segment context in graph state but hits both `set_execution_timeout` and the AgentCore compute lifetime. Recommend per-segment with continuity in Neo4j + `S3SessionManager`.
7. **Context growth.** Decide between `context_manager="auto"` (convenient, but in-memory offload that does not survive restart) and an explicit `ContextOffloader` with durable storage via `plugins=`. With `session_manager` in play the source explicitly recommends the latter.
8. **`interventions` for the 20-minute acknowledgement gate** — is the human-in-the-loop `InterventionHandler` the right tool, or is an external timer simpler and more demo-proof? Lean external.
9. **Is `str(AgentResult)` used anywhere in the alert path?** With `structured_output` set, `__str__` returns JSON, not prose. Easy to accidentally paste JSON into an SMS.
10. **Neo4j MCP read-only enforcement.** `tool_filters` filters *loading*, not *authorisation*. Confirm the MCP server or the Neo4j role is genuinely read-only, and route `index_tool` writes through the Python driver, never MCP.
11. **Pin everything.** `strands-agents==1.50.2`, `strands-agents-tools==0.8.5`, `openai>=2.0.0`, `bedrock-agentcore` (pin once chosen). The SDK ships ~weekly and permits minor-version breaking changes.

---

## 14. Sources

All URLs below were fetched on 2026-07-30 unless marked. Source-level facts were read from a sparse clone of `strands-agents/harness-sdk` at tag **`python/v1.50.2`** — file paths are given relative to the repo root, which is the most authoritative form available.

### Package registries (versions pinned from here)
- `https://pypi.org/pypi/strands-agents/json` — **1.50.2**, uploaded 2026-07-27T20:38:46Z; `requires-python >=3.10`; deps `boto3`, `botocore`, `pydantic>=2.4`, `httpx>=0.28.1`, `mcp>=1.23`, `opentelemetry-api>=1.30`, `docstring-parser`, `watchdog`, `pyyaml`. `1.0.0` uploaded **2025-07-15**. Confirms the `openai` extra pins `openai<3.0.0,>=1.68.0` + `aws-bedrock-token-generator>=1.1.0`.
- `https://pypi.org/pypi/strands-agents-tools/json` — **0.8.5**, uploaded 2026-07-21T20:06:14Z; extras include `twelvelabs`, `a2a-client`, `mem0-memory`, `diagram`, `use-computer`.

### GitHub (via `gh api` + sparse clone at `python/v1.50.2`)
- `https://github.com/strands-agents` (org repo listing) — confirms the rename to **`harness-sdk`** and that `docs`, `sdk-typescript`, `agent-builder`, `mcp-server` are **archived**.
- `strands-py/src/strands/__init__.py` — top-level exports.
- `strands-py/src/strands/agent/agent.py` — `Agent.__init__` (`:161`), `__call__` (`:704`), `invoke_async` (`:786`), **deprecated** `structured_output` (`:856`) / `structured_output_async` (`:887`), `as_tool` (`:958`), `add_hook` (`:1004`), `stream_async` (`:1071`), `_DEFAULT_AGENT_NAME = "Strands Agents"` (`:123`).
- `strands-py/src/strands/agent/agent_result.py` — `AgentResult` fields incl. `structured_output`, and `__str__` priority order.
- `strands-py/src/strands/agent/_agent_as_tool.py` — single `input: str` tool spec; `preserve_context` + session-manager `ValueError`; `{"json": …}` emission for structured sub-agents; interrupt propagation.
- `strands-py/src/strands/multiagent/__init__.py` — exact export list (**no `Graph`, no `GraphState`**).
- `strands-py/src/strands/multiagent/base.py` — `MultiAgentBase`, `MultiAgentResult`, `NodeResult`, `Status`; `**kwargs` deprecation warning.
- `strands-py/src/strands/multiagent/graph.py` — `EdgeConditionWithContext` (`:66`), `_is_context_condition` name-based dispatch (`:89`), `GraphState` (`:108`), `GraphResult` (`:174`), `_validate_node_executor` session/duplicate errors (`:279-298`), `GraphBuilder` (`:301`), `add_node` (`:326`), `add_edge` (`:336`), `build` (`:449`), shared `_current_invocation_state` (`:641`), node dispatch (`:1014-1042`), `should_traverse` call sites (`:965`, `:1204`), resume-state comment (`:1418-1422`).
- `strands-py/src/strands/models/openai_responses.py` — module docstring w/ built-in-tool support matrix; **`openai>=2.0.0` import-time check** (`:37-53`); `OpenAIResponsesConfig` + `__init__` (`:136-200`); `_resolve_client_args`.
- `strands-py/src/strands/models/_openai_bedrock.py` — **`BedrockMantleConfig`**, `_MANTLE_BASE_URL_TEMPLATE`, `_OPENAI_PATH_MODEL_PREFIXES = ("openai.gpt-5.",)`, `resolve_bedrock_client_args`, per-request token minting.
- `strands-py/src/strands/models/__init__.py`, `model.py` — lazy provider loading; `BaseModelConfig`, `CacheConfig`, abstract `structured_output`.
- `strands-py/src/strands/hooks/__init__.py`, `hooks/events.py` — the **12** exported event classes and their exact writable fields.
- `strands-py/src/strands/session/__init__.py` — `FileSessionManager`, `S3SessionManager`, `RepositorySessionManager`, `SessionManager`, `SessionRepository`.
- `strands-py/src/strands/tools/decorator.py` — `tool()` overloads + signature (`:724-742`).
- `strands-py/src/strands/tools/tools.py` — `validate_tool_use_name`, `tool_name_pattern = r"^[a-zA-Z0-9_\-]{1,}$"`, 64-char cap (`:50-79`).
- `strands-py/src/strands/tools/mcp/__init__.py`, `mcp_client.py` — `MCPClient.__init__` (`:223`), `ToolFilters` (`:84`), `MCPServerConfig` (`:103`).
- `strands-py/src/strands/telemetry/__init__.py`, `config.py` — `StrandsTelemetry`, `setup_console_exporter`, `setup_otlp_exporter`, `setup_meter`, OTel env vars.
- `strands-py/src/strands/event_loop/_retry.py` — `ModelRetryStrategy(max_attempts=6, initial_delay=4, max_delay=240)`.
- `strands-py/src/strands/types/agent.py` — `Limits(turns, output_tokens, total_tokens)` and the `limit_*` stop reasons.
- `strands-py/src/strands/types/_events.py` — `multiagent_node_start` / `multiagent_node_stop` stream event payload shapes.
- `strands-py/pyproject.toml` — extras: `openai = ["openai>=1.68.0,<3.0.0", "aws-bedrock-token-generator>=1.1.0,<2.0.0"]`, `otel`, `all`.
- `site/src/content/docs/user-guide/**` (Astro content collection at the same tag) — the canonical page set; used to derive real doc URLs and to read `graph.mdx`, `agents-as-tools.mdx`, `state.mdx`, `session-management.mdx`, `hooks.mdx`, `mcp-tools.mdx`, `custom-tools.mdx`, `openai-responses.mdx`, `versioning-and-support.mdx`, `guardrails.mdx`, `traces.mdx`, `deploy_to_bedrock_agentcore/python.mdx` verbatim.
- `github.com/strands-agents/tools` @ tag **`v0.8.5`** — `src/strands_tools/` listing; `chat_video.py` (Pegasus, `TWELVELABS_API_KEY`, `TWELVELABS_PEGASUS_INDEX_ID`, SHA-256 upload cache); `search_video.py` (Marengo, `group_by`, `threshold`); `cron.py` (system crontab, `BYPASS_TOOL_CONSENT`); `workflow.py`; `pyproject.toml` (`twelvelabs = ["twelvelabs>=0.4.0,<1.0.0"]`).

### strandsagents.com — every URL the brief listed, verified
| URL | Status | Confirmed |
|---|---|---|
| `strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/` | ✅ 200 | Three patterns; direct passing is "the simplest way"; `.as_tool()`; `@tool` wrapper |
| `strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/` | ✅ 200 | Graph/Swarm/Workflow comparison table; `workflow` is a `strands-agents-tools` tool |
| `strandsagents.com/docs/user-guide/concepts/multi-agent/graph/` | ✅ 200 | `GraphBuilder` API, conditional edges + `invocation_state`, OR-semantics note, Custom Node Types, `graph` tool |
| `strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/` | ✅ 200 | `from strands.multiagent import Swarm`; handoff kwargs |
| `strandsagents.com/docs/user-guide/concepts/multi-agent/workflow/` | ✅ 200 | Workflow is the `strands_tools.workflow` tool |
| `strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/` | ✅ 200 | `OpenAIResponsesModel` import + kwargs; Mantle via manual `client_args`/`base_url`; built-in tools; `stateful` |
| `strandsagents.com/docs/api/python/strands.models.openai_responses/` | ✅ 200 | Exact `__init__` incl. `bedrock_mantle_config`; config keys |
| `strandsagents.com/docs/api/python/strands.multiagent.graph/` | ✅ 200 | `Graph`/`GraphBuilder`/`GraphState`/`GraphEdge`/`GraphNode`/`EdgeConditionWithContext` signatures |
| `strandsagents.com/docs/api/python/strands.multiagent.base/` | ✅ 200 | `MultiAgentBase`, `NodeResult`, `MultiAgentResult`, `Status` |
| `strandsagents.com/docs/user-guide/concepts/agents/structured-output/` | ✅ 200 | **`agent.structured_output()` is deprecated**; `structured_output_model=` on constructor + per-call + streaming |
| `strandsagents.com/docs/user-guide/concepts/agents/hooks/` | ✅ 200 | `agent.add_hook()`, type inference, `orchestrator.hooks.add_callback`, `Plugin` + `@hook` |
| `strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/` | ✅ 200 | Overview only; delegates to `python/` and `typescript/` |
| `strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/` | ✅ 200 | `BedrockAgentCoreApp`, `@app.entrypoint`, `app.run()`, streaming entrypoint, `@aws/agentcore` CLI, `create_agent_runtime`. **No 8-hour claim anywhere.** |
| `strandsagents.com/changelog/` | ✅ 200 | v1.50.2 (2026-07-27), v1.50.1/1.50.0 (2026-07-24); "routes gpt-5 mantle traffic through `/openai/v1` base path"; `stop` tool → experimental |
| `strandsagents.com/docs/user-guide/versioning-and-support/` | ✅ 200 | SemVer + "pay for play" minor-version breaking changes; `strands.experimental` outside semver; pin minor versions |
| `strandsagents.com/latest/` | ❌ **404** | Old mkdocs scheme removed |
| `strandsagents.com/docs/user-guide/concepts/agents/state-sessions/` | ❌ **404** | Split into `.../agents/state/` and `.../agents/session-management/` |
| `strandsagents.com/docs/user-guide/concepts/tools/python-tools/` | ⚠️ redirect | → `.../concepts/tools/custom-tools/` |
| `strandsagents.com/docs/` | ⚠️ redirect | → `/docs/user-guide/quickstart/overview/` |

### AWS
- `https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html` — **Mantle is real.** `OPENAI_BASE_URL="https://bedrock-mantle.<region>.api.aws/v1"`, Bedrock API key as `OPENAI_API_KEY`, 14 regions, separate quotas, `store`/`previous_response_id` semantics, 30-day retention default.
- `https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html` — **8-hour max compute lifetime**, 15-minute default idle timeout, session states, fresh microVM on resume, ≥33-char session IDs, session headers per protocol.
- `https://aws.amazon.com/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/` — **dated 2025-07-15** (the original 1.0, not a 2026 release). Four primitives: agents-as-tools, handoffs, swarms, graphs; A2A; `SessionManager`; `stream_async`.
- `https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html` (+ EventBridge Scheduler docs) — scheduled *rules* are legacy; **EventBridge Scheduler** is the recommended path for cron/one-time invocations with timezones, retries, and DLQ.
- Bedrock model cards / AWS ML blog — `openai.gpt-5.6-terra` GA on Bedrock; GPT-5.6 family (Luna/Terra/Sol) released 2026-07-09.

### Other
- `https://developers.openai.com/api/docs/models/gpt-5.6-terra` — Terra is real: mid-tier, $1.25/$7.50 per Mtok, positioned for "structured data extraction and general-purpose agentic tasks."
- Context7 (`mcp__plugin_context7_context7__resolve-library-id`) — confirms the primary library ID is now **`/strands-agents/harness-sdk`**; `/strands-agents/docs` and `/strands-agents/sdk-typescript` are stale mirrors of archived repos. Not used for any factual claim above.

### ⚠️ UNVERIFIED
- **`bedrock_mantle_config` end-to-end against `openai.gpt-5.6-terra`.** Present in v1.50.2 source with a clear contract, and the changelog references gpt-5 Mantle path routing — but it is absent from the published docs and I could not execute it. Searched: the docs content collection at `python/v1.50.2` (`grep -rn bedrock_mantle_config site/src/content/docs/` → **no hits**), plus the openai-responses page and API reference. Smoke-test before relying on it.
- **Whether mutations to `invocation_state` survive interrupt/resume.** Docs and a source comment appear to disagree (§13 item 2). Searched `graph.mdx` and `multiagent/graph.py`; did not run an interrupt/resume cycle.
- **Exact set of hook events importable from `strands.hooks` in versions other than 1.50.2.** Verified only against 1.50.2's `hooks/__init__.py`.
- **A ZooVision-shaped end-to-end sample in `strands-agents/samples`.** I did not exhaustively enumerate that repo; the §10 sketch is composed from verified primitives, not copied from a running sample. It has not been executed.
