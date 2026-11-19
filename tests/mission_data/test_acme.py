from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import mission_data as md
from portal.mission_data import acme

def test_acme_contract(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "test-viewer")
    original = acme.project_acme
    calls = []
    def project():
        calls.append(True)
        return original()
    monkeypatch.setattr(acme, "project_acme", project)
    app = FastAPI()
    app.include_router(md.router)
    client = TestClient(app)
    path = "/api/mission-data/acme?mode="
    headers = {"Authorization":"Bearer test-viewer"}
    assert client.get(path+"DEMO").status_code == 401
    assert client.get(path+"LIVE", headers=headers).status_code == 503
    assert not calls
    response = client.get(path+"DEMO", headers=headers)
    assert response.status_code == 200
    d = response.json()["data"]
    assert d["classification"] == "SYNTHETIC_SIMULATION_ONLY"
    assert d["kpis"]["ci_count"] == len(d["graph"]["nodes"])
    assert d["kpis"]["runtime_open_incidents"] is None
    assert all(n["health"] is None for n in d["graph"]["nodes"])
    assert all(h["observed_at"] is None for h in d["history"])
    assert d["runtime_attested"] is False
    assert calls == [True]
    def broken():
        raise ValueError("invalid source")
    monkeypatch.setattr(acme, "project_acme", broken)
    response = client.get(path+"DEMO", headers=headers)
    assert response.status_code == 503
    assert response.json()["data"] is None
