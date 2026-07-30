from datetime import UTC, datetime, timedelta

from zoovision.alerts import AlertDeliveryContext, delivery_gate, slack_payload
from zoovision.domain import (
    AlertAction,
    BaselineState,
    Behavior,
    EventRecord,
    Severity,
    ShiftMode,
)


def event(*, shift_mode=ShiftMode.NIGHT):
    start = datetime(2026, 7, 30, 2, tzinfo=UTC)
    return EventRecord(
        event_id="evt-1",
        animal_id="animal-1",
        enclosure_id="ENC-01",
        behavior=Behavior.PACING,
        start_ts=start,
        end_ts=start + timedelta(minutes=21),
        severity=Severity.HIGH,
        rule_fired="R004_PACING_20M_NO_WATER_6H",
        action=AlertAction.VERIFY_WATER,
        confidence=0.9,
        source_observation_ids=["obs-1"],
        explanation_facts=[
            "Continuous pacing lasted 21.0 minutes.",
            "No water contact was observed for 6.5 hours.",
        ],
        rule_version="2026-07-30.v1",
        shift_mode=shift_mode,
        created_at=start,
    )


def active_context(**overrides):
    values = {
        "fixture_mode": False,
        "delivery_enabled": True,
        "webhook_configured": True,
        "baseline_state": BaselineState.ACTIVE,
    }
    values.update(overrides)
    return AlertDeliveryContext(**values)


def test_alert_requires_night_active_baseline_and_explicit_delivery():
    assert delivery_gate(event(), active_context()).allowed
    assert not delivery_gate(event(shift_mode=ShiftMode.DAY), active_context()).allowed
    assert not delivery_gate(event(), active_context(fixture_mode=True)).allowed
    assert not delivery_gate(
        event(),
        active_context(baseline_state=BaselineState.SHADOW),
    ).allowed
    assert not delivery_gate(
        event(),
        active_context(delivery_enabled=False),
    ).allowed


def test_slack_payload_is_factual_and_constrained():
    payload = slack_payload(
        event(),
        animal_name="Nox",
        evidence_url="https://console.example/events/evt-1",
    )
    rendered = str(payload)
    assert "R004_PACING_20M_NO_WATER_6H" in rendered
    assert "Review evidence" in rendered
    assert "diagnos" not in rendered.lower()
    assert "medication" not in rendered.lower()
