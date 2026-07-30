from zoovision.domain import Behavior, Severity, TriageInput
from zoovision.triage import classify


def make_input(**overrides) -> TriageInput:
    values = {
        "animal_id": "animal-rex",
        "behavior": Behavior.OTHER,
        "continuous_duration_minutes": 0,
        "source_observation_ids": ["obs-1"],
    }
    values.update(overrides)
    return TriageInput(**values)


def test_first_match_precedence_keeps_fighting_critical():
    result = classify(
        make_input(
            behavior=Behavior.FIGHTING,
            continuous_duration_minutes=30,
            baseline_delta_z=4,
        )
    )
    assert result.severity is Severity.CRITICAL
    assert result.rule_fired == "R001_FIGHTING"


def test_pacing_with_no_water_is_high_only_above_twenty_minutes():
    at_boundary = classify(
        make_input(
            behavior=Behavior.PACING,
            continuous_duration_minutes=20,
            hours_since_water_contact=6,
        )
    )
    above_boundary = classify(
        make_input(
            behavior=Behavior.PACING,
            continuous_duration_minutes=20.01,
            hours_since_water_contact=6,
        )
    )
    assert at_boundary.severity is Severity.MODERATE
    assert at_boundary.rule_fired == "R005_PACING_10M"
    assert above_boundary.severity is Severity.HIGH
    assert above_boundary.rule_fired == "R004_PACING_20M_NO_WATER_6H"


def test_pacing_ten_minute_boundary_is_not_moderate():
    result = classify(make_input(behavior=Behavior.PACING, continuous_duration_minutes=10))
    assert result.severity is Severity.NONE


def test_inactivity_and_baseline_boundaries_are_strict():
    inactivity = classify(make_input(behavior=Behavior.INACTIVITY, inactivity_z=2))
    baseline = classify(make_input(baseline_delta_z=2.5))
    assert inactivity.severity is Severity.NONE
    assert baseline.severity is Severity.NONE


def test_tipped_water_bowl_is_low():
    result = classify(make_input(behavior=Behavior.WATER_BOWL_TIPPED))
    assert result.severity is Severity.LOW
    assert result.rule_fired == "R008_WATER_BOWL_TIPPED"


def test_insufficient_evidence_never_pages():
    result = classify(make_input(behavior=Behavior.VOMITING, evidence_sufficient=False))
    assert result.severity is Severity.NONE
    assert result.rule_fired is None
