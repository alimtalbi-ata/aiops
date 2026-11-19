import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
module = importlib.import_module("portal.mission_actions.router")

def client():
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)

def test_viewer_cannot_simulate(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token")
    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", "operator-test-token")
    monkeypatch.delenv("AIOPS_INTERNAL_TOKEN", raising=False)
    def forbidden():
        raise AssertionError("pipeline must not execute")
    monkeypatch.setattr(module, "run_acme_demo_simulation", forbidden)
    assert client().post("/api/mission-actions/demo/simulation", json={}, headers={"Authorization":"Bearer viewer-test-token"}).status_code == 401

def test_context_mismatch_before_simulation(monkeypatch):
    monkeypatch.setattr(module, "require_demo_operator", lambda _: None)
    monkeypatch.setattr(module, "_load_or_503", lambda: {"incident_id":"I", "run_id":"R", "source_sha256":"a"*64})
    def forbidden():
        raise AssertionError("pipeline must not execute")
    monkeypatch.setattr(module, "run_acme_demo_simulation", forbidden)
    response = client().post("/api/mission-actions/demo/simulation", json={"incident_id":"I","run_id":"OTHER","source_sha256":"a"*64})
    assert response.status_code == 409

def test_real_offline_pipeline(monkeypatch):
    monkeypatch.setattr(module, "require_demo_operator", lambda _: None)
    impact = module._load_or_503()
    response = client().post("/api/mission-actions/demo/simulation", json={k:impact[k] for k in ("incident_id","run_id","source_sha256")})
    assert response.status_code == 200
    data = response.json()
    assert data["simulation"]["receipt"]["simulation_result"] == "HYPOTHETICAL_ONLY"
    assert data["actual_recovery_state"] == "UNKNOWN"
    assert data["runtime_execution_performed"] is False
    assert data["live_remediation_authorized"] is False
