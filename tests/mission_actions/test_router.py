from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from portal.mission_actions import router
import importlib

module = importlib.import_module("portal.mission_actions.router")

def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

def test_auth_before_fixture(monkeypatch):
    def deny(_):
        raise HTTPException(401, "denied")
    def forbidden():
        raise AssertionError("fixture accessed before auth")
    monkeypatch.setattr(module, "_require_portal_read_auth", deny)
    monkeypatch.setattr(module, "_load_or_503", forbidden)
    assert client().get("/api/mission-actions/journey").status_code == 401
    assert client().post("/api/mission-actions/story", content="invalid").status_code == 401

def test_viewer_cannot_execute(monkeypatch):
    monkeypatch.setattr(module, "_require_portal_read_auth", lambda _: None)
    c = client()
    for command in module.BLOCKED:
        r = c.post("/api/mission-actions/commands/" + command, json={"tenant": "forged", "approved": True})
        assert r.status_code == 503
        assert r.json()["live_remediation_authorized"] is False
    assert c.post("/api/mission-actions/commands/RT10").status_code == 404

def test_session_not_actor(monkeypatch):
    monkeypatch.setattr(module, "_require_portal_read_auth", lambda _: None)
    r = client().get("/api/mission-actions/session")
    assert r.json()["tenant_acl_qualified"] is False

def test_story_delegates(monkeypatch):
    monkeypatch.setattr(module, "_require_portal_read_auth", lambda _: None)
    from fastapi.responses import JSONResponse
    monkeypatch.setattr(module, "explore_story_control",
                        lambda payload, auth: JSONResponse({"payload": payload, "auth": auth}))
    payload = {"action": "advance", "cursor": 1, "mode": "story"}
    r = client().post("/api/mission-actions/story", json=payload, headers={"Authorization": "Bearer test"})
    assert r.json() == {"payload": payload, "auth": "Bearer test"}
