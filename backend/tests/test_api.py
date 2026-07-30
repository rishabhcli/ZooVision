import pytest
from fastapi.testclient import TestClient
from zoovision.api import create_app
from zoovision.settings import Settings
from zoovision.store import SQLiteStore


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        ZOOVISION_STORAGE_ROOT=tmp_path,
        ZOOVISION_FIXTURE_MODE=True,
        _env_file=None,
    )
    store = SQLiteStore(tmp_path / "zoovision.db")
    return TestClient(create_app(settings, store))


def test_dashboard_preserves_deterministic_evidence(client):
    client.post("/api/demo/reset")
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert len(body["animals"]) == 3
    event = next(item for item in body["events"] if item["severity"] == "HIGH")
    assert event["rule_fired"] == "R004_PACING_20M_NO_WATER_6H"
    assert event["evidence_kind"] == "synthetic_scenario"
    assert event["delivery_status"] == "shadowed"


def test_readiness_does_not_claim_external_providers_are_healthy(client):
    body = client.get("/api/readiness").json()
    assert body["status"] == "ready"
    assert body["external_delivery_ready"] is False
    assert body["providers"]["openai"]["status"] in {
        "not_configured",
        "configured_disabled",
    }
    assert all("healthy" not in provider for provider in body["providers"].values())


def test_acknowledgement_is_persisted_and_not_repeatable(client):
    client.post("/api/demo/reset")
    event = client.get("/api/dashboard").json()["events"][0]
    path = f"/api/alerts/{event['alert_id']}/ack"
    assert client.post(path, json={"keeper": "Avery"}).status_code == 200
    assert client.post(path, json={"keeper": "Avery"}).status_code == 409


def test_morning_report_includes_quiet_animals_and_gaps(client):
    client.post("/api/demo/reset")
    report = client.get("/api/morning-report").json()
    assert report["summary"] == {
        "animals_monitored": 3,
        "events": 2,
        "data_gaps": 1,
    }
    assert any(animal["events"] == [] for animal in report["animals"])


def test_baseline_activation_requires_shadow_and_enough_day_shifts(client):
    client.post("/api/demo/reset")
    assert (
        client.post("/api/animals/animal-nox/baseline", json={"state": "active"}).status_code == 200
    )
    assert (
        client.post("/api/animals/animal-juniper/baseline", json={"state": "active"}).status_code
        == 409
    )
