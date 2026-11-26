"""Independent D acceptance probe: real, bounded HTTP workloads; no remediation.
Ground truth stays outside the platform; detection is after explicit collection.
The CI harness can pass while product qualification remains NOT_QUALIFIED.
"""
import contextlib
from datetime import datetime,timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import re
import socket
import statistics
import sys
import threading
import time
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from urllib.error import HTTPError
import uuid

SEED=7319
FAMILIES=("HTTP_DELAY","RESOURCE_CONTENTION","DEPENDENCY_UNAVAILABLE")
TARGETS={"fault_episodes":30,"control_episodes":10,"detection_seconds":60,
         "dedup_exact_reduction":.70,"rca_top3_recall":.90,"forbidden_effects":0}
SCOPE={"asset_id":"NODE-CI-ENT-ASSET-PAR","application_id":"NODE-CI-ENT-APP-PAY"}
ROOT="NODE-CI-ROOT"

def require(ok,reason):
    if not ok: raise AssertionError(reason)

def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path!="/health":
            self.send_error(404)
            return
        target=self.server
        status=200
        if target.fault=="HTTP_DELAY":
            time.sleep(.09)
        elif target.fault=="RESOURCE_CONTENTION":
            acquired=threading.Event()
            def hold():
                with target.slot:
                    acquired.set()
                    time.sleep(.09)
            t=threading.Thread(target=hold)
            t.start()
            require(acquired.wait(1),"resource holder did not start")
            with target.slot: pass
            t.join(1)
            require(not t.is_alive(),"resource holder leaked")
        elif target.fault=="DEPENDENCY_UNAVAILABLE":
            # The dependency's port is held by a bound, non-listening socket.
            # An actual failed connection triggers a bounded fallback.
            try:
                with socket.create_connection(("127.0.0.1",target.dependency_port),timeout=.2):
                    raise AssertionError("unavailable dependency unexpectedly accepted connection")
            except ConnectionRefusedError:
                status=503
                time.sleep(.09)
        else:
            time.sleep(.01)
        self.send_response(status)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"OK")

@contextlib.contextmanager
def target():
    with socket.socket() as blocked,ThreadingHTTPServer(("127.0.0.1",0),Handler) as app:
        blocked.bind(("127.0.0.1",0))
        app.dependency_port=blocked.getsockname()[1]
        require(not {app.server_port,app.dependency_port}&{7770,7777,7790},"protected port")
        app.fault=None
        app.slot=threading.Semaphore(1)
        thread=threading.Thread(target=app.serve_forever)
        thread.start()
        try: yield app
        finally:
            app.shutdown()
            thread.join(3)
            require(not thread.is_alive(),"target leaked")

def measure(app):
    samples=[]; statuses=[]
    for _ in range(5):
        conn=http.client.HTTPConnection("127.0.0.1",app.server_port,timeout=2)
        try:
            start=time.perf_counter_ns()
            conn.request("GET","/health")
            response=conn.getresponse()
            body=response.read()
            samples.append(round((time.perf_counter_ns()-start)/1e6,3))
            require(body==b"OK" and response.status in (200,503),"unexpected target response")
            statuses.append(response.status)
        finally: conn.close()
    return samples,statuses

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def api(origin):
    require(re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) is not None,"loopback required")
    require(1024<=int(origin.rsplit(":",1)[1])<=65535 and int(origin.rsplit(":",1)[1]) not in (7770,7777,7790),"invalid port")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def call(path,body=None):
        data=None if body is None else json.dumps(body,separators=(",",":")).encode()
        require(data is None or len(data)<=4096,"batch exceeds real HTTP limit")
        request=Request(origin+path,data=data,headers={"Origin":origin,"Content-Type":"application/json"})
        with opener.open(request,timeout=30) as response:
            raw=response.read(65537)
            require(len(raw)<=65536,"oversized response")
            return json.loads(raw)
    return call

def refs(rows):
    require(len({x["evidence_id"] for x in rows})==len(rows),"duplicate evidence references")
    return {x["evidence_id"]:x["payload_hash"] for x in rows}

def episode(call,label,identity):
    common={"resource":ROOT,"source":"independent-qa-http","tenant":"synthetic-demo",
            "synthetic":True,"severity":"warning"}
    def metric(phase,samples,at):
        return dict(common,id=identity+"-"+phase,kind="metric",
                    enterprise=dict(SCOPE,occurred_at=at,measurement={
                        "classification":"MEASURED_SYNTHETIC_LAB","method":"HTTP_MONOTONIC_MEDIAN_5","samples_ms":samples}),
                    observation={"metric":"latency_ms","phase":phase,"value":round(statistics.median(samples),3)})
    with target() as app:
        before,baseline_status=measure(app)
        baseline_at=utc()
        app.fault=label if label in FAMILIES else None
        injected=time.monotonic()
        after,observed_status=measure(app)
        observed_at=utc()
    rows=[metric("incident",after,observed_at)]
    if label!="AMBIGUOUS":
        rows.insert(0,metric("baseline",before,baseline_at))
    rows.append(dict(common,id=identity+"-log",kind="log",enterprise=dict(SCOPE,occurred_at=observed_at,
                    message="HTTP observation statuses: "+",".join(map(str,observed_status)))))
    rows.append(dict(common,id=identity+"-event",kind="event",enterprise=dict(SCOPE,occurred_at=observed_at,
                    message="Independent collector completed five requests")))
    created=call("/api/v1/ingest/create",rows)
    run=created["core"]["run"]
    rid=run["run_id"]
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid) and run["mode"]=="DEMO" and run["status"]=="CREATED","invalid run")
    path="/api/v1/incident-context/dynamic?run_id="+rid
    projection=call(path)
    seconds=round(time.monotonic()-injected,3)
    context=projection["context"]
    diagnosis=context["diagnosis"]
    require(projection["core"]["run"]==run and projection["production_authorized"] is False
            and context["policy"]=="DENY" and context["production_authorized"] is False
            and diagnosis["operational_decision"]=="DENY" and diagnosis["executed_on_host"] is False
            and refs(context["evidence"])==refs(created["stored_evidence"]),"unsafe or unbound projection")
    require(call("/api/v1/ingest/create",rows)==created,"replayed ingestion changed receipt")
    require(refs(call(path)["context"]["evidence"])==refs(context["evidence"]),"evidence changed on read")
    # Explicit invalid operation, not a real remediation request.
    try: call(path+"&decision=execute")
    except HTTPError as exc: require(exc.code==503,"unexpected operation rejection")
    else: raise AssertionError("unsafe operation accepted")
    pending=call("/api/v1/hitl/dynamic/request",{"run_id":rid})
    rejected=call("/api/v1/hitl/dynamic/decide",{"run_id":rid,"request_id":pending["request_id"],"approved":False})
    require(rejected["decision"]=="DENY" and rejected["operational_decision"]=="DENY" and rejected["executed_on_host"] is False,"HITL denial missing")
    replay=call("/api/v1/hitl/dynamic/decide",{"run_id":rid,"request_id":pending["request_id"],"approved":True})
    require(replay["decision"]=="DENY" and replay["executed_on_host"] is False,"denied approval replay accepted")
    final=call(path)
    require(final["core"]["run"]==run and refs(final["context"]["evidence"])==refs(context["evidence"]),"forbidden operation altered canonical state")
    return {"episode_id":identity,"run_id":rid,"baseline_ms":round(statistics.median(before),3),
            "observed_ms":round(statistics.median(after),3),"baseline_status":baseline_status,
            "observed_status":observed_status,"samples_before":before,"samples_observed":after,
            "collection_to_projection_seconds":seconds,"detected":diagnosis["hypothesis"]=="LATENCY_REGRESSION_OBSERVED",
            "root_cause":diagnosis["root_cause"],"rca_candidates":diagnosis.get("candidates",[]),
            "evidence_count":len(context["evidence"]),"incident_created":True,
            "forbidden_effects":0,"production_authorized":False}

def main(origin,root):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.getuid()!=0,"disposable rootless CI only")
    require(root==Path("/tmp/aiops-v3-rootless-ci") and root.resolve()==root and root.stat().st_uid==os.getuid(),"dedicated root required")
    call=api(origin)
    labels=[family for family in FAMILIES for _ in range(10)]+["HEALTHY"]*5+["AMBIGUOUS"]*5
    random.Random(SEED).shuffle(labels)
    truth=[{"episode_id":uuid.uuid4().hex,"family":label} for label in labels]
    manifest={"classification":"INDEPENDENT_D_GROUND_TRUTH","seed":SEED,"thresholds":TARGETS,"episodes":truth}
    with (root/"qa-ground-truth.json").open("x") as f: json.dump(manifest,f,sort_keys=True)
    results=[]
    for item in truth:
        result=episode(call,item["family"],item["episode_id"])
        results.append(result)
        print(json.dumps({"episode_id":result["episode_id"],"run_id":result["run_id"],"detected":result["detected"],"root_cause":result["root_cause"]}),file=sys.stderr,flush=True)
    require(len({r["run_id"] for r in results})==40,"run reuse across independent episodes")
    # Exact replay suppression measured separately from semantic alert noise.
    unique=[{"id":uuid.uuid4().hex,"kind":"event","source":"qa-duplicate",
             "resource":ROOT,"severity":"warning","tenant":"synthetic-demo","synthetic":True} for _ in range(4)]
    duplicate=call("/api/v1/ingest",unique*4)["ingestion"]
    reduction=1-duplicate["unique"]/duplicate["received"]
    foreign=dict(unique[0],tenant="foreign")
    try: call("/api/v1/ingest/create",[foreign])
    except HTTPError as exc: require(exc.code==503,"foreign tenant not rejected")
    else: raise AssertionError("foreign tenant accepted")
    pairs=list(zip(truth,results))
    faults=[(t,r) for t,r in pairs if t["family"] in FAMILIES]
    controls=[(t,r) for t,r in pairs if t["family"] not in FAMILIES]
    hits=sum(r["detected"] and r["collection_to_projection_seconds"]<TARGETS["detection_seconds"] for _,r in faults)
    false_positive=sum(r["detected"] for _,r in controls)
    ground_truth_valid=sum((r["observed_ms"]>=2*r["baseline_ms"] and
                            r["observed_status"]==([503]*5 if t["family"]=="DEPENDENCY_UNAVAILABLE" else [200]*5))
                           for t,r in faults)
    family_scores={family:{"episodes":10,"detected":sum(r["detected"] for t,r in faults if t["family"]==family)}
                   for family in FAMILIES}
    # The current API has no independently calibrated causal candidate list.
    # Do not translate a latency symptom or UNKNOWN into a correct RCA.
    rca_hits=sum(t["family"] in [c.get("family") for c in r["rca_candidates"][:3] if isinstance(c,dict)] for t,r in faults)
    report={"classification":"INDEPENDENT_D_MEASURED_CAMPAIGN","harness_result":"PASS",
            "qualification":"NOT_QUALIFIED","ground_truth_sha256":digest(manifest),"thresholds":TARGETS,
            "fault_episodes":len(faults),"control_episodes":len(controls),"valid_fault_measurements":ground_truth_valid,
            "detection_within_60s":hits,"hypothesis_false_positives":false_positive,
            "control_incidents_created":sum(r["incident_created"] for _,r in controls),
            "exact_duplicate_reduction":reduction,"semantic_noise_reduction":"NOT_MEASURED",
            "rca_top3_recall":rca_hits/len(faults),"family_scores":family_scores,
            "forbidden_effects":sum(r["forbidden_effects"] for r in results),
            "continuous_detection":"NOT_MEASURED","production_authorized":False,
            "limitations":["Explicit collection, not continuous detection","Local synthetic workload surrogates, not production incidents",
                           "No independent LLM, product action or recovery campaign","Foreign tenant rejection is not tenant ACL qualification"],
            "episodes":results}
    with (root/"qa-measured-campaign.json").open("x") as f: json.dump(report,f,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k!="episodes"},sort_keys=True))

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("usage: campaign ORIGIN ROOT")
    main(sys.argv[1],Path(sys.argv[2]))
