import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
module = importlib.import_module("portal.mission_actions.router")

def test_gamma03_fixture_projection(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token")
    app = FastAPI()
    app.include_router(module.router)
    response = TestClient(app).get("/api/mission-actions/journey", headers={"Authorization":"Bearer viewer-test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["twin"] is not None and data["affected_ci_ids"]
    assert data["decision_preview"]["analyst"]["status"] == "HYPOTHESIS_ONLY"
    assert data["decision_preview"]["critic"]["decision"] == "HOLD_FOR_HUMAN_REVIEW"
    assert data["decision_preview"]["policy"]["decision"] == "DENY_LIVE_ACTION"
    assert data["cockpit"]["evidence_plan"]["verified_count"] == 0

def test_gamma03_glpi_status_remains_denied(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token")
    app = FastAPI()
    app.include_router(module.router)
    response = TestClient(app).get("/api/mission-actions/glpi", headers={"Authorization":"Bearer viewer-test-token"})
    assert response.status_code == 503
    assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
    assert response.json()["glpi_write_enabled"] is False
