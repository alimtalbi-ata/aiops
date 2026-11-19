from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import mission_data as md

def test_contract(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "test-token")
    calls = []
    def query(job, minutes):
        calls.append((job, minutes))
        return [{"at": 123, "up": 0}]
    monkeypatch.setattr(md, "query_prom", query)
    app = FastAPI()
    app.include_router(md.router)
    client = TestClient(app)
    path = "/api/mission-data/health?job=aiops2-core&mode=PLATFORM"
    headers = {"Authorization": "Bearer test-token"}
    assert client.get(path).status_code == 401
    assert not calls
    assert client.get(path.replace("PLATFORM", "DEMO"), headers=headers).status_code == 503
    assert client.get(path.replace("PLATFORM", "LIVE"), headers=headers).status_code == 503
    assert not calls
    response = client.get(path, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["points"][0]["up"] == 0
    assert response.headers["cache-control"] == "no-store"
    assert calls == [("aiops2-core", 0)]
    for name in ("core", "fs-lab", "evidence", "logs", "traces", "twin", "impact", "noc"):
        response = client.get("/api/mission-data/datasets/" + name + "?mode=LIVE", headers=headers)
        assert response.status_code == 503
        assert response.json()["data"] is None
    assert client.get(path.replace("aiops2-core", "arbitrary"), headers=headers).status_code == 422
    monkeypatch.setattr(md, "query_prom", lambda *args: [])
    assert client.get(path, headers=headers).json()["reason"] == "NO_SAMPLES"
