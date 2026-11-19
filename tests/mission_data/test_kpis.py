import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal import mission_data as md
from portal.mission_data import kpis as k

def test_authorization(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN","viewer")
    monkeypatch.delenv("AIOPS_MISSION_AGGREGATE_GROUPS",raising=False)
    calls=[]
    monkeypatch.setattr(k,"read_kpis",lambda *args: calls.append(args) or {})
    app=FastAPI()
    app.include_router(md.router)
    client=TestClient(app)
    url="/api/mission-data/kpis/core"
    headers={"Authorization":"Bearer viewer"}
    assert client.get(url).status_code==401
    assert client.get(url,headers=headers).status_code==503
    assert calls==[]
    monkeypatch.setenv("AIOPS_MISSION_AGGREGATE_GROUPS","core")
    assert client.get(url,headers=headers).status_code==200
    assert len(calls)==1
    assert client.get("/api/mission-data/kpis/evidence",headers=headers).status_code==503
    assert len(calls)==1

def test_history(monkeypatch):
    monkeypatch.setattr(k.time,"time",lambda:6000)
    rows=[
        {"metric":{"__name__":"aiops_runs_total"},"values":[[5880,"7"],[6000,"8"]]},
        {"metric":{"__name__":"aiops_runs_running"},"values":[[6000,"0"]]},
        {"metric":{"__name__":"aiops_runs_blocked"},"values":[[6000,"2"]]},
        {"metric":{"__name__":"aiops_runs_blocked"},"values":[[6000,"3"]]},
    ]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,size):
            return json.dumps({"status":"success","data":{"resultType":"matrix","result":rows}}).encode()
    class Opener:
        def open(self,url,timeout): return Response()
    monkeypatch.setattr(k.urllib.request,"build_opener",lambda *args:Opener())
    d=k.read_kpis("core",md.PROM,md.NoRedirect,2)
    a,b,c,e=d["series"]
    assert a["value"]==8 and a["points"][1]["value"] is None
    assert b["value"]==0
    assert c["reason"]=="AMBIGUOUS_SERIES" and c["value"] is None
    assert e["reason"]=="NO_CURRENT_SAMPLE" and e["coverage"]==0
    assert d["coverage"]==3/12

def test_portal_catalog_and_history(monkeypatch):
    assert k.CATALOG["services"] == ("aiops_worker_up","aiops_policy_up","aiops_portal_up")
    monkeypatch.setattr(k.time,"time",lambda:6000)
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,size):
            return json.dumps({"status":"success","data":{"resultType":"matrix","result":[
                {"metric":{"__name__":"aiops_portal_up"},"values":[[6000,"1"]]}
            ]}}).encode()
    class Opener:
        def open(self,url,timeout):
            assert "aiops_portal_up" in url
            return Response()
    monkeypatch.setattr(k.urllib.request,"build_opener",lambda *args:Opener())
    d=k.read_kpis("services",md.PROM,md.NoRedirect,1)
    portal=d["series"][2]
    assert portal["value"]==1 and portal["unit"]=="binary"
    assert portal["points"]==[{"at":5940,"value":None},{"at":6000,"value":1}]
    assert d["series"][0]["value"] is None
    assert d["coverage"]==1/6

def test_default_deny_all_groups(monkeypatch):
    monkeypatch.setenv("AIOPS_PORTAL_READ_TOKEN","viewer")
    monkeypatch.setenv("AIOPS_MISSION_AGGREGATE_GROUPS","*")
    def forbidden(*args):
        raise AssertionError("upstream must not be reached")
    monkeypatch.setattr(k,"read_kpis",forbidden)
    app=FastAPI()
    app.include_router(md.router)
    client=TestClient(app)
    headers={"Authorization":"Bearer viewer"}
    for group in k.CATALOG:
        response=client.get("/api/mission-data/kpis/"+group,headers=headers)
        assert response.status_code==503
        assert response.json()["reason"]=="AGGREGATE_AUTHORIZATION_NOT_QUALIFIED"
    assert client.get("/api/mission-data/kpis/other",headers=headers).status_code==422
    assert client.get("/api/mission-data/kpis/core?minutes=1441",headers=headers).status_code==422

def test_provider_modules_are_not_shadowed():
    from portal.mission_data import acme, technical
    assert callable(acme.project_acme)
    assert callable(technical.technical_series)
    assert callable(k.read_kpis)
