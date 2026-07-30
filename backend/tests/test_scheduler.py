from datetime import UTC, datetime

from zoovision.scheduler import EventBridgeEscalationScheduler


class FakeScheduler:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create_schedule(self, **kwargs):
        self.created.append(kwargs)
        return {"ScheduleArn": f"arn:aws:scheduler:::schedule/{kwargs['Name']}"}

    def delete_schedule(self, **kwargs):
        self.deleted.append(kwargs)


def test_one_time_escalation_is_self_deleting_and_bounded():
    client = FakeScheduler()
    scheduler = EventBridgeEscalationScheduler(
        target_arn="arn:aws:lambda:us-east-1:123456789012:function:escalate",
        role_arn="arn:aws:iam::123456789012:role/scheduler",
        client=client,
    )

    scheduled = scheduler.schedule_alert(
        alert_id="alt:animal/1",
        event_id="evt-1",
        run_at=datetime(2026, 7, 30, 2, 20, tzinfo=UTC),
    )

    request = client.created[0]
    assert request["ActionAfterCompletion"] == "DELETE"
    assert request["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert request["ScheduleExpression"] == "at(2026-07-30T02:20:00)"
    assert request["Target"]["RetryPolicy"]["MaximumRetryAttempts"] == 2
    assert len(scheduled.name) <= 64

    scheduler.cancel(scheduled.name)
    assert client.deleted == [{"Name": scheduled.name, "GroupName": "default"}]
