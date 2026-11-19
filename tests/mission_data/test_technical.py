import json
from portal import mission_data as md
from portal.mission_data import technical as t

def test_technical(monkeypatch):
    monkeypatch.setattr(t.time,"time",lambda:6000)
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,size):
            return json.dumps({"status":"success","data":{"resultType":"matrix","result":[
                {"metric":{"job":"aiops2-core"},"values":[[5880,"0"],[6000,"0.25"]]}
            ]}}).encode()
    class Opener:
        def open(self,url,timeout):
            assert "scrape_duration_seconds" in url
            return Response()
    monkeypatch.setattr(t.urllib.request,"build_opener",lambda *args:Opener())
    d=t.technical_series(md.JOBS,md.PROM,md.NoRedirect,"scrape-duration",2)
    assert d["series"][0]["points"]==[{"at":5880,"value":0},{"at":5940,"value":None},{"at":6000,"value":0.25}]
    assert d["series"][-1]["coverage"]==0
    assert d["unit"]=="seconds"
