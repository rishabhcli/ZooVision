from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from .domain import BaselineState, EventRecord, Severity, ShiftMode


class AlertDeliveryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture_mode: bool
    delivery_enabled: bool
    webhook_configured: bool
    baseline_state: BaselineState


class AlertGateDecision(BaseModel):
    allowed: bool
    reasons: list[str]


def delivery_gate(event: EventRecord, context: AlertDeliveryContext) -> AlertGateDecision:
    reasons = []
    if event.severity is Severity.NONE:
        reasons.append("severity_none")
    if event.shift_mode is not ShiftMode.NIGHT:
        reasons.append("day_shift_never_pages")
    if not event.rule_fired:
        reasons.append("missing_deterministic_rule")
    if context.baseline_state is not BaselineState.ACTIVE:
        reasons.append("baseline_not_human_activated")
    if context.fixture_mode:
        reasons.append("fixture_mode")
    if not context.delivery_enabled:
        reasons.append("delivery_disabled")
    if not context.webhook_configured:
        reasons.append("webhook_not_configured")
    return AlertGateDecision(allowed=not reasons, reasons=reasons)


def slack_payload(
    event: EventRecord,
    *,
    animal_name: str,
    evidence_url: str,
) -> dict[str, Any]:
    facts = "\n".join(f"• {fact}" for fact in event.explanation_facts)
    return {
        "text": f"ZooVision {event.severity.value}: {animal_name}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{event.severity.value} · {animal_name}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Observed:* {event.behavior.value.replace('_', ' ')}\n"
                        f"*Rule:* `{event.rule_fired}`\n{facts}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Review evidence"},
                        "url": evidence_url,
                        "action_id": "review_evidence",
                    }
                ],
            },
        ],
    }


class SlackNotifier:
    def __init__(self, webhook_url: str, *, client: httpx.Client | None = None):
        self.webhook_url = webhook_url
        self.client = client or httpx.Client(timeout=10)

    def send(self, payload: dict[str, Any]) -> None:
        response = self.client.post(self.webhook_url, json=payload)
        response.raise_for_status()
