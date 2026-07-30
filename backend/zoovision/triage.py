from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .domain import AlertAction, Behavior, Severity, TriageDecision, TriageInput

RULE_VERSION = "2026-07-30.v1"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    action: AlertAction
    predicate: Callable[[TriageInput], bool]
    facts: Callable[[TriageInput], list[str]]


RULES = (
    Rule(
        "R001_FIGHTING",
        Severity.CRITICAL,
        AlertAction.WELFARE_CHECK,
        lambda value: value.behavior is Behavior.FIGHTING,
        lambda _: ["Fighting was observed."],
    ),
    Rule(
        "R002_ESCAPE_ATTEMPT",
        Severity.CRITICAL,
        AlertAction.WELFARE_CHECK,
        lambda value: value.behavior is Behavior.ESCAPE_ATTEMPT,
        lambda _: ["An escape attempt was observed."],
    ),
    Rule(
        "R003_VOMITING",
        Severity.HIGH,
        AlertAction.WELFARE_CHECK,
        lambda value: value.behavior is Behavior.VOMITING,
        lambda _: ["Vomiting was observed."],
    ),
    Rule(
        "R004_PACING_20M_NO_WATER_6H",
        Severity.HIGH,
        AlertAction.VERIFY_WATER,
        lambda value: (
            value.behavior is Behavior.PACING
            and value.continuous_duration_minutes > 20
            and value.hours_since_water_contact is not None
            and value.hours_since_water_contact >= 6
        ),
        lambda value: [
            f"Continuous pacing lasted {value.continuous_duration_minutes:.1f} minutes.",
            f"No water contact was observed for {value.hours_since_water_contact:.1f} hours.",
        ],
    ),
    Rule(
        "R005_PACING_10M",
        Severity.MODERATE,
        AlertAction.OBSERVE,
        lambda value: value.behavior is Behavior.PACING and value.continuous_duration_minutes > 10,
        lambda value: [
            f"Continuous pacing lasted {value.continuous_duration_minutes:.1f} minutes."
        ],
    ),
    Rule(
        "R006_INACTIVITY_2SD",
        Severity.MODERATE,
        AlertAction.OBSERVE,
        lambda value: (
            value.behavior is Behavior.INACTIVITY
            and value.inactivity_z is not None
            and value.inactivity_z > 2
        ),
        lambda value: [f"Inactivity measured {value.inactivity_z:.1f} standard deviations."],
    ),
    Rule(
        "R007_BASELINE_DELTA_2_5",
        Severity.MODERATE,
        AlertAction.OBSERVE,
        lambda value: value.baseline_delta_z is not None and value.baseline_delta_z > 2.5,
        lambda value: [
            f"Behavior measured {value.baseline_delta_z:.1f} standard deviations above baseline."
        ],
    ),
    Rule(
        "R008_WATER_BOWL_TIPPED",
        Severity.LOW,
        AlertAction.VERIFY_WATER,
        lambda value: value.behavior is Behavior.WATER_BOWL_TIPPED,
        lambda _: ["A tipped water bowl was observed."],
    ),
)


def classify(value: TriageInput) -> TriageDecision:
    if not value.evidence_sufficient:
        return TriageDecision(
            severity=Severity.NONE,
            rule_fired=None,
            action=None,
            explanation_facts=["Evidence was insufficient for deterministic triage."],
            rule_version=RULE_VERSION,
        )

    for rule in RULES:
        if rule.predicate(value):
            return TriageDecision(
                severity=rule.severity,
                rule_fired=rule.rule_id,
                action=rule.action,
                explanation_facts=rule.facts(value),
                rule_version=RULE_VERSION,
            )

    return TriageDecision(
        severity=Severity.NONE,
        rule_fired=None,
        action=None,
        explanation_facts=["No deterministic triage rule matched."],
        rule_version=RULE_VERSION,
    )
