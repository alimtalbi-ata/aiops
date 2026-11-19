import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import mission_data as md
from portal.mission_data import history as h

def test_history(monkeypatch):
    monkeypatch.setattr(h.time, "time", lambda: 6000)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            return json.dumps({"status":"success","data":{"resultType":"matrix","result":[
                {"metric":{"job":"aiops2-core"},"values":[[5880,"1"],[6000,"0"]]}
            ]}}).encode()
    class Opener:
        def open(self, url, timeout): return Response()
    monkeypatch.setattr(h.urllib.request,"build_opener",lambda *args: Opener())
    d = h.history(md.JOBS, md.PROM, md.NoRedirect, 2)
    assert d["series"][0]["points"] == [{"at":5880,"up":1},{"at":5940,"up":None},{"at":6000,"up":0}]
    assert d["series"][-1]["coverage"] == 0
    assert d["coverage"] == 2/18

def test_scrape():
    app = FastAPI()
    app.include_router(md.router)
    response = TestClient(app).get("/api/mission-data/metrics")
    assert response.status_code == 200
    assert response.text == "# TYPE aiops_portal_up gauge\naiops_portal_up 1\n"
    assert response.headers["content-type"].startswith("text/plain")
