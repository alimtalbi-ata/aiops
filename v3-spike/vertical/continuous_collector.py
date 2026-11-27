"""Bounded periodic synthetic-lab collector. No action or general host discovery.

The baseline is commissioned on an explicitly nominal local target. A pair of
consecutive degraded windows opens one episode; recovery re-arms after two
nominal windows. Ambiguous publication blocks further writes. State is local
to this process: restart/restore and collector authentication are not qualified.
"""
from datetime import datetime,timezone
import http.client
import json
import math
import statistics
import time
import uuid
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler,Request
from ingestion_demo import ingest
from collector_receipt import validate_receipt

ROOT="NODE-CI-ROOT"
SCOPE={"asset_id":"NODE-CI-ENT-ASSET-PAR","application_id":"NODE-CI-ENT-APP-PAY"}
PERIOD=1.1
MAX_WINDOWS=100

def require(ok,message):
    if not ok: raise ValueError(message)

def port(value):
    require(type(value) is int and 1024<=value<=65535 and value not in (7770,7777,7790),"isolated loopback port required")
    return value

def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sample(target_port):
    samples=[]
    for _ in range(5):
        c=http.client.HTTPConnection("127.0.0.1",port(target_port),timeout=2)
        try:
            start=time.perf_counter_ns()
            c.request("GET","/health")
            response=c.getresponse()
            raw=response.read(3)
            require(response.status==200 and raw==b"OK","unverified sample")
            samples.append(round((time.perf_counter_ns()-start)/1e6,3))
        finally:
            c.close()
    require(all(math.isfinite(v) and 0<v<=2000 for v in samples),"invalid sample")
    return {"at":utc(),"samples":samples,"median":round(statistics.median(samples),3)}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def admission(gamma_port,rows):
    origin="http://127.0.0.1:"+str(port(gamma_port))
    body=json.dumps(rows,separators=(",",":")).encode()
    require(len(body)<=4096,"oversized batch")
    req=Request(origin+"/api/v1/ingest/admit",data=body,headers={"Origin":origin,"Content-Type":"application/json"})
    with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=15) as response:
        raw=response.read(65537)
        require(len(raw)<=65536 and response.headers.get("Cache-Control")=="no-store","invalid admission response")
        return json.loads(raw)

def batch(baseline,incident):
    identity=uuid.uuid4().hex
    common=dict(resource=ROOT,source="continuous-lab-http",tenant="synthetic-demo",synthetic=True,severity="warning")
    rows=[]
    for phase,window in (("baseline",baseline),("incident",incident)):
        rows.append(dict(common,id=identity+"-"+phase,kind="metric",enterprise=dict(SCOPE,occurred_at=window["at"],
             measurement={"classification":"MEASURED_SYNTHETIC_LAB","method":"HTTP_MONOTONIC_MEDIAN_5","samples_ms":window["samples"]}),
             observation={"metric":"latency_ms","phase":phase,"value":window["median"]}))
    rows.append(dict(common,id=identity+"-log",kind="log",enterprise=dict(SCOPE,occurred_at=incident["at"],
                     message="Periodic collector completed five HTTP health requests with status 200")))
    return rows

class Collector:
    def __init__(self,target_port,gamma_port):
        self.target_port=port(target_port)
        self.gamma_port=port(gamma_port)
        require(target_port!=gamma_port,"separate endpoints required")
        self.state="COMMISSIONING"
        self.baseline=None
        self.nominal=0
        self.degraded=0
        self.run_id=None

    def checkpoint(self):
        """Optional durable subclass hook; default remains process-local."""

    def publish(self, rows, correlation):
        return admission(self.gamma_port, rows)

    def allow_local_rearm(self):
        return True

    def observe(self):
        try:
            window=sample(self.target_port)
        except Exception:
            self.nominal=self.degraded=0
            self.checkpoint()
            return {"state":self.state,"observation":"UNAVAILABLE","run_id":self.run_id}
        value=window["median"]
        result={"median_ms":value,"sampled_at":window["at"],"state":self.state,
                "observation":"MEASURED","run_id":self.run_id}
        if self.state=="UNKNOWN_BLOCKED":
            return result
        if self.state=="COMMISSIONING":
            # The fixed disposable fixture is commissioned at <=40 ms only.
            if value<=40:
                self.nominal+=1
                self.baseline=window
                if self.nominal>=2:
                    self.state="ARMED"
                    self.nominal=0
            else:
                self.nominal=0
                self.baseline=None
        elif self.state=="ARMED":
            if value>=2*self.baseline["median"]:
                self.degraded+=1
                if self.degraded>=2:
                    # Fail closed BEFORE publication; a lost response must not
                    # lead to a new run or a fresh identity on the next poll.
                    self.state="UNKNOWN_BLOCKED"
                    self.checkpoint()
                    try:
                        rows=batch(self.baseline,window)
                        correlation=ingest(rows)
                        response=self.publish(rows,correlation)
                        self.run_id=validate_receipt(correlation,response)
                        self.state="LATCHED"
                        result["published"]=True
                    except Exception:
                        result["publication_unknown"]=True
            else:
                self.degraded=0
                if value<=1.5*self.baseline["median"] and value<=40:
                    self.baseline=window
        elif self.state=="LATCHED" and self.allow_local_rearm():
            if value<=1.5*self.baseline["median"] and value<=40:
                self.nominal+=1
                if self.nominal>=2:
                    self.baseline=window
                    self.state="ARMED"
                    self.nominal=self.degraded=0
                    self.run_id=None
            else:
                self.nominal=0
        self.checkpoint()
        result.update(state=self.state,run_id=self.run_id)
        return result

    def run(self,stop,report,max_windows=MAX_WINDOWS):
        require(type(max_windows) is int and 1<=max_windows<=MAX_WINDOWS,"bounded campaign required")
        for _ in range(max_windows):
            if stop.is_set(): return
            started=time.monotonic()
            report(self.observe())
            if stop.wait(max(0,PERIOD-(time.monotonic()-started))): return
