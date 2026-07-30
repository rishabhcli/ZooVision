from types import SimpleNamespace

import pytest
from zoovision.enrichment import (
    EvidenceMergeRequest,
    EvidenceNarrative,
    EvidenceSource,
    MorningAnimalFacts,
    MorningAnimalNarrative,
    MorningNarrative,
    MorningReportRequest,
    OpenAIEvidenceEnricher,
    OpenAIMorningReportWriter,
    StrandsEvidenceEnricher,
    StrandsMorningReportWriter,
)


class FakeResponses:
    def __init__(self, narrative):
        self.narrative = narrative
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.narrative)


class FakeOpenAI:
    def __init__(self, narrative):
        self.responses = FakeResponses(narrative)


def request():
    return EvidenceMergeRequest(
        event_id="evt-1",
        animal_name="Nox",
        behavior_label="pacing",
        sources=[
            EvidenceSource(source_id="obs-1", fact="A repeated route was observed."),
            EvidenceSource(source_id="obs-2", fact="The route continued into the next chunk."),
        ],
    )


def test_openai_enrichment_is_structured_and_non_authoritative():
    narrative = EvidenceNarrative(
        headline="Repeated route continued",
        factual_summary="The same visible route continued across two source chunks.",
        uncertainty=["Behavior label is a provider observation."],
        cited_source_ids=["obs-1", "obs-2"],
    )
    client = FakeOpenAI(narrative)
    result = OpenAIEvidenceEnricher(
        "unused",
        model="gpt-5.6-luna",
        client=client,
    ).merge(request())
    assert result == narrative
    assert client.responses.kwargs["text_format"] is EvidenceNarrative
    schema = EvidenceNarrative.model_json_schema()
    assert "severity" not in schema["properties"]
    assert client.responses.kwargs["store"] is False


def test_openai_enrichment_rejects_invented_source_ids():
    client = FakeOpenAI(
        EvidenceNarrative(
            headline="Observation",
            factual_summary="A route was visible.",
            uncertainty=[],
            cited_source_ids=["invented"],
        )
    )
    with pytest.raises(ValueError, match="unknown"):
        OpenAIEvidenceEnricher(
            "unused",
            model="gpt-5.6-luna",
            client=client,
        ).merge(request())


def test_morning_writer_requires_every_animal():
    morning_request = MorningReportRequest(
        shift_label="Overnight",
        animals=[
            MorningAnimalFacts(
                animal_id="animal-1",
                animal_name="Nox",
                event_facts=["Pacing lasted 21 minutes."],
                data_gap_facts=[],
                no_notable_events=False,
            ),
            MorningAnimalFacts(
                animal_id="animal-2",
                animal_name="Mara",
                event_facts=[],
                data_gap_facts=["Camera signal was absent for 18 minutes."],
                no_notable_events=True,
            ),
        ],
    )
    client = FakeOpenAI(
        MorningNarrative(
            handoff_summary="One event and one coverage gap were recorded.",
            animals=[
                MorningAnimalNarrative(
                    animal_id="animal-1",
                    summary="A repeated route was recorded.",
                )
            ],
            uncertainty=[],
        )
    )
    with pytest.raises(ValueError, match="each animal"):
        OpenAIMorningReportWriter(
            "unused",
            model="gpt-5.6-terra",
            client=client,
        ).write(morning_request)


def test_strands_agents_request_structured_outputs(monkeypatch):
    evidence = EvidenceNarrative(
        headline="Repeated route continued",
        factual_summary="The supplied evidence records the same route.",
        uncertainty=[],
        cited_source_ids=["obs-1"],
    )
    morning = MorningNarrative(
        handoff_summary="All monitored animals are represented.",
        animals=[MorningAnimalNarrative(animal_id="animal-1", summary="No notable events.")],
        uncertainty=[],
    )
    invocations = []

    class FakeAgent:
        def __init__(self, **kwargs):
            invocations.append(("init", kwargs))

        def __call__(self, prompt, *, structured_output_model):
            invocations.append(("call", structured_output_model, prompt))
            output = evidence if structured_output_model is EvidenceNarrative else morning
            return SimpleNamespace(structured_output=output)

    monkeypatch.setattr("zoovision.enrichment.Agent", FakeAgent)
    enricher = StrandsEvidenceEnricher(
        "unused",
        model="gpt-5.6-luna",
        model_provider=object(),
    )
    result = enricher.merge(
        EvidenceMergeRequest(
            event_id="evt-1",
            animal_name="Nox",
            behavior_label="pacing",
            sources=[EvidenceSource(source_id="obs-1", fact="Repeated route.")],
        )
    )
    writer = StrandsMorningReportWriter(
        "unused",
        model="gpt-5.6-terra",
        model_provider=object(),
    )
    report = writer.write(
        MorningReportRequest(
            shift_label="2026-07-30",
            animals=[
                MorningAnimalFacts(
                    animal_id="animal-1",
                    animal_name="Nox",
                    event_facts=[],
                    data_gap_facts=[],
                    no_notable_events=True,
                )
            ],
        )
    )

    assert result == evidence
    assert report == morning
    assert ("call", EvidenceNarrative) == invocations[1][:2]
    assert ("call", MorningNarrative) == invocations[3][:2]
