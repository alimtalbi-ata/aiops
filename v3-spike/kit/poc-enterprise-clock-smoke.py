"""Exercise E2 against the real isolated GAMMA launcher before and after restart."""
import json
import re
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def smoke(origin, restart):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) or int(origin.rsplit(":",1)[1]) in (7770,7777,7790):
        raise ValueError("isolated origin required")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def call(path,data=None):
        req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),
                    headers={"Origin":origin,"Content-Type":"application/json"})
        with opener.open(req,timeout=30) as response:
            return json.load(response)
    status=lambda:call("/api/v1/enterprise-clock")
    advance=lambda n:call("/api/v1/enterprise-clock/advance",{"expected_tick":n})
    capture=lambda n:call("/api/v1/enterprise-clock/capture",{"expected_tick":n})
    initial=status()
    assert initial["current_tick"]==(4 if restart else 0)
    assert initial["pending"] is False and initial["production_authorized"] is False
    first=initial["recent"][2]["publication"]["run_id"] if restart else None
    old_capture=initial["recent"][2]["measured_capture"] if restart else None
    for n in (range(5,9) if restart else range(1,5)):
        step=advance(n)
        assert step==advance(n) and step["tick"]==n
        assert step["measurement_kind"]=="MODEL_GENERATED"
        assert step["production_authorized"] is False and step["operational_decision"]=="DENY"
        if n%4==3:
            pub=step["publication"]
            assert pub["state"]=="PUBLISHED" and len(pub["evidence"])==4
            if restart: assert pub["run_id"]!=first
            else: first=pub["run_id"]
            ctx=call("/api/v1/enterprise-context?run_id="+pub["run_id"])
            assert ctx["reported_user_ids"]==["NODE-CI-ENT-USER-FIN-01"]
            assert {x["evidence_id"]:x["payload_hash"] for x in ctx["timeline"]}=={x["evidence_id"]:x["payload_hash"] for x in pub["evidence"]}
            assert all(x["source"].endswith(":enterprise-clock-e2") for x in ctx["timeline"])
            assert ctx["causality_established"] is False
            measured=capture(n)
            assert measured==capture(n) and measured["state"]=="PUBLISHED"
            assert re.fullmatch(r"[a-f0-9]{64}",measured["batch_sha256"])
            assert {x["resource"] for x in measured["incidents"]}=={"NODE-CI-ROOT","NODE-CI-ENT-ASSET-LYO"}
            assert len({x["run_id"] for x in measured["incidents"]}|{pub["run_id"]})==3
            for item in measured["incidents"]:
                observed=call("/api/v1/enterprise-context?run_id="+item["run_id"])
                assert observed["root"]==item["resource"]
                assert len([x for x in observed["timeline"] if x.get("measurement",{}).get("classification")=="MEASURED_SYNTHETIC_LAB"])==2
            if restart:
                assert not {x["run_id"] for x in measured["incidents"]}&{x["run_id"] for x in old_capture["incidents"]}
            assert status()["latest"]["measured_capture"]==measured
        else:
            assert step["publication"]["state"]=="MODEL_ONLY"
    end=status()
    assert end["current_tick"]==(8 if restart else 4)
    assert [x["phase"] for x in end["recent"]]==["NOMINAL","CHANGE","DEGRADED","MODEL_RECOVERY"]*(2 if restart else 1)
    if restart:
        old=call("/api/v1/enterprise-context?run_id="+first)
        assert old["run_id"]==first and len(old["timeline"])==4
        assert end["recent"][2]["measured_capture"]==old_capture
        for item in old_capture["incidents"]:
            assert call("/api/v1/enterprise-context?run_id="+item["run_id"])["root"]==item["resource"]
    try: advance(end["current_tick"]+2)
    except HTTPError as exc: assert exc.code==503
    else: raise AssertionError("skipped tick accepted")
    print(json.dumps({"classification":"E2_CLOCK_RESTART" if restart else "E2_CLOCK_FIRST_CYCLE","result":"PASS","current_tick":end["current_tick"],"published_run_ids":[x["publication"]["run_id"] for x in end["recent"] if x["publication"]["state"]=="PUBLISHED"],"measured_run_ids":[item["run_id"] for x in end["recent"] for item in x.get("measured_capture",{}).get("incidents",[])],"production_authorized":False}))

if __name__=="__main__":
    if len(sys.argv) not in (2,3) or (len(sys.argv)==3 and sys.argv[2]!="--restart"):
        raise SystemExit("usage: poc-enterprise-clock-smoke.py ORIGIN [--restart]")
    smoke(sys.argv[1],len(sys.argv)==3)
