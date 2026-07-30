from types import SimpleNamespace

from zoovision import agentcore_app


class FakeStore:
    def __init__(self, state="pending"):
        self.state = state

    def alert_state(self, alert_id):
        assert alert_id == "alt-1"
        return self.state

    def escalate_pending_alert(self, alert_id):
        if self.state != "pending":
            return False
        self.state = "escalated"
        return True


class FakeWorkflow:
    def run(self, request):
        return SimpleNamespace(model_dump=lambda **_kwargs: {"route": request.shift_mode.value})


def test_agentcore_entrypoint_escalates_only_pending_alerts(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(
        agentcore_app,
        "_runtime",
        lambda: (object(), store, FakeWorkflow()),
    )

    first = agentcore_app.invoke(
        {
            "operation": "escalate_unacknowledged",
            "alert_id": "alt-1",
            "event_id": "evt-1",
        }
    )
    second = agentcore_app.invoke(
        {
            "operation": "escalate_unacknowledged",
            "alert_id": "alt-1",
            "event_id": "evt-1",
        }
    )

    assert first["status"] == "escalated"
    assert second["status"] == "no_action"
