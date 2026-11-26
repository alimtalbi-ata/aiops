"""Measure two independent loopback applications; publish distinct synthetic lab incidents."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import json
import re
import statistics
import sys
import threading
import time
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

P="NODE-CI-ENT-"
CONFIGS=(
    ("NODE-CI-ROOT",P+"ASSET-PAR",P+"APP-PAY",P+"GROUP-FIN",P+"USER-FIN-01",0.12),
    (P+"ASSET-LYO",P+"ASSET-LYO",P+"APP-HR",P+"GROUP-HR",P+"USER-HR-01",0.19),
)

def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class App(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path!="/health":
            self.send_error(404)
            return
        time.sleep(self.server.delay)
        self.send_response(200)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"OK")
        self.server.records.append({"at":now(),"status":200})

def measure(app):
    values=[]
    for _ in range(5):
        conn=http.client.HTTPConnection("127.0.0.1",app.server_port,timeout=3)
        try:
            start=time.perf_counter_ns()
            conn.request("GET","/health")
            response=conn.getresponse()
            body=response.read()
            elapsed=(time.perf_counter_ns()-start)/1e6
            if response.status!=200 or body!=b"OK":
                raise RuntimeError("unexpected app response")
            values.append(round(elapsed,3))
        finally:
            conn.close()
    return values

def collect():
    identity=uuid.uuid4().hex
    with ExitStack() as stack, ThreadPoolExecutor(max_workers=2) as pool:
        apps=[]
        for _ in CONFIGS:
            app=stack.enter_context(HTTPServer(("127.0.0.1",0),App))
            if app.server_port in (7770,7777,7790):
                raise RuntimeError("protected port")
            app.delay=0.01
            app.records=[]
            t=threading.Thread(target=app.serve_forever,daemon=True)
            t.start()
            stack.callback(t.join,5)
            stack.callback(app.shutdown)
            apps.append(app)
        before=list(pool.map(measure,apps))
        baseline_time=now()
        for app,config in zip(apps,CONFIGS):
            app.delay=config[-1]
        change_time=now()
        after=list(pool.map(measure,apps))
        incident_time=now()
        batches=[]
        for i,(config,app,b,a) in enumerate(zip(CONFIGS,apps,before,after)):
            root,asset,application,group,user,_=config
            baseline=round(statistics.median(b),3)
            incident=round(statistics.median(a),3)
            if not 0<baseline<incident/2 or len(app.records)!=10:
                raise RuntimeError("measured regression not established")
            base={"resource":root,"source":"multiasset-observed-http","tenant":"synthetic-demo","synthetic":True,"severity":"critical"}
            scope={"asset_id":asset,"application_id":application}
            prefix=identity+"-"+str(i)+"-"
            rows=[]
            for phase,samples,value,at in (("baseline",b,baseline,baseline_time),("incident",a,incident,incident_time)):
                rows.append(dict(base,id=prefix+phase,kind="metric",
                    enterprise=dict(scope,occurred_at=at,measurement={"classification":"MEASURED_SYNTHETIC_LAB","samples_ms":samples,"method":"HTTP_MONOTONIC_MEDIAN_5"}),
                    observation={"metric":"latency_ms","phase":phase,"value":value}))
            rows.append(dict(base,id=prefix+"log",kind="log",enterprise=dict(scope,occurred_at=app.records[-1]["at"],group_id=group,user_id=user,message="Lab HTTP log: ten requests completed with status 200; synthetic client identity")))
            rows.append(dict(base,id=prefix+"event",kind="event",enterprise=dict(scope,occurred_at=change_time,message="Controlled response delay applied to isolated lab application")))
            batches.append(rows)
        return batches

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def smoke(origin):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) or int(origin.rsplit(":",1)[1]) in (7770,7777,7790):
        raise ValueError("isolated origin required")
    opener=build_opener(ProxyHandler({}),NoRedirect())
    def call(path,data=None):
        req=Request(origin+path,data=None if data is None else json.dumps(data).encode(),headers={"Origin":origin,"Content-Type":"application/json"})
        with opener.open(req,timeout=30) as response:
            return json.load(response)
    batches=collect()
    # Keep incident correlation per resource; do not combine unrelated applications.
    with ThreadPoolExecutor(max_workers=2) as pool:
        created=list(pool.map(lambda rows:call("/api/v1/ingest/create",rows),batches))
    receipts=[]
    for i,(rows,result) in enumerate(zip(batches,created)):
        run=result["core"]["run"]["run_id"]
        context=call("/api/v1/incident-context/dynamic?run_id="+run)
        ent=context["enterprise_context"]
        assert ent["root"]==CONFIGS[i][0] and ent["reported_user_ids"]==[CONFIGS[i][4]]
        assert ent["production_authorized"] is False and ent["causality_established"] is False
        assert len(ent["timeline"])==4
        assert {x["evidence_id"]:x["payload_hash"] for x in ent["timeline"]}=={x["evidence_id"]:x["payload_hash"] for x in result["stored_evidence"]}
        assert {x["node_id"] for x in ent["potential_exposure"]["applications"]}==({P+"APP-PAY",P+"APP-CRM"} if i==0 else {P+"APP-HR"})
        assert {x["id"] for x in ent["document_references"]}==({"ENT-DOC-001","ENT-DOC-003"} if i==0 else {"ENT-DOC-004"})
        for row in rows[:2]:
            match=next(x for x in ent["timeline"] if x["event_id"]==row["id"])
            assert match["measurement"]==row["enterprise"]["measurement"] and match["observation"]==row["observation"]
        assert context["copilot"]["sources"]==context["context"]["evidence"]
        receipts.append({"run_id":run,"resource":ent["root"],"application":CONFIGS[i][2],"baseline_ms":rows[0]["observation"]["value"],"incident_ms":rows[1]["observation"]["value"],"evidence_count":4})
    assert receipts[0]["run_id"]!=receipts[1]["run_id"]
    print(json.dumps({"classification":"MULTIASSET_MEASURED_SYNTHETIC_LAB","result":"PASS","incidents":receipts,"production_authorized":False}))

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: poc-multiasset-observed.py ORIGIN")
    smoke(sys.argv[1])
