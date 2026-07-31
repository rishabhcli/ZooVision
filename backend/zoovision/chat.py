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
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .store import SQLiteStore

CHAT_INSTRUCTIONS = """
You answer questions about an overnight animal-welfare shift record for keeper
staff.

Ground every statement in the supplied context JSON. Rules you must follow:
- Never assign, infer, revise, or imply a severity. Severity exists only where a
  deterministic rule already recorded it; quote it and name the rule.
- Never diagnose a condition, suggest a cause of illness, or recommend
  medication, treatment, or any enclosure action.
- For diagnosis, medication, treatment, or enclosure-action requests, refuse
  that part directly and leave moment_ids empty unless the user also asks to
  inspect a specific recorded time or activity.
- If the context does not answer the question, say so plainly and name the
  missing evidence or the recorded data gap. Never invent an observation,
  timestamp, animal, or event.
- Motion regions locate movement in the frame. They do not identify a species or
  a behavior. Do not describe them as either.
- Cite the ids of the context records you used in cited_ids.
- When the question asks where or when something happened, select up to five
  relevant observation ids in moment_ids. Only select ids present in moments.
- Write video positions as M:SS or H:MM:SS, including ranges such as
  "4:02-7:13". Never expose raw total-second positions in the prose answer.
- When retrieval includes a requested_media_offset_seconds value, answer from
  the observation intervals at or nearest that position in the selected video.
  Treat those media offsets as authoritative; wall-clock timestamps are not
  positions in the video.
- When retrieval includes referenced_media_offsets_seconds, treat those prior
  assistant timestamps only as lookup anchors. Verify them against the supplied
  observation intervals, and never reject an anchor that an observation covers.
- A `bedrock_embedding_failed` data gap means semantic vector indexing failed.
  It does not mean the footage, object detections, or structured observations
  are missing. Never use it to override an available structured observation or
  claim that the depicted activity is unknowable.
- Prefer `provider_structured` moments for footage lookup. Use
  `synthetic_scenario` moments only when the user explicitly asks about a demo
  scenario or the deterministic rule event that cites it.
- For any recording-wide inventory or activity-pattern question, cover every
  distinct animal type explicitly documented by the supplied moments. Do not
  infer an animal from the profile alone.
- For an animal-timing question, use every supplied matching moment to describe
  the documented intervals. Claim completeness only when
  animal_timing_all_matches_included is true.
- The recording_summary contains authoritative counts for the selected source.
  For rule or event questions, use those counts and never say footage or
  observations are absent when observation_count is greater than zero.
- Answer the user's actual question instead of listing every available tag or
  record. Synthesize the smallest useful answer, connect evidence across records,
  and explain why each cited record is relevant.
- Treat earlier conversation turns as context for follow-up questions. The newest
  user question controls the task when the subject changes.
- The scope identifies the animal, enclosure, camera, and video source currently
  selected in the console. Resolve phrases such as "this animal", "it", and
  "this camera" to that scope, and name the selected animal in the answer. The
  current scope is authoritative even when an earlier turn discussed a different
  animal or camera.
- Describe citations in keeper-friendly language in the answer. Never expose a
  raw database id in the answer, uncertainty text, or a suggested label.
- Distinguish absence of a recorded event from proof that nothing happened.
- Use plain text only. Short hyphen-led lines are fine, but do not emit Markdown
  headings, emphasis markers, tables, or code fences.
- Be brief and factual. Keep the answer under 900 characters; keeper staff read
  these during a night shift.
""".strip()

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_RAW_RECORD_ID_PATTERN = re.compile(
    r"(?<![a-z0-9])(?:animal|alert|chk|chunk|event|evt|gap|obs|observation)"
    r"[_-][a-z0-9_-]+(?![a-z0-9])",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "at",
    "be",
    "did",
    "do",
    "does",
    "for",
    "from",
    "give",
    "had",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "please",
    "show",
    "that",
    "the",
    "their",
    "there",
    "this",
    "to",
    "was",
    "were",
    "what",
    "which",
    "who",
    "with",
}
_SUMMARY_PHRASES = ("summary", "summarise", "summarize", "overview", "what happened", "report")
_GAP_PHRASES = ("gap", "missing", "coverage", "camera loss", "unavailable")
_QUIET_PHRASES = ("no event", "no recorded event", "quiet animal", "nothing recorded")
_MOMENT_PHRASES = ("footage", "clip", "video", "where", "when", "find", "moment")
_EVENT_PHRASES = ("event", "severity", "rule", "evidence", "support", "highest")
_MEDIA_TIMESTAMP_PATTERN = re.compile(
    r"\b(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,3}):(?P<seconds>[0-5]\d)\b"
)
_MINUTES_SECONDS_PATTERN = re.compile(
    r"\b(?P<minutes>\d+(?:\.\d+)?)\s*(?:minutes?|mins?)"
    r"(?:\s*(?:and\s*)?(?P<seconds>\d+(?:\.\d+)?)\s*(?:seconds?|secs?))?\b",
    re.IGNORECASE,
)
_SECONDS_PATTERN = re.compile(
    r"\b(?P<seconds>\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b",
    re.IGNORECASE,
)
_RAW_VIDEO_SECONDS_PATTERN = re.compile(
    r"(?<![\w.])(?P<seconds>\d+(?:\.\d+)?)\s*s(?![\w])",
    re.IGNORECASE,
)
_RAW_VIDEO_SECONDS_RANGE_PATTERN = re.compile(
    r"\bfrom\s+(?P<start>\d+(?:\.\d+)?)\s*(?:to|-)\s*"
    r"(?P<end>\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b",
    re.IGNORECASE,
)
_RAW_VIDEO_SECONDS_AT_PATTERN = re.compile(
    r"\bat\s+(?P<seconds>\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b",
    re.IGNORECASE,
)
_EMBEDDING_GAP_REASONS = {"bedrock_embedding_failed"}
_TEMPORAL_MOMENT_WINDOW_SECONDS = 120.0
_INTENT_TERMS = {
    "event",
    "evidence",
    "happened",
    "highest",
    "overview",
    "recorded",
    "report",
    "rule",
    "severity",
    "shift",
    "summarise",
    "summarize",
    "summary",
    "tonight",
}
_GENERIC_ANIMAL_PROFILE_TERMS = {
    "animal",
    "backyard",
    "camera",
    "enclosure",
    "selected",
    "unspecified",
    "wildlife",
}
_COMMON_ANIMAL_TYPE_TERMS = {
    "badger",
    "bear",
    "bird",
    "condor",
    "deer",
    "elephant",
    "giraffe",
    "gorilla",
    "lion",
    "rabbit",
    "raccoon",
    "squirrel",
}


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    enclosure_id: str | None = None
    animal_id: str | None = None
    camera_id: str | None = Field(default=None, max_length=120)
    source_path: str | None = Field(default=None, max_length=400)


class ChatAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=1800)
    cited_ids: list[str]
    uncertainty: list[str]
    moment_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("answer", mode="before")
    @classmethod
    def bound_answer_length(cls, value: Any) -> Any:
        if not isinstance(value, str) or len(value) <= 1800:
            return value
        boundary = value.rfind(" ", 0, 1797)
        if boundary < 1400:
            boundary = 1797
        return f"{value[:boundary].rstrip()}..."

    @field_validator("moment_ids", mode="before")
    @classmethod
    def bound_moment_count(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return list(value[:5])
        return value


class ChatMoment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    source_path: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    label: str
    camera_id: str
    enclosure_id: str
    animal_name: str


class ChatCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    label: str
    kind: str


class ChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    cited_ids: list[str]
    uncertainty: list[str]
    mode: str
    model: str | None = None
    context_record_count: int
    citations: list[ChatCitation] = Field(default_factory=list)
    moments: list[ChatMoment] = Field(default_factory=list)

    @field_validator("answer")
    @classmethod
    def humanize_video_second_references(cls, answer: str) -> str:
        return _humanize_video_second_references(answer)


def build_context(
    store: SQLiteStore,
    *,
    enclosure_id: str | None = None,
    animal_id: str | None = None,
    camera_id: str | None = None,
    source_path: str | None = None,
    event_limit: int = 40,
) -> dict[str, Any]:
    """Collect the shift record the assistant is allowed to read."""
    dashboard = store.dashboard()
    animals = dashboard["animals"]
    events = dashboard["events"]
    gaps = dashboard["data_gaps"]
    moments = store.searchable_moments(
        enclosure_id=enclosure_id,
        animal_id=animal_id,
        camera_id=camera_id,
        source_path=source_path,
    )
    if source_path:
        moments = [moment for moment in moments if moment["source_path"] == source_path]
    elif camera_id:
        moments = [moment for moment in moments if moment["camera_id"] == camera_id]

    if enclosure_id:
        animals = [a for a in animals if a["enclosure_id"] == enclosure_id]
        events = [e for e in events if e["enclosure_id"] == enclosure_id]
        gaps = [g for g in gaps if g["enclosure_id"] == enclosure_id]
    if animal_id:
        animals = [a for a in animals if a["animal_id"] == animal_id]
        events = [e for e in events if e["animal_id"] == animal_id]

    observations = {row["observation_id"]: row for row in store.dump_table("observations")}
    chunks = {row["chunk_id"]: row for row in store.dump_table("video_chunks")}
    trimmed_events = []
    scoped_event_count = 0
    for event in events:
        detail_sources = []
        for source_id in event.get("source_observation_ids", []):
            observation = observations.get(source_id)
            if observation is None:
                continue
            chunk = chunks.get(observation["chunk_id"], {})
            if source_path and chunk.get("source_path") != source_path:
                continue
            if camera_id and not source_path and chunk.get("camera_id") != camera_id:
                continue
            detail_sources.append(
                {
                    "observation_id": source_id,
                    "evidence": observation["evidence"],
                    "provider": observation["provider"],
                    "evidence_kind": observation["evidence_kind"],
                    "camera_id": chunk.get("camera_id"),
                    "source_path": chunk.get("source_path"),
                }
            )
        if source_path and not any(
            source["source_path"] == source_path for source in detail_sources
        ):
            continue
        if (
            camera_id
            and not source_path
            and not any(source["camera_id"] == camera_id for source in detail_sources)
        ):
            continue
        scoped_event_count += 1
        if len(trimmed_events) < event_limit:
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

    scoped_gaps = []
    for gap in gaps:
        chunk = chunks.get(gap.get("chunk_id"), {})
        if source_path and chunk.get("source_path") != source_path:
            continue
        if camera_id and not source_path and chunk.get("camera_id") != camera_id:
            continue
        scoped_gap = {
            "gap_id": gap["gap_id"],
            "enclosure_id": gap["enclosure_id"],
            "reason": gap["reason"],
            "detail": gap["detail"],
            "start_ts": gap["start_ts"],
            "end_ts": gap["end_ts"],
        }
        if chunk:
            source_offset = float(chunk.get("source_offset_seconds") or 0)
            scoped_gap["start_seconds"] = round(
                max(
                    0.0,
                    source_offset
                    + _seconds_between_iso(chunk.get("start_ts"), gap.get("start_ts")),
                ),
                3,
            )
            scoped_gap["end_seconds"] = round(
                max(
                    0.0,
                    source_offset + _seconds_between_iso(chunk.get("start_ts"), gap.get("end_ts")),
                ),
                3,
            )
        scoped_gaps.append(scoped_gap)

    recording_summary = None
    if source_path or camera_id:
        recording_summary = {
            "source_path": source_path,
            "camera_id": camera_id,
            "observation_count": len(moments),
            "event_count": scoped_event_count,
            "coverage_gap_count": sum(not _is_embedding_only_gap(gap) for gap in scoped_gaps),
            "indexing_gap_count": sum(_is_embedding_only_gap(gap) for gap in scoped_gaps),
        }

    return {
        "scope": {
            "enclosure_id": enclosure_id,
            "animal_id": animal_id,
            "camera_id": camera_id,
            "source_path": source_path,
        },
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
        "moments": moments,
        "data_gaps": scoped_gaps,
        "recording_summary": recording_summary,
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
        + len(context.get("moments", []))
        + len(context.get("data_gaps", []))
        + int(context.get("recording_summary") is not None)
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
        full_context = build_context(
            self.store,
            enclosure_id=request.enclosure_id,
            animal_id=request.animal_id,
            camera_id=request.camera_id,
            source_path=request.source_path,
        )
        context = retrieve_context(full_context, request.messages)
        count = context_record_count(context)
        current_question = request.messages[-1].content
        if (
            context.get("retrieval", {}).get("no_match")
            or _asks_for_prohibited_guidance(current_question)
            or _asks_for_recording_counts(current_question)
        ):
            answer = summarize(context, request.messages)
            return ChatReply(
                answer=answer.answer,
                cited_ids=answer.cited_ids,
                uncertainty=answer.uncertainty,
                mode="deterministic",
                model=None,
                context_record_count=count,
                citations=_resolve_citations(context, answer.cited_ids),
                moments=_resolve_moments(context, answer.moment_ids),
            )
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
                    citations=_resolve_citations(context, answer.cited_ids),
                    moments=_resolve_moments(context, answer.moment_ids),
                )
            except Exception as error:  # noqa: BLE001 - degrade to the grounded summary
                if not self.allow_fallback:
                    raise RuntimeError("live OpenAI chat is unavailable") from error
                fallback = summarize(context, request.messages)
                fallback.uncertainty.append(
                    f"The language model was unavailable ({type(error).__name__}); "
                    "this answer was assembled directly from the shift record."
                )
                return ChatReply(
                    answer=fallback.answer,
                    cited_ids=fallback.cited_ids,
                    uncertainty=fallback.uncertainty,
                    mode="deterministic_fallback",
                    model=None,
                    context_record_count=count,
                    citations=_resolve_citations(context, fallback.cited_ids),
                    moments=_resolve_moments(context, fallback.moment_ids),
                )
        if not self.allow_fallback:
            raise RuntimeError("live OpenAI chat is not configured")
        answer = summarize(context, request.messages)
        return ChatReply(
            answer=answer.answer,
            cited_ids=answer.cited_ids,
            uncertainty=answer.uncertainty,
            mode="deterministic",
            model=None,
            context_record_count=count,
            citations=_resolve_citations(context, answer.cited_ids),
            moments=_resolve_moments(context, answer.moment_ids),
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
            reasoning={"effort": "medium"},
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
        allowed_moments = {moment["observation_id"] for moment in context.get("moments", [])}
        unknown_moments = [moment for moment in answer.moment_ids if moment not in allowed_moments]
        if unknown_moments:
            raise ValueError(f"chat answer selected unknown moments: {unknown_moments[:3]}")
        answer = answer.model_copy(
            update={
                "answer": _humanize_raw_record_ids(answer.answer, context),
                "uncertainty": [
                    _humanize_raw_record_ids(item, context) for item in answer.uncertainty
                ],
                "moment_ids": (
                    []
                    if context.get("retrieval", {}).get("safety_boundary")
                    and context.get("retrieval", {}).get("requested_media_offset_seconds") is None
                    else answer.moment_ids
                ),
            }
        )
        return answer


def retrieve_context(
    context: dict[str, Any],
    messages: list[ChatMessage],
) -> dict[str, Any]:
    """Select records that can answer the current turn before synthesis.

    This is intentionally lexical and deterministic. It prevents a broad shift
    record from turning into arbitrary "top tags", while the language model is
    still responsible for phrasing and multi-turn synthesis.
    """
    question = messages[-1].content
    previous_users = [message.content for message in messages[:-1] if message.role == "user"]
    previous_assistants = [
        message.content for message in messages[:-1] if message.role == "assistant"
    ]
    follow_up = _looks_like_follow_up(question)
    query = question
    if follow_up and previous_users:
        query = f"{previous_users[-1]} {question}"

    intents = _query_intents(query)
    explicit_offsets_seconds = _requested_media_offsets_seconds(question)
    requested_offset_seconds = explicit_offsets_seconds[0] if explicit_offsets_seconds else None
    referenced_offsets_seconds: list[float] = []
    if follow_up and not explicit_offsets_seconds:
        for prior_text in [
            previous_assistants[-1] if previous_assistants else "",
            previous_users[-1] if previous_users else "",
        ]:
            referenced_offsets_seconds = _requested_media_offsets_seconds(prior_text)
            if referenced_offsets_seconds:
                break
    temporal_offsets_seconds = explicit_offsets_seconds or referenced_offsets_seconds
    terms = _tokens(query)
    content_terms = terms - _INTENT_TERMS
    animals = context.get("animals", [])
    matched_animal_ids = {
        animal["animal_id"]
        for animal in animals
        if _record_score(animal, terms, ("name", "species", "enclosure_id")) > 0
    }
    scoped_animal_id = context.get("scope", {}).get("animal_id")
    if scoped_animal_id and _uses_scoped_subject(question):
        matched_animal_ids = {scoped_animal_id}
    unresolved_scoped_subject = bool(
        _uses_scoped_subject(question) and not scoped_animal_id and not matched_animal_ids
    )
    if unresolved_scoped_subject:
        terms = set()
        content_terms = set()
    matched_enclosures = {
        animal["enclosure_id"] for animal in animals if animal["animal_id"] in matched_animal_ids
    }
    broad = intents["summary"] or intents["quiet"]

    ranked_events = _rank_records(
        context.get("events", []),
        terms,
        (
            "animal_id",
            "animal_name",
            "enclosure_id",
            "behavior",
            "rule_fired",
            "action",
            "explanation_facts",
        ),
    )
    if matched_animal_ids:
        ranked_events = [
            (score + 20, event)
            for score, event in ranked_events
            if event["animal_id"] in matched_animal_ids
        ]
    if broad:
        if matched_animal_ids:
            selected_events = [event for _, event in ranked_events][:20]
        elif content_terms:
            selected_events = [event for score, event in ranked_events if score > 0][:12]
        else:
            selected_events = context.get("events", [])[:20]
    else:
        selected_events = [event for score, event in ranked_events if score > 0][:12]

    allow_synthetic = _explicitly_requests_demo(query)
    event_source_ids = {
        source["observation_id"] for event in selected_events for source in event.get("sources", [])
    }
    candidate_moments = [
        moment
        for moment in context.get("moments", [])
        if allow_synthetic
        or moment.get("evidence_kind") != "synthetic_scenario"
        or moment["observation_id"] in event_source_ids
    ]
    animal_timing_terms = _requested_animal_timing_terms(question)
    animal_timing_matches = [
        moment
        for moment in candidate_moments
        if animal_timing_terms & _moment_descriptive_animal_terms(moment)
    ]
    animal_timing_matches.sort(
        key=lambda moment: (
            float(moment.get("start_seconds") or 0),
            float(moment.get("end_seconds") or 0),
            moment["observation_id"],
        )
    )
    undocumented_profile_terms = (
        set()
        if requested_offset_seconds is not None
        else _undocumented_requested_profile_terms(
            question,
            animals,
            candidate_moments,
        )
    )
    ranked_moments = _rank_records(
        candidate_moments,
        terms,
        (
            "animal_id",
            "animal_name",
            "species",
            "enclosure_id",
            "camera_id",
            "behavior",
            "activity_label",
            "evidence",
        ),
    )
    if matched_animal_ids:
        ranked_moments = [
            (score + 20, moment)
            for score, moment in ranked_moments
            if moment["animal_id"] in matched_animal_ids
        ]
    relevant_moments = [
        moment
        for score, moment in ranked_moments
        if score > 0 or moment["observation_id"] in event_source_ids
    ]
    recording_inventory = bool(
        requested_offset_seconds is None
        and context.get("scope", {}).get("source_path")
        and (
            _asks_for_recording_inventory(question)
            or _asks_about_activity_pattern(question)
            or intents["summary"]
        )
    )
    if recording_inventory:
        relevant_moments = _select_recording_inventory_moments(
            ranked_moments,
            animals,
            limit=20,
        )
    if animal_timing_terms:
        relevant_moments = animal_timing_matches[:20]
    if undocumented_profile_terms:
        relevant_moments = []
    if intents["summary"] and not content_terms and not relevant_moments:
        relevant_moments = [moment for _, moment in ranked_moments[:5]]
    if matched_animal_ids and _asks_about_activity_pattern(question) and not relevant_moments:
        relevant_moments = [moment for _, moment in ranked_moments[:8]]
    if intents["quiet"] or intents["gaps"] and not intents["moments"]:
        relevant_moments = []
    if temporal_offsets_seconds and not intents["quiet"]:
        relevant_moments = _select_temporal_moments_for_offsets(
            ranked_moments,
            temporal_offsets_seconds,
            limit=20,
        )
        temporal_moment_ids = {moment["observation_id"] for moment in relevant_moments}
        selected_events = [
            event
            for event in selected_events
            if any(
                source["observation_id"] in temporal_moment_ids
                for source in event.get("sources", [])
            )
        ]

    gaps = context.get("data_gaps", [])
    if temporal_offsets_seconds:
        gaps = _select_temporal_gaps_for_offsets(gaps, temporal_offsets_seconds)
        if relevant_moments:
            gaps = [gap for gap in gaps if not _is_embedding_only_gap(gap)]
    elif not intents["gaps"]:
        if not intents["summary"]:
            gaps = [gap for gap in gaps if not _is_embedding_only_gap(gap)]
        if matched_enclosures:
            gaps = [gap for gap in gaps if gap["enclosure_id"] in matched_enclosures]
        elif not intents["summary"] or content_terms:
            gaps = [
                gap
                for gap in gaps
                if _record_score(
                    gap,
                    terms,
                    ("gap_id", "enclosure_id", "reason", "detail", "start_ts", "end_ts"),
                )
                > 0
            ]

    selected_animals = animals
    if matched_animal_ids and not intents["quiet"]:
        selected_animals = [
            animal for animal in animals if animal["animal_id"] in matched_animal_ids
        ]

    return {
        **context,
        "animals": selected_animals,
        "events": selected_events,
        "moments": relevant_moments[:20],
        "data_gaps": gaps[:12],
        "retrieval": {
            "query": question,
            "resolved_query": query,
            "intents": [name for name, active in intents.items() if active],
            "matched_animal_ids": sorted(matched_animal_ids),
            "requested_media_offset_seconds": requested_offset_seconds,
            "referenced_media_offsets_seconds": referenced_offsets_seconds,
            "recording_inventory": recording_inventory,
            "animal_timing_terms": sorted(animal_timing_terms),
            "animal_timing_match_count": len(animal_timing_matches),
            "animal_timing_all_matches_included": len(animal_timing_matches) <= 20,
            "safety_boundary": _asks_for_prohibited_guidance(question),
            "undocumented_profile_terms": sorted(undocumented_profile_terms),
            "no_match": unresolved_scoped_subject
            or bool(undocumented_profile_terms and not selected_events)
            or bool(
                animals
                and content_terms
                and not matched_animal_ids
                and not selected_events
                and not relevant_moments
                and not gaps
                and not (
                    intents["events"]
                    and (context.get("recording_summary") or {}).get("event_count") == 0
                )
            ),
        },
    }


def summarize(
    context: dict[str, Any],
    question: str | list[ChatMessage],
) -> ChatAnswer:
    """Assemble a factual answer straight from the record, with no model.

    This keeps the console useful when the language model is unreachable, and it
    keeps the same boundaries: it quotes recorded severities and rules and never
    derives a new one.
    """
    events = context.get("events", [])
    animals = context.get("animals", [])
    gaps = context.get("data_gaps", [])
    moments = context.get("moments", [])
    recording_summary = context.get("recording_summary")
    asked = question[-1].content.lower() if isinstance(question, list) else question.lower()
    intents = _query_intents(asked)
    requested_offset_seconds = context.get("retrieval", {}).get("requested_media_offset_seconds")
    temporal_question = requested_offset_seconds is not None
    activity_question = _asks_about_activity_pattern(asked) or temporal_question
    selected = [] if activity_question else events
    selected_moments = moments

    if _asks_for_prohibited_guidance(asked):
        return ChatAnswer(
            answer=(
                "I cannot diagnose an animal, prescribe medication or treatment, "
                "change a recorded severity, or operate an enclosure. I can summarize "
                "recorded observations and existing deterministic rule results for "
                "keeper review."
            ),
            cited_ids=[],
            uncertainty=[],
            moment_ids=[],
        )

    if recording_summary and _asks_for_recording_counts(asked):
        answer = (
            f"The selected recording contains "
            f"{recording_summary['observation_count']} structured observations and "
            f"{recording_summary['event_count']} deterministic rule events."
        )
        if "observation id" in asked or "raw observation" in asked:
            answer += (
                " The assistant presents timestamped evidence instead of dumping "
                "internal record IDs; ask for an animal, activity, or time range to "
                "open the relevant moments."
            )
        return ChatAnswer(
            answer=answer,
            cited_ids=[],
            uncertainty=[],
            moment_ids=[],
        )

    if context.get("retrieval", {}).get("no_match"):
        if recording_summary and recording_summary["observation_count"] > 0:
            return ChatAnswer(
                answer=(
                    f"The selected recording contains "
                    f"{recording_summary['observation_count']} structured observations, "
                    "but none match that question. I did not substitute unrelated animals "
                    "or moments."
                ),
                cited_ids=[],
                uncertainty=[
                    "No matching record was found; this is not proof that nothing happened."
                ],
            )
        return ChatAnswer(
            answer=(
                "I could not find recorded evidence that answers that question. "
                "Try naming an animal, enclosure, behavior, rule, or asking for the shift summary."
            ),
            cited_ids=[],
            uncertainty=["No matching record was found; this is not proof that nothing happened."],
        )

    if not animals:
        return ChatAnswer(
            answer="No animals are in scope for this view, so there is nothing to report.",
            cited_ids=[],
            uncertainty=["The current scope contains no monitored animals."],
        )

    lines: list[str] = []
    cited: list[str] = []
    quiet = [animal for animal in animals if animal["event_count"] == 0]

    if activity_question:
        pass
    elif intents["quiet"]:
        if quiet:
            lines.append(
                "Animals with no deterministic welfare events recorded in this view: "
                + ", ".join(sorted(animal["name"] for animal in quiet))
                + "."
            )
            cited.extend(animal["animal_id"] for animal in quiet)
        else:
            lines.append("Every animal in this view has at least one recorded welfare event.")
    elif intents["gaps"] and not selected and not selected_moments:
        lines.append("I found no event or footage record relevant to that question.")
    elif selected:
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
    elif not intents["gaps"] and not intents["summary"]:
        if recording_summary and intents["events"]:
            lines.append(
                "No deterministic welfare events are recorded for this view. "
                f"The selected recording contains "
                f"{recording_summary['observation_count']} structured observation(s) and "
                f"{recording_summary['event_count']} rule event(s)."
            )
        else:
            lines.append("No deterministic welfare events are recorded for this view.")

    if selected_moments and not intents["quiet"]:
        activity_counts: dict[str, int] = {}
        for moment in selected_moments:
            label = moment.get("activity_label") or moment["behavior"].replace("_", " ")
            activity_counts[label] = activity_counts.get(label, 0) + 1
        if temporal_question:
            lines.append(
                f"Around {_display_offset(float(requested_offset_seconds))} in the "
                "selected video, the structured footage record shows:"
            )
            for moment in selected_moments[:5]:
                label = (
                    moment.get("activity_label")
                    or moment.get("evidence")
                    or moment["behavior"].replace("_", " ")
                )
                lines.append(
                    f"- {_human_label(label)} "
                    f"({_display_offset(moment['start_seconds'])}-"
                    f"{_display_offset(moment['end_seconds'])})."
                )
                cited.append(moment["observation_id"])
        elif activity_question:
            subject = animals[0]["name"] if len(animals) == 1 else "The selected animals"
            activities = sorted(
                activity_counts,
                key=lambda label: (-activity_counts[label], label.lower()),
            )
            lines.append(
                f"In the available footage, {subject} was recorded "
                + _natural_join(activities[:4])
                + "."
            )
            lines.append(
                "These are recorded moments from the selected camera, not enough evidence "
                "to establish a usual behavior pattern."
            )
        else:
            lines.append(
                f"{len(selected_moments)} tracked footage moment(s) are available for review."
            )
        if not temporal_question:
            for moment in selected_moments[:5]:
                label = moment.get("activity_label") or moment["behavior"].replace("_", " ")
                lines.append(
                    f"- {moment['animal_name']} on {moment['camera_id']}: {label} at "
                    f"{_display_offset(float(moment['start_seconds']))}. {moment['evidence']}"
                )
                cited.append(moment["observation_id"])
    elif activity_question:
        if temporal_question:
            lines.append(
                "No structured footage observation was recorded near "
                f"{_display_offset(float(requested_offset_seconds))} in this view."
            )
        else:
            lines.append("No recorded footage moments match that activity question in this view.")

    if quiet and intents["summary"] and not intents["quiet"]:
        lines.append(
            "Animals with no recorded events: "
            + ", ".join(sorted(animal["name"] for animal in quiet))
            + "."
        )
        cited.extend(animal["animal_id"] for animal in quiet)

    uncertainty: list[str] = []
    coverage_gaps = [gap for gap in gaps if not _is_embedding_only_gap(gap)]
    embedding_gaps = [gap for gap in gaps if _is_embedding_only_gap(gap)]
    if coverage_gaps:
        lines.append(f"{len(coverage_gaps)} coverage gap(s) limit what could be observed:")
        for gap in coverage_gaps[:3]:
            lines.append(
                f"- {gap['enclosure_id']}: {gap['reason'].replace('_', ' ')} "
                f"between {gap['start_ts']} and {gap['end_ts']}."
            )
            cited.append(gap["gap_id"])
        uncertainty.append("Recorded coverage gaps mean the record may be incomplete.")
    if embedding_gaps:
        lines.append(
            f"{len(embedding_gaps)} semantic indexing issue(s) were recorded. "
            "They affect vector lookup, not the availability of footage or structured "
            "observations."
        )
        cited.extend(gap["gap_id"] for gap in embedding_gaps[:3])
        uncertainty.append(
            "Semantic lookup was incomplete; direct structured observations remain available."
        )

    if not cited and not gaps and not (recording_summary and intents["events"]):
        if temporal_question:
            lines = [
                "I could not find a structured footage observation near "
                f"{_display_offset(float(requested_offset_seconds))} in this view."
            ]
        elif activity_question:
            lines = ["I could not find recorded footage that answers that activity question."]
        else:
            lines = [
                "I could not find recorded evidence that answers that question.",
                "Try naming an animal, enclosure, behavior, rule, or asking for the shift summary.",
            ]
        uncertainty.append("No matching record was found; this is not proof that nothing happened.")

    return ChatAnswer(
        answer="\n".join(lines)[:1800],
        cited_ids=cited[:20],
        uncertainty=uncertainty,
        moment_ids=[moment["observation_id"] for moment in selected_moments[:5]],
    )


def _query_intents(query: str) -> dict[str, bool]:
    lowered = query.lower()
    return {
        "summary": any(phrase in lowered for phrase in _SUMMARY_PHRASES),
        "gaps": any(phrase in lowered for phrase in _GAP_PHRASES),
        "quiet": any(phrase in lowered for phrase in _QUIET_PHRASES),
        "moments": any(phrase in lowered for phrase in _MOMENT_PHRASES),
        "events": any(phrase in lowered for phrase in _EVENT_PHRASES),
    }


def _requested_media_offset_seconds(query: str) -> float | None:
    """Parse an explicit position in the selected video from a question."""
    timestamp = _MEDIA_TIMESTAMP_PATTERN.search(query)
    if timestamp:
        hours = int(timestamp.group("hours") or 0)
        minutes = int(timestamp.group("minutes"))
        seconds = int(timestamp.group("seconds"))
        return float(hours * 3600 + minutes * 60 + seconds)

    minutes_match = _MINUTES_SECONDS_PATTERN.search(query)
    if minutes_match:
        minutes = float(minutes_match.group("minutes"))
        seconds = float(minutes_match.group("seconds") or 0)
        return minutes * 60 + seconds

    seconds_match = _SECONDS_PATTERN.search(query)
    if seconds_match:
        return float(seconds_match.group("seconds"))
    return None


def _requested_media_offsets_seconds(query: str) -> list[float]:
    """Return every explicit playback timestamp, preserving textual order."""
    offsets: list[float] = []
    for timestamp in _MEDIA_TIMESTAMP_PATTERN.finditer(query):
        hours = int(timestamp.group("hours") or 0)
        minutes = int(timestamp.group("minutes"))
        seconds = int(timestamp.group("seconds"))
        offset = float(hours * 3600 + minutes * 60 + seconds)
        if offset not in offsets:
            offsets.append(offset)
    if offsets:
        return offsets

    offset = _requested_media_offset_seconds(query)
    return [offset] if offset is not None else []


def _select_temporal_moments(
    ranked_moments: list[tuple[int, dict[str, Any]]],
    target_seconds: float,
) -> list[dict[str, Any]]:
    """Prefer observations covering the requested frame, then nearby evidence."""
    scored: list[tuple[float, int, float, int, float, dict[str, Any]]] = []
    for lexical_score, moment in ranked_moments:
        start = float(moment.get("start_seconds") or 0)
        end = max(start, float(moment.get("end_seconds") or start))
        distance = _interval_distance(target_seconds, start, end)
        provider_rank = 0 if moment.get("evidence_kind") == "provider_structured" else 1
        scored.append(
            (
                distance,
                provider_rank,
                end - start,
                -lexical_score,
                start,
                moment,
            )
        )

    overlapping = [item for item in scored if item[0] == 0]
    if overlapping:
        return [item[-1] for item in sorted(overlapping)[:5]]

    nearby = [item for item in scored if item[0] <= _TEMPORAL_MOMENT_WINDOW_SECONDS]
    return [item[-1] for item in sorted(nearby)[:5]]


def _select_temporal_moments_for_offsets(
    ranked_moments: list[tuple[int, dict[str, Any]]],
    offsets_seconds: list[float],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for offset_seconds in offsets_seconds:
        for moment in _select_temporal_moments(ranked_moments, offset_seconds):
            selected[moment["observation_id"]] = moment
    return sorted(
        selected.values(),
        key=lambda moment: (
            float(moment.get("start_seconds") or 0),
            float(moment.get("end_seconds") or 0),
            moment["observation_id"],
        ),
    )[:limit]


def _select_temporal_gaps(
    gaps: list[dict[str, Any]],
    target_seconds: float,
) -> list[dict[str, Any]]:
    """Keep only gaps whose source-relative interval is near the requested time."""
    relevant: list[tuple[float, dict[str, Any]]] = []
    for gap in gaps:
        if "start_seconds" not in gap or "end_seconds" not in gap:
            continue
        start = float(gap["start_seconds"])
        end = max(start, float(gap["end_seconds"]))
        distance = _interval_distance(target_seconds, start, end)
        if distance <= _TEMPORAL_MOMENT_WINDOW_SECONDS:
            relevant.append((distance, gap))
    return [gap for _, gap in sorted(relevant, key=lambda item: item[0])[:12]]


def _select_temporal_gaps_for_offsets(
    gaps: list[dict[str, Any]],
    offsets_seconds: list[float],
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for offset_seconds in offsets_seconds:
        for gap in _select_temporal_gaps(gaps, offset_seconds):
            selected[gap["gap_id"]] = gap
    return list(selected.values())[:12]


def _interval_distance(target: float, start: float, end: float) -> float:
    if start <= target <= end:
        return 0.0
    return min(abs(target - start), abs(target - end))


def _is_embedding_only_gap(gap: dict[str, Any]) -> bool:
    return str(gap.get("reason", "")).lower() in _EMBEDDING_GAP_REASONS


def _seconds_between_iso(start_iso: Any, end_iso: Any) -> float:
    try:
        return (
            datetime.fromisoformat(str(end_iso)) - datetime.fromisoformat(str(start_iso))
        ).total_seconds()
    except (TypeError, ValueError):
        return 0.0


def _tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    tokens = set(_TOKEN_PATTERN.findall(str(value).lower().replace("_", " ")))
    normalized = {
        token[:-1] if token.endswith("s") and len(token) > 4 else token for token in tokens
    }
    return normalized - _STOP_WORDS


def _record_score(record: dict[str, Any], terms: set[str], fields: tuple[str, ...]) -> int:
    if not terms:
        return 0
    score = 0
    for index, field in enumerate(fields):
        overlap = terms & _tokens(record.get(field, ""))
        if overlap:
            score += len(overlap) * max(1, 5 - index // 2)
    return score


def _rank_records(
    records: list[dict[str, Any]],
    terms: set[str],
    fields: tuple[str, ...],
) -> list[tuple[int, dict[str, Any]]]:
    ranked = [(_record_score(record, terms, fields), record) for record in records]
    return sorted(ranked, key=lambda item: item[0], reverse=True)


def _looks_like_follow_up(question: str) -> bool:
    lowered = question.strip().lower()
    return (
        len(_tokens(lowered)) <= 3
        or lowered.startswith(("and ", "what about", "how about", "why ", "when ", "where "))
        or any(word in _tokens(lowered) for word in ("it", "that", "them", "those"))
    )


def _uses_scoped_subject(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "this animal",
            "that animal",
            "selected animal",
            "current animal",
            "this camera",
            "selected camera",
        )
    ) or "it" in _tokens(lowered)


def _asks_about_activity_pattern(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "usually do",
            "usually doing",
            "normal behavior",
            "normally do",
            "normally doing",
            "what is it doing",
            "what did it do",
            "what has it been doing",
            "what is this animal doing",
            "what did this animal do",
            "what are they doing",
            "what were they doing",
            "doing in this video",
            "doing on this camera",
            "usual activity",
            "normal activity",
            "activity pattern",
        )
    )


def _asks_for_prohibited_guidance(question: str) -> bool:
    lowered = question.lower()
    return any(
        phrase in lowered
        for phrase in (
            "diagnos",
            "medicine",
            "medication",
            "prescribe",
            "treatment",
            "what drug",
            "administer",
            "open the enclosure",
            "open the gate",
            "act on the enclosure",
        )
    )


def _asks_for_recording_counts(question: str) -> bool:
    lowered = question.lower()
    record_terms = (
        "observation",
        "rule event",
        "welfare event",
        "recorded event",
        "observation id",
        "raw observation",
    )
    return any(term in lowered for term in record_terms) and any(
        phrase in lowered for phrase in ("how many", "count", "number of", "every raw", "all raw")
    )


def _undocumented_requested_profile_terms(
    question: str,
    animals: list[dict[str, Any]],
    moments: list[dict[str, Any]],
) -> set[str]:
    """Reject animal types that exist only in a generic wildlife profile.

    Backyard profiles describe the set of animals a camera may cover. They are
    not evidence that every listed species appears in every recording.
    """
    generic_profiles = [
        animal
        for animal in animals
        if _tokens(str(animal.get("name") or ""))
        & {"backyard", "unassigned", "unspecified", "wildlife"}
    ]
    if not generic_profiles:
        return set()

    profile_terms: set[str] = set()
    for animal in generic_profiles:
        profile_terms.update(_normalized_lexemes(str(animal.get("species") or "")))
    profile_terms -= _GENERIC_ANIMAL_PROFILE_TERMS

    requested = _normalized_lexemes(question) & (profile_terms | _COMMON_ANIMAL_TYPE_TERMS)
    if not requested:
        return set()

    documented: set[str] = set()
    for moment in moments:
        documented.update(
            _normalized_lexemes(
                " ".join(
                    str(moment.get(field) or "")
                    for field in ("activity_label", "evidence", "behavior")
                )
            )
        )
    return requested - documented


def _normalized_lexemes(text: str) -> set[str]:
    normalized: set[str] = set()
    for token in _tokens(text):
        normalized.add(token)
        base = token
        if len(token) > 3 and token.endswith("ies"):
            base = f"{token[:-3]}y"
            normalized.add(base)
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            base = token[:-1]
            normalized.add(base)
        if base in {
            "blackbird",
            "cardinal",
            "crow",
            "dove",
            "finch",
            "jay",
            "pigeon",
            "robin",
            "sparrow",
        }:
            normalized.add("bird")
    return normalized


def _requested_animal_timing_terms(question: str) -> set[str]:
    lowered = question.lower()
    if not any(
        phrase in lowered for phrase in ("when", "appear", "visible", "show me", "find", "moment")
    ):
        return set()
    return _normalized_lexemes(question) & _COMMON_ANIMAL_TYPE_TERMS


def _moment_descriptive_animal_terms(moment: dict[str, Any]) -> set[str]:
    return _normalized_lexemes(
        " ".join(
            str(moment.get(field) or "") for field in ("activity_label", "evidence", "behavior")
        )
    )


def _asks_for_recording_inventory(question: str) -> bool:
    """Recognize a broad request to inventory animals across one recording."""
    lowered = question.lower()
    asks_which_animals = any(
        phrase in lowered
        for phrase in (
            "what animal",
            "which animal",
            "what species",
            "which species",
            "animals are visible",
            "animals were visible",
        )
    )
    recording_language = any(
        term in _tokens(lowered)
        for term in ("camera", "clip", "footage", "recording", "video", "visible")
    )
    return asks_which_animals and recording_language


def _select_recording_inventory_moments(
    ranked_moments: list[tuple[int, dict[str, Any]]],
    animals: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Represent named animal types and the full timeline within the context cap.

    Broad inventory language gives most moments the same lexical score. Taking
    that ranking's first records therefore over-represents the start of a long
    video. Reserve evidence for animal terms grounded in the selected profile,
    then fill the remaining slots evenly across the recording.
    """
    if limit <= 0 or not ranked_moments:
        return []

    score_by_id = {moment["observation_id"]: score for score, moment in ranked_moments}
    chronological = sorted(
        (moment for _, moment in ranked_moments),
        key=lambda moment: (
            float(moment.get("start_seconds") or 0),
            float(moment.get("end_seconds") or 0),
            moment["observation_id"],
        ),
    )
    if len(chronological) <= limit:
        return chronological

    profile_terms: set[str] = set()
    for animal in animals:
        profile_terms.update(_tokens(f"{animal.get('name', '')} {animal.get('species', '')}"))
    profile_terms -= _GENERIC_ANIMAL_PROFILE_TERMS

    descriptive_tokens = {
        moment["observation_id"]: _tokens(
            " ".join(
                str(moment.get(field) or "") for field in ("activity_label", "evidence", "behavior")
            )
        )
        for moment in chronological
    }
    term_matches = {
        term: [
            moment
            for moment in chronological
            if term in descriptive_tokens[moment["observation_id"]]
        ]
        for term in profile_terms
    }

    selected: dict[str, dict[str, Any]] = {}
    for _term, matches in sorted(
        ((term, matches) for term, matches in term_matches.items() if matches),
        key=lambda item: (len(item[1]), item[0]),
    ):
        representative = max(
            matches,
            key=lambda moment: (
                len(profile_terms & descriptive_tokens[moment["observation_id"]]),
                score_by_id[moment["observation_id"]],
                -float(moment.get("start_seconds") or 0),
            ),
        )
        selected[representative["observation_id"]] = representative
        if len(selected) >= min(limit, 6):
            break

    remaining_slots = limit - len(selected)
    if remaining_slots > 0:
        if remaining_slots == 1:
            sample_indexes = [len(chronological) // 2]
        else:
            sample_indexes = [
                round(index * (len(chronological) - 1) / (remaining_slots - 1))
                for index in range(remaining_slots)
            ]
        for index in sample_indexes:
            moment = chronological[index]
            selected[moment["observation_id"]] = moment

    if len(selected) < limit:
        for moment in chronological:
            selected[moment["observation_id"]] = moment
            if len(selected) == limit:
                break

    return sorted(
        selected.values(),
        key=lambda moment: (
            float(moment.get("start_seconds") or 0),
            float(moment.get("end_seconds") or 0),
            moment["observation_id"],
        ),
    )[:limit]


def _natural_join(values: list[str]) -> str:
    if not values:
        return "with no activity label"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def _human_label(value: Any) -> str:
    label = str(value).strip().rstrip(".")
    return label[:1].upper() + label[1:] if label else "Recorded activity"


def _explicitly_requests_demo(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in ("demo", "fixture", "synthetic", "scenario"))


def _citable_ids(context: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    for animal in context.get("animals", []):
        allowed.add(animal["animal_id"])
    for event in context.get("events", []):
        allowed.add(event["event_id"])
        allowed.update(source["observation_id"] for source in event.get("sources", []))
    for moment in context.get("moments", []):
        allowed.add(moment["observation_id"])
    for gap in context.get("data_gaps", []):
        allowed.add(gap["gap_id"])
    return allowed


def _humanize_raw_record_ids(text: str, context: dict[str, Any]) -> str:
    """Replace internal ids with the same keeper-facing labels used by the UI."""
    labels = {
        citation.record_id.lower(): citation.label
        for citation in _resolve_citations(context, sorted(_citable_ids(context)))
    }

    def replacement(match: re.Match[str]) -> str:
        label = labels.get(match.group(0).lower())
        return f"the cited evidence ({label})" if label else "recorded evidence"

    return _RAW_RECORD_ID_PATTERN.sub(replacement, text)


def _humanize_video_second_references(text: str) -> str:
    """Convert standalone raw video-second positions to playback timestamps."""

    def range_replacement(match: re.Match[str]) -> str:
        start = _display_offset(float(match.group("start")))
        end = _display_offset(float(match.group("end")))
        return f"from {start} to {end}"

    def replacement(match: re.Match[str]) -> str:
        return _display_offset(float(match.group("seconds")))

    humanized = _RAW_VIDEO_SECONDS_RANGE_PATTERN.sub(range_replacement, text)
    humanized = _RAW_VIDEO_SECONDS_AT_PATTERN.sub(
        lambda match: f"at {replacement(match)}", humanized
    )
    return _RAW_VIDEO_SECONDS_PATTERN.sub(replacement, humanized)


def _resolve_moments(context: dict[str, Any], moment_ids: list[str]) -> list[ChatMoment]:
    requested = set(moment_ids)
    return [
        ChatMoment(
            observation_id=moment["observation_id"],
            source_path=moment["source_path"],
            start_seconds=moment["start_seconds"],
            end_seconds=moment["end_seconds"],
            label=moment.get("activity_label") or moment["behavior"].replace("_", " ").title(),
            camera_id=moment["camera_id"],
            enclosure_id=moment["enclosure_id"],
            animal_name=moment["animal_name"],
        )
        for moment in context.get("moments", [])
        if moment["observation_id"] in requested
    ]


def _resolve_citations(
    context: dict[str, Any],
    cited_ids: list[str],
) -> list[ChatCitation]:
    """Turn stable record ids into concise labels suitable for the console."""
    records: dict[str, ChatCitation] = {}
    for animal in context.get("animals", []):
        records[animal["animal_id"]] = ChatCitation(
            record_id=animal["animal_id"],
            label=f"{animal['name']} profile",
            kind="animal",
        )
    for event in context.get("events", []):
        records[event["event_id"]] = ChatCitation(
            record_id=event["event_id"],
            label=(
                f"{event['animal_name']}: {event['behavior'].replace('_', ' ')} event "
                f"at {_display_time(event['start_ts'])}"
            ),
            kind="event",
        )
        for source in event.get("sources", []):
            records[source["observation_id"]] = ChatCitation(
                record_id=source["observation_id"],
                label=f"{event['animal_name']}: supporting footage",
                kind="moment",
            )
    for moment in context.get("moments", []):
        label = moment.get("activity_label") or moment["behavior"].replace("_", " ").title()
        records[moment["observation_id"]] = ChatCitation(
            record_id=moment["observation_id"],
            label=(
                f"{moment['animal_name']}: {label} at {_display_offset(moment['start_seconds'])}"
            ),
            kind="moment",
        )
    for gap in context.get("data_gaps", []):
        gap_position = (
            _display_offset(float(gap["start_seconds"]))
            if "start_seconds" in gap
            else _display_time(gap["start_ts"])
        )
        records[gap["gap_id"]] = ChatCitation(
            record_id=gap["gap_id"],
            label=(f"{gap['enclosure_id']}: {gap['reason'].replace('_', ' ')} at {gap_position}"),
            kind="data_gap",
        )
    return [records[record_id] for record_id in cited_ids if record_id in records]


def _display_offset(seconds: float) -> str:
    total = max(0, int(seconds + 0.5))
    hours, remainder = divmod(total, 3600)
    minutes, remaining = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _display_time(timestamp: str) -> str:
    match = re.search(r"T(\d{2}):(\d{2})", timestamp)
    return f"{match.group(1)}:{match.group(2)}" if match else timestamp
