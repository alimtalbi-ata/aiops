"""Real HTTP measurements and actual GAMMA admission; disposable CI only."""
import contextlib
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import re
import runpy
import statistics
import sys
import threading
import time
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from urllib.error import HTTPError
import uuid

def require(ok,msg):
    if not ok: raise AssertionError(msg)

origin,mode=sys.argv[1:]
require(os.environ.get("GITHUB_ACTIONS")=="true" and os.getuid()!=0,"disposable CI required")
require(os.environ.get("V3_ROOT")=="/tmp/aiops-v3-rootless-ci","dedicated lab required")
require(re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) is not None,"loopback required")
require(1024<=int(origin.rsplit(":",1)[1])<=65535 and int(origin.rsplit(":",1)[1]) not in (7770,7777,7790),"protected port")
require(mode in ("controls","fault"),"unknown mode")
fixture=runpy.run_path(str(Path(__file__).with_name("poc-multiasset-observed.py")))
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
opener=build_opener(ProxyHandler({}),NoRedirect())
def call(path,body=None):
    raw=None if body is None else json.dumps(body,separators=(",",":")).encode()
    require(raw is None or len(raw)<=4096,"oversized batch")
    req=Request(origin+path,data=raw,headers={"Origin":origin,"Content-Type":"application/json"})
    with opener.open(req,timeout=30) as response:
        payload=response.read(65537)
        require(len(payload)<=65536 and response.headers["Cache-Control"]=="no-store","invalid response")
        return json.loads(payload)

def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def batch(fault):
    with fixture["HTTPServer"](("127.0.0.1",0),fixture["App"]) as app:
        require(app.server_port not in (7770,7777,7790),"protected port")
        app.delay=.01
        app.records=[]
        thread=threading.Thread(target=app.serve_forever)
        thread.start()
        try:
            before=fixture["measure"](app)
            baseline_at=stamp()
            time.sleep(1.05)
            app.delay=.12 if fault else .01
            after=fixture["measure"](app)
            incident_at=stamp()
            require(len(app.records)==10 and all(x["status"]==200 for x in app.records),"unexpected HTTP observations")
        finally:
            app.shutdown()
            thread.join(3)
            require(not thread.is_alive(),"target leaked")
    require(baseline_at<incident_at,"timestamps not ordered")
    identity=uuid.uuid4().hex
    common=dict(resource="NODE-CI-ROOT",source="admission-measured-ci",tenant="synthetic-demo",synthetic=True,severity="warning")
    scope=dict(asset_id="NODE-CI-ENT-ASSET-PAR",application_id="NODE-CI-ENT-APP-PAY")
    rows=[dict(common,id=identity+"-"+phase,kind="metric",enterprise=dict(scope,occurred_at=at,
             measurement=dict(classification="MEASURED_SYNTHETIC_LAB",method="HTTP_MONOTONIC_MEDIAN_5",samples_ms=samples)),
             observation=dict(metric="latency_ms",phase=phase,value=round(statistics.median(samples),3)))
          for phase,samples,at in (("baseline",before,baseline_at),("incident",after,incident_at))]
    rows.append(dict(common,id=identity+"-log",kind="log",enterprise=dict(scope,occurred_at=incident_at,message="Five actual HTTP requests returned status 200")))
    return rows

def admission(rows,expected):
    result=call("/api/v1/ingest/admit",rows)
    d=result["admission"]
    require(d["classification"]=="SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1" and d["disposition"]==expected
            and d["production_authorized"] is False and result["production_authorized"] is False
            and d["root_cause"]=="UNKNOWN" and d["operational_decision"]=="DENY","wrong admission disposition")
    require(d["admitted"]==(expected=="MEASURED_INCIDENT_CANDIDATE"),"wrong admission flag")
    require((result["publication"] is not None)==d["admitted"],"unexpected publication")
    return result

if mode=="controls":
    from copy import deepcopy
    healthy=batch(False)
    degraded=batch(True)
    ambiguous=deepcopy(degraded)
    ambiguous[1]["enterprise"]["occurred_at"]=ambiguous[0]["enterprise"]["occurred_at"]
    stale=deepcopy(degraded)
    for row in stale:
        row["enterprise"]["occurred_at"]=(datetime.strptime(row["enterprise"]["occurred_at"],"%Y-%m-%dT%H:%M:%SZ")-timedelta(seconds=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases=[(healthy,"NOMINAL_OBSERVATION"),(degraded[1:],"INSUFFICIENT_EVIDENCE"),
           (ambiguous,"AMBIGUOUS_EVIDENCE"),(stale,"STALE_OR_FUTURE_EVIDENCE"),(degraded[:2],"INSUFFICIENT_EVIDENCE")]
    dispositions=[admission(rows,expected)["admission"]["disposition"] for rows,expected in cases]
    try: call("/api/v1/ingest/admit",[dict(degraded[0],tenant="foreign")])
    except HTTPError as exc: require(exc.code==503 and json.load(exc)["policy"]=="DENY","wrong foreign rejection")
    else: raise AssertionError("foreign tenant accepted")
    print(json.dumps({"classification":"V3_ADMISSION_CONTROLS","result":"PASS","dispositions":dispositions,"foreign_rejected":True,"production_authorized":False},sort_keys=True))
else:
    rows=batch(True)
    result=admission(rows+rows,"MEASURED_INCIDENT_CANDIDATE")
    require(result["admission"]["unique"]==3 and result["admission"]["received"]==6,"dedup mismatch")
    require(admission(rows+rows,"MEASURED_INCIDENT_CANDIDATE")==result,"replay changed receipt")
    publication=result["publication"]
    rid=publication["core"]["run"]["run_id"]
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid) is not None,"invalid run")
    context=call("/api/v1/incident-context/dynamic?run_id="+rid)["context"]
    refs=lambda items:{x["evidence_id"]:x["payload_hash"] for x in items}
    require(len(context["evidence"])==3 and refs(context["evidence"])==refs(publication["stored_evidence"]),"evidence mismatch")
    require(context["policy"]=="DENY" and context["diagnosis"]["hypothesis"]=="LATENCY_REGRESSION_OBSERVED","invalid diagnosis")
    print(json.dumps({"classification":"V3_ADMISSION_MEASURED_CANDIDATE","result":"PASS","run_id":rid,
                      "measurements":result["admission"]["measurements"],"evidence_count":3,"replay_idempotent":True,"production_authorized":False},sort_keys=True))
