"""Grounded question answering over recorded welfare evidence.

The assistant reads the shift record and explains what was recorded. It is not
part of the decision path: it cannot assign or revise severity, cannot diagnose,
cannot recommend treatment, and cannot act on an enclosure. Severity shown in an
answer is always quoted from a deterministic rule that already fired.

Two answer modes exist. When OpenAI is configured, a schema-constrained call
phrases the answer and must cite evidence ids drawn from the supplied context. A
deterministic summarizer answers when that is unavailable or fails, so the
console's chat always responds rather than presenting an error.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .store import SQLiteStore

CHAT_INSTRUCTIONS = """
You answer questions about an overnight animal-welfare shift record for keeper
staff.

Ground every statement in the supplied context JSON. Rules you must follow:
- Never assign, infer, revise, or imply a severity. Severity exists only where a
  deterministic rule already recorded it; quote it and name the rule.
- Never diagnose a condition, suggest a cause of illness, or recommend
  medication, treatment, or any enclosure action.
- If the context does not answer the question, say so plainly and name the
  missing evidence or the recorded data gap. Never invent an observation,
  timestamp, animal, or event.
- Motion regions locate movement in the frame. They do not identify a species or
  a behavior. Do not describe them as either.
- Cite the ids of the context records you used in cited_ids.
- Be brief and factual. Keeper staff read these during a night shift.
""".strip()


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    enclosure_id: str | None = None
    animal_id: str | None = None


class ChatAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1800)
    cited_ids: list[str]
    uncertainty: list[str]


class ChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    cited_ids: list[str]
    uncertainty: list[str]
    mode: str
    model: str | None = None
    context_record_count: int


def build_context(
    store: SQLiteStore,
    *,
    enclosure_id: str | None = None,
    animal_id: str | None = None,
    event_limit: int = 40,
) -> dict[str, Any]:
    """Collect the shift record the assistant is allowed to read."""
    dashboard = store.dashboard()
    animals = dashboard["animals"]
    events = dashboard["events"]
    gaps = dashboard["data_gaps"]

    if enclosure_id:
        animals = [a for a in animals if a["enclosure_id"] == enclosure_id]
        events = [e for e in events if e["enclosure_id"] == enclosure_id]
        gaps = [g for g in gaps if g["enclosure_id"] == enclosure_id]
    if animal_id:
        animals = [a for a in animals if a["animal_id"] == animal_id]
        events = [e for e in events if e["animal_id"] == animal_id]

    observations = {row["observation_id"]: row for row in store.dump_table("observations")}
    trimmed_events = []
    for event in events[:event_limit]:
        detail_sources = [
            {
                "observation_id": source_id,
                "evidence": observations[source_id]["evidence"],
                "provider": observations[source_id]["provider"],
                "evidence_kind": observations[source_id]["evidence_kind"],
            }
            for source_id in event.get("source_observation_ids", [])
            if source_id in observations
        ]
        trimmed_events.append(
            {
                "event_id": event["event_id"],
                "animal_id": event["animal_id"],
                "animal_name": event["animal_name"],
                "enclosure_id": event["enclosure_id"],
                "behavior": event["behavior"],
                "severity": event["severity"],
                "rule_fired": event["rule_fired"],
                "action": event["action"],
                "shift_mode": event["shift_mode"],
                "start_ts": event["start_ts"],
                "end_ts": event["end_ts"],
                "confidence": event["confidence"],
                "explanation_facts": event["explanation_facts"],
                "acknowledgement": event.get("ack_state"),
                "acknowledged_by": event.get("acknowledged_by"),
                "delivery_status": event.get("delivery_status"),
                "sources": detail_sources,
            }
        )

    return {
        "scope": {"enclosure_id": enclosure_id, "animal_id": animal_id},
        "animals": [
            {
                "animal_id": animal["animal_id"],
                "name": animal["name"],
                "species": animal["species"],
                "enclosure_id": animal["enclosure_id"],
                "baseline_state": animal["baseline_state"],
                "baseline_day_shifts": animal["baseline_days"],
                "event_count": animal["event_count"],
            }
            for animal in animals
        ],
        "events": trimmed_events,
        "data_gaps": [
            {
                "gap_id": gap["gap_id"],
                "enclosure_id": gap["enclosure_id"],
                "reason": gap["reason"],
                "detail": gap["detail"],
                "start_ts": gap["start_ts"],
                "end_ts": gap["end_ts"],
            }
            for gap in gaps
        ],
        "policy": {
            "severity_source": "deterministic Python rules only",
            "night_shift_only_paging": True,
            "assistant_may_not": [
                "assign severity",
                "diagnose",
                "recommend treatment",
                "act on an enclosure",
            ],
        },
    }


def context_record_count(context: dict[str, Any]) -> int:
    return (
        len(context.get("animals", []))
        + len(context.get("events", []))
        + len(context.get("data_gaps", []))
    )


class GroundedChat:
    """Answers questions about the shift record, with a deterministic fallback."""

    def __init__(
        self,
        store: SQLiteStore,
        *,
        client: Any | None = None,
        model: str | None = None,
        allow_fallback: bool = True,
    ):
        self.store = store
        self.client = client
        self.model = model
        self.allow_fallback = allow_fallback

    def reply(self, request: ChatRequest) -> ChatReply:
        context = build_context(
            self.store,
            enclosure_id=request.enclosure_id,
            animal_id=request.animal_id,
        )
        count = context_record_count(context)
        if self.client is not None and self.model:
            try:
                answer = self._ask_model(request, context)
                return ChatReply(
                    answer=answer.answer,
                    cited_ids=answer.cited_ids,
                    uncertainty=answer.uncertainty,
                    mode="openai",
                    model=self.model,
                    context_record_count=count,
                )
            except Exception as error:  # noqa: BLE001 - degrade to the grounded summary
                if not self.allow_fallback:
                    raise RuntimeError("live OpenAI chat is unavailable") from error
                fallback = summarize(context, request.messages[-1].content)
                fallback.uncertainty.append(
                    f"The language model was unavailable ({type(error).__name__}); "
                    "this answer was assembled directly from the shift record."
                )
                return ChatReply(
                    **fallback.model_dump(),
                    mode="deterministic_fallback",
                    model=None,
                    context_record_count=count,
                )
        if not self.allow_fallback:
            raise RuntimeError("live OpenAI chat is not configured")
        answer = summarize(context, request.messages[-1].content)
        return ChatReply(
            **answer.model_dump(),
            mode="deterministic",
            model=None,
            context_record_count=count,
        )

    def _ask_model(self, request: ChatRequest, context: dict[str, Any]) -> ChatAnswer:
        conversation = [
            {"role": message.role, "content": message.content} for message in request.messages
        ]
        response = self.client.responses.parse(
            model=self.model,
            instructions=CHAT_INSTRUCTIONS,
            input=json.dumps(
                {"context": context, "conversation": conversation},
                separators=(",", ":"),
                default=str,
            ),
            text_format=ChatAnswer,
            reasoning={"effort": "low"},
            max_output_tokens=900,
            store=False,
        )
        answer = response.output_parsed
        if answer is None:
            raise ValueError("OpenAI returned no parsed chat answer")
        allowed = _citable_ids(context)
        unknown = [cited for cited in answer.cited_ids if cited not in allowed]
        if unknown:
            raise ValueError(f"chat answer cited unknown records: {unknown[:3]}")
        return answer


def summarize(context: dict[str, Any], question: str) -> ChatAnswer:
    """Assemble a factual answer straight from the record, with no model.

    This keeps the console useful when the language model is unreachable, and it
    keeps the same boundaries: it quotes recorded severities and rules and never
    derives a new one.
    """
    events = context.get("events", [])
    animals = context.get("animals", [])
    gaps = context.get("data_gaps", [])
    asked = question.lower()

    focus = [
        event
        for event in events
        if event["animal_name"].lower() in asked or event["behavior"].replace("_", " ") in asked
    ]
    selected = focus or events

    if not animals:
        return ChatAnswer(
            answer="No animals are in scope for this view, so there is nothing to report.",
            cited_ids=[],
            uncertainty=["The current scope contains no monitored animals."],
        )

    lines: list[str] = []
    cited: list[str] = []
    if selected:
        lines.append(f"{len(selected)} recorded event(s) match this view:")
        for event in selected[:6]:
            lines.append(
                f"- {event['animal_name']} ({event['enclosure_id']}): "
                f"{event['behavior'].replace('_', ' ')}, severity {event['severity']} "
                f"from rule {event['rule_fired']}. "
                f"{' '.join(event['explanation_facts'])} "
                f"Review state: {event.get('acknowledgement') or 'unknown'}."
            )
            cited.append(event["event_id"])
    else:
        lines.append("No deterministic welfare events are recorded for this view.")

    quiet = [animal for animal in animals if animal["event_count"] == 0]
    if quiet:
        lines.append(
            "Animals with no recorded events: "
            + ", ".join(sorted(animal["name"] for animal in quiet))
            + "."
        )
        cited.extend(animal["animal_id"] for animal in quiet)

    uncertainty: list[str] = []
    if gaps:
        lines.append(f"{len(gaps)} coverage gap(s) limit what could be observed:")
        for gap in gaps[:3]:
            lines.append(
                f"- {gap['enclosure_id']}: {gap['reason'].replace('_', ' ')} "
                f"between {gap['start_ts']} and {gap['end_ts']}."
            )
            cited.append(gap["gap_id"])
        uncertainty.append("Recorded coverage gaps mean the record may be incomplete.")

    return ChatAnswer(
        answer="\n".join(lines)[:1800],
        cited_ids=cited[:20],
        uncertainty=uncertainty,
    )


def _citable_ids(context: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for animal in context.get("animals", []):
        allowed.add(animal["animal_id"])
    for event in context.get("events", []):
        allowed.add(event["event_id"])
        allowed.update(source["observation_id"] for source in event.get("sources", []))
    for gap in context.get("data_gaps", []):
        allowed.add(gap["gap_id"])
    return allowed
