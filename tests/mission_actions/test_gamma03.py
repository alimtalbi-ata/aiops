import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient
module = importlib.import_module("portal.mission_actions.router")

def test_gamma03_fixture_projection(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token-000000000000000000")
    app = FastAPI()
    app.include_router(module.router)
    response = TestClient(app).get("/api/mission-actions/journey", headers={"Authorization":"Bearer viewer-test-token-000000000000000000"})
    assert response.status_code == 200
    data = response.json()
    assert data["twin"] is not None and data["affected_ci_ids"]
    assert data["decision_preview"]["analyst"]["status"] == "HYPOTHESIS_ONLY"
    assert data["decision_preview"]["critic"]["decision"] == "HOLD_FOR_HUMAN_REVIEW"
    assert data["decision_preview"]["policy"]["decision"] == "DENY_LIVE_ACTION"
    assert data["cockpit"]["evidence_plan"]["verified_count"] == 0

def test_gamma03_glpi_status_remains_denied(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token-000000000000000000")
    app = FastAPI()
    app.include_router(module.router)
    response = TestClient(app).get("/api/mission-actions/glpi", headers={"Authorization":"Bearer viewer-test-token-000000000000000000"})
    assert response.status_code == 503
    assert response.json()["reason"] == "TENANT_ACL_NOT_QUALIFIED"
    assert response.json()["glpi_write_enabled"] is False

def test_operator_capability_does_not_grant_tenant_acl(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "viewer-test-token-000000000000000000")
    monkeypatch.setenv("AIOPS_PORTAL_OPERATOR_TOKEN", "operator-test-token-000000000000000000")
    monkeypatch.delenv("AIOPS_INTERNAL_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)
    path = "/api/mission-actions/session/operator"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization":"Bearer viewer-test-token-000000000000000000"}).status_code == 401
    response = client.get(path, headers={"Authorization":"Bearer operator-test-token-000000000000000000"})
    assert response.status_code == 200
    assert response.json()["simulation_authorized"] is True
    assert response.json()["tenant_acl_qualified"] is False
    assert response.json()["live_remediation_authorized"] is False


def test_operator_unconfigured_fails_closed(monkeypatch):
    monkeypatch.delenv("AIOPS_PORTAL_OPERATOR_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(module.router)
    response = TestClient(app).get("/api/mission-actions/session/operator")
    assert response.status_code == 503
    assert response.json()["detail"] == "portal_operator_not_configured"
    assert response.headers["cache-control"] == "no-store"
