"""Measured recovery after synthetic HITL on a private loopback HTTP fixture.

No host or existing service configuration changes. Publishes a new immutable
comparison run; original run and Evidence are retained. CI approval is synthetic.
"""
from pathlib import Path
import runpy
import hashlib
import json
import re
import statistics
import sys
import threading
import time
import uuid
from http.server import HTTPServer
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler

fixture=runpy.run_path(str(Path(__file__).with_name("poc-multiasset-observed.py")))
App,measure,now=fixture["App"],fixture["measure"],fixture["now"]
root,asset,application,group,user,degraded=fixture["CONFIGS"][0]
origin=sys.argv[1]
assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) and int(origin.rsplit(":",1)[1]) not in (7770,7777,7790)
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
opener=build_opener(ProxyHandler({}),NoRedirect())
def call(path,data=None):
    req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),headers={"Origin":origin,"Content-Type":"application/json"})
    with opener.open(req,timeout=30) as r:return json.load(r)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
identity=uuid.uuid4().hex
base={"resource":root,"source":"measured-recovery-ci","tenant":"synthetic-demo","synthetic":True,"severity":"critical"}
scope={"asset_id":asset,"application_id":application}
def metric(phase,samples):
    return dict(base,id=identity+"-"+phase,kind="metric",
                enterprise=dict(scope,occurred_at=now(),measurement={"classification":"MEASURED_SYNTHETIC_LAB","method":"HTTP_MONOTONIC_MEDIAN_5","samples_ms":samples}),
                observation={"metric":"latency_ms","phase":phase,"value":round(statistics.median(samples),3)})
def event(name,message):
    return dict(base,id=identity+"-"+name,kind="event",enterprise=dict(scope,occurred_at=now(),message=message))
def publish(rows):
    d=call("/api/v1/ingest/create",rows)
    assert d==call("/api/v1/ingest/create",rows)
    rid=d["core"]["run"]["run_id"]
    assert re.fullmatch(r"RUN-[A-F0-9]{16}",rid)
    return rid,d
def context(rid):return call("/api/v1/incident-context/dynamic?run_id="+rid)
with HTTPServer(("127.0.0.1",0),App) as app:
    assert app.server_port not in (7770,7777,7790)
    app.delay=.01
    app.records=[]
    thread=threading.Thread(target=app.serve_forever,daemon=True)
    thread.start()
    try:
        baseline=metric("baseline",measure(app))
        # Enterprise timestamps are UTC with one-second resolution.
        time.sleep(1.1)
        app.delay=degraded
        fault=event("fault","Controlled lab response delay applied")
        incident=metric("incident",measure(app))
        rows=[baseline,fault,incident]
        rid,created=publish(rows)
        original=context(rid)
        assert original["context"]["diagnosis"]["hypothesis"]=="LATENCY_REGRESSION_OBSERVED"
        for approved in (False,True):
            pending=call("/api/v1/hitl/dynamic/request",{"run_id":rid})
            payload={"run_id":rid,"request_id":pending["request_id"],"approved":approved}
            decision=call("/api/v1/hitl/dynamic/decide",payload)
            assert decision["run_id"]==rid and decision["decision"]==("SIMULATE_ONLY" if approved else "DENY")
            assert decision["production_authorized"] is False and decision["executed_on_host"] is False
            assert call("/api/v1/hitl/dynamic/decide",payload)["decision"]=="DENY"
            assert app.delay==degraded
        approval_binding=digest({"run_id":rid,"evidence":original["context"]["evidence"],"decision":decision})
        # The only intervention is a local Python variable on this fixture.
        time.sleep(1.1)
        app.delay=.01
        action=event("action","Synthetic HITL fixture-only delay reset; prior run "+rid+"; approval binding "+approval_binding)
        recovery=metric("recovery",measure(app))
        assert len(app.records)==15
        comparison_rows=rows+[action,recovery]
        comparison_id,comparison=publish(comparison_rows)
        assert comparison_id!=rid
        final=context(comparison_id)
        d=final["context"]["diagnosis"]["recovery"]
        assert d["within_baseline_tolerance"] and d["causality_established"] is False
        assert d["recovery_ms"]==recovery["observation"]["value"]
        assert final["context"]["policy"]=="DENY" and final["production_authorized"] is False
        timeline=final["enterprise_context"]["timeline"]
        assert len(timeline)==5
        assert {x["evidence_id"]:x["payload_hash"] for x in timeline}=={x["evidence_id"]:x["payload_hash"] for x in comparison["stored_evidence"]}
        assert next(x for x in timeline if x["event_id"]==recovery["id"])["measurement"]==recovery["enterprise"]["measurement"]
        assert next(x for x in timeline if x["event_id"]==action["id"])["message"]==action["enterprise"]["message"]
        after=context(rid)
        assert after["core"]["run"]==original["core"]["run"] and after["context"]["evidence"]==original["context"]["evidence"]
        print(json.dumps({"classification":"E17_MEASURED_LAB_RECOVERY","result":"PASS","original_run_id":rid,
                          "comparison_run_id":comparison_id,"approval_binding_sha256":approval_binding,
                          "measurements":d,"original_evidence":created["stored_evidence"],"comparison_evidence":comparison["stored_evidence"],
                          "host_execution":False,"production_authorized":False},sort_keys=True))
    finally:
        app.shutdown()
        thread.join(5)
