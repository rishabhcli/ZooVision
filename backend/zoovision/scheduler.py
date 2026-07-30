from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import boto3
from pydantic import BaseModel, ConfigDict, Field


class ScheduledEscalation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arn: str
    run_at: datetime


class EventBridgeEscalationScheduler:
    def __init__(
        self,
        *,
        target_arn: str,
        role_arn: str,
        group_name: str = "default",
        region: str = "us-east-1",
        client: Any | None = None,
    ):
        self.target_arn = target_arn
        self.role_arn = role_arn
        self.group_name = group_name
        self.client = client or boto3.client("scheduler", region_name=region)

    def schedule_alert(
        self,
        *,
        alert_id: str,
        event_id: str,
        run_at: datetime,
    ) -> ScheduledEscalation:
        if run_at.tzinfo is None:
            raise ValueError("escalation time must be timezone-aware")
        utc_run_at = run_at.astimezone(UTC).replace(microsecond=0)
        name = _schedule_name(alert_id)
        response = self.client.create_schedule(
            Name=name,
            GroupName=self.group_name,
            Description=f"ZooVision acknowledgement check for {alert_id}",
            ScheduleExpression=f"at({utc_run_at.strftime('%Y-%m-%dT%H:%M:%S')})",
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            ActionAfterCompletion="DELETE",
            State="ENABLED",
            Target={
                "Arn": self.target_arn,
                "RoleArn": self.role_arn,
                "Input": json.dumps(
                    {
                        "operation": "escalate_unacknowledged",
                        "alert_id": alert_id,
                        "event_id": event_id,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "RetryPolicy": {
                    "MaximumEventAgeInSeconds": 900,
                    "MaximumRetryAttempts": 2,
                },
            },
        )
        return ScheduledEscalation(
            name=name,
            arn=response["ScheduleArn"],
            run_at=utc_run_at,
        )

    def cancel(self, name: str) -> None:
        self.client.delete_schedule(Name=name, GroupName=self.group_name)


def _schedule_name(alert_id: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "-_." else "-" for character in alert_id)
    return f"zv-{normalized}"[:64]
