import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import mission_data as md

def test_jobs(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN", "test-viewer")
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            return json.dumps({"status":"success","data":{"resultType":"vector","result":[
                {"metric":{"job":job},"value":[md.time.time(),"1"]}
                for job in md.JOBS if job != "aiops2-portal"]}}).encode()
    class Opener:
        def open(self, url, timeout):
            calls.append(url)
            return Response()
    monkeypatch.setattr(md.urllib.request, "build_opener", lambda *args: Opener())
    app = FastAPI()
    app.include_router(md.router)
    client = TestClient(app)
    path = "/api/mission-data/health/jobs"
    assert client.get(path).status_code == 401
    assert not calls
    response = client.get(path, headers={"Authorization":"Bearer test-viewer"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["counts"] == {"UP":5,"DOWN":0,"UNKNOWN":1}
    assert data["items"][-1] == {"job":"aiops2-portal","status":"UNKNOWN","at":None,"reason":"NO_SAMPLES"}
    assert len(calls) == 1
