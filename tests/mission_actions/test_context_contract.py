import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient

module = importlib.import_module("portal.mission_actions.router")

def test_journey_context_uses_server_fixture(monkeypatch):
    monkeypatch.setattr(module, "_require_portal_read_auth", lambda _: None)
    fixture = {"run_id": "SIM-1", "incident_id": "INC-1",
               "source_sha256": "a" * 64, "affected_ci_ids": ["ci-a"],
               "decision_preview": {"policy": "DENY"}}
    monkeypatch.setattr(module, "_load_or_503", lambda: fixture)
    monkeypatch.setattr(module, "project_synthetic_incident_cockpit", lambda _: {"mode": "DEMO"})
    app = FastAPI()
    app.include_router(module.router)
    result = TestClient(app).get("/api/mission-actions/journey?run_id=FORGED&incident_id=FORGED")
    assert result.status_code == 200
    data = result.json()
    assert data["run_id"] == "SIM-1"
    assert data["incident_id"] == "INC-1"
    assert data["affected_ci_ids"] == ["ci-a"]
    assert data["runtime_attested"] is False
    assert data["live_remediation_authorized"] is False
