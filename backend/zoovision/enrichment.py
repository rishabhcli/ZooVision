from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

ENRICHMENT_INSTRUCTIONS = """
You phrase evidence for an animal-welfare support record. Use only the supplied
facts and source IDs. Do not assign or mention severity, diagnose, recommend
medication or treatment, infer intent, or add unsupported facts. Clearly retain
uncertainty. This text will be reviewed by a human keeper.
""".strip()


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    fact: str = Field(min_length=1, max_length=1000)


class EvidenceMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    animal_name: str
    behavior_label: str
    sources: list[EvidenceSource] = Field(min_length=1)


class EvidenceNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=100)
    factual_summary: str = Field(min_length=1, max_length=800)
    uncertainty: list[str]
    cited_source_ids: list[str] = Field(min_length=1)


class MorningAnimalFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animal_id: str
    animal_name: str
    event_facts: list[str]
    data_gap_facts: list[str]
    no_notable_events: bool


class MorningReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shift_label: str
    animals: list[MorningAnimalFacts] = Field(min_length=1)


class MorningAnimalNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animal_id: str
    summary: str = Field(min_length=1, max_length=500)


class MorningNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_summary: str = Field(min_length=1, max_length=800)
    animals: list[MorningAnimalNarrative] = Field(min_length=1)
    uncertainty: list[str]


class OpenAIEvidenceEnricher:
    def __init__(self, api_key: str, *, model: str, client: Any | None = None):
        self.model = model
        self.client = client or OpenAI(api_key=api_key)

    def merge(self, request: EvidenceMergeRequest) -> EvidenceNarrative:
        response = self.client.responses.parse(
            model=self.model,
            instructions=ENRICHMENT_INSTRUCTIONS,
            input=json.dumps(request.model_dump(mode="json")),
            text_format=EvidenceNarrative,
            reasoning={"effort": "low"},
            max_output_tokens=500,
            store=False,
        )
        narrative = response.output_parsed
        if narrative is None:
            raise ValueError("OpenAI returned no parsed evidence narrative")
        allowed = {source.source_id for source in request.sources}
        cited = set(narrative.cited_source_ids)
        if not cited.issubset(allowed) or not cited:
            raise ValueError("OpenAI narrative cited an unknown evidence source")
        return narrative


class OpenAIMorningReportWriter:
    def __init__(self, api_key: str, *, model: str, client: Any | None = None):
        self.model = model
        self.client = client or OpenAI(api_key=api_key)

    def write(self, request: MorningReportRequest) -> MorningNarrative:
        response = self.client.responses.parse(
            model=self.model,
            instructions=(
                ENRICHMENT_INSTRUCTIONS
                + "\nInclude every supplied animal, including animals with no notable events."
            ),
            input=json.dumps(request.model_dump(mode="json")),
            text_format=MorningNarrative,
            reasoning={"effort": "low"},
            max_output_tokens=1200,
            store=False,
        )
        narrative = response.output_parsed
        if narrative is None:
            raise ValueError("OpenAI returned no parsed morning narrative")
        expected = {animal.animal_id for animal in request.animals}
        actual = {animal.animal_id for animal in narrative.animals}
        if actual != expected or len(narrative.animals) != len(request.animals):
            raise ValueError("OpenAI morning narrative did not include each animal exactly once")
        return narrative
