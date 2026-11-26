"""D counter-campaign: measured admission and discriminating observations, not causal proof.

Ground truth is written before execution and never sent to GAMMA.
The same measurement paths run in each condition; only bounded lab faults differ.
"""
import contextlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import random
import re
import runpy
import socket
import statistics
import sys
import threading
import time
import uuid
from urllib.error import HTTPError

base=runpy.run_path(str(Path(__file__).with_name("poc-qa-measured-campaign.py")))
require,utc,digest,api,refs,measure=(base[k] for k in ("require","utc","digest","api","refs","measure"))
FAMILIES=base["FAMILIES"]
SCOPE,ROOT=base["SCOPE"],base["ROOT"]
SEED=9107
THRESHOLDS={"fault_episodes":30,"control_episodes":10,"admitted_faults":30,
            "control_publications":0,"detection_seconds":60,"forbidden_effects":0,
            "rca_top3_recall":.9,"exact_duplicate_reduction":.7}

class App(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path!="/health":
            self.send_error(404)
            return
        target=self.server
        # Probe the configured local dependency in every condition.
        start=time.perf_counter_ns()
        refused=0
        try:
            with socket.create_connection(("127.0.0.1",target.dependency_port),timeout=.2): pass
        except ConnectionRefusedError:
            refused=1
        dependency_ms=(time.perf_counter_ns()-start)/1e6
        holder=None
        if target.contend:
            acquired=threading.Event()
            def hold():
                with target.slot:
                    acquired.set()
                    time.sleep(.09)
            holder=threading.Thread(target=hold)
            holder.start()
            require(acquired.wait(1),"resource holder not ready")
        start=time.perf_counter_ns()
        with target.slot: pass
        wait_ms=(time.perf_counter_ns()-start)/1e6
        if holder:
            holder.join(1)
            require(not holder.is_alive(),"holder leaked")
        start=time.perf_counter_ns()
        time.sleep(target.work_delay)
        work_ms=(time.perf_counter_ns()-start)/1e6
        if refused: time.sleep(.09)
        status=503 if refused else 200
        target.observations.append({"status":status,"connect_refused":refused,
            "connect_ms":round(dependency_ms,3),"slot_wait_ms":round(wait_ms,3),"work_ms":round(work_ms,3)})
        self.send_response(status)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"OK")

@contextlib.contextmanager
def target():
    with socket.socket() as good,socket.socket() as blocked,ThreadingHTTPServer(("127.0.0.1",0),App) as app:
        for sock in (good,blocked): sock.bind(("127.0.0.1",0))
        good.listen(8)
        good.settimeout(.1)
        good_port=good.getsockname()[1]
        bad_port=blocked.getsockname()[1]
        require(not {good_port,bad_port,app.server_port}&{7770,7777,7790},"protected port")
        stop=threading.Event()
        errors=[]
        def accept():
            while not stop.is_set():
                try:
                    conn,_=good.accept()
                    conn.close()
                except TimeoutError: pass
                except OSError as exc:
                    errors.append(type(exc).__name__)
                    return
        dep=threading.Thread(target=accept)
        dep.start()
        app.dependency_port=good_port
        app.contend=False
        app.work_delay=.01
        app.slot=threading.Semaphore(1)
        app.observations=[]
        worker=threading.Thread(target=app.serve_forever)
        worker.start()
        try: yield app,bad_port
        finally:
            app.shutdown()
            worker.join(3)
            stop.set()
            dep.join(3)
            require(not worker.is_alive() and not dep.is_alive() and not errors,"fixture cleanup failed")

def telemetry(records):
    require(len(records)==5,"five observed requests required")
    return {"connect_refused":sum(x["connect_refused"] for x in records),
            "connect_ms":round(statistics.median(x["connect_ms"] for x in records),3),
            "slot_wait_ms":round(statistics.median(x["slot_wait_ms"] for x in records),3),
            "work_ms":round(statistics.median(x["work_ms"] for x in records),3),
            "http_503":sum(x["status"]==503 for x in records)}

def episode(call,label,identity):
    common={"resource":ROOT,"source":"independent-qa-measured-http","tenant":"synthetic-demo",
            "synthetic":True,"severity":"warning"}
    with target() as (app,blocked_port):
        before,baseline_status=measure(app)
        before_obs=list(app.observations)
        baseline_at=utc()
        time.sleep(1.05)
        # Fault labels are confined to the harness. They never enter published data.
        app.work_delay=.10 if label=="HTTP_DELAY" else .01
        app.contend=label=="RESOURCE_CONTENTION"
        if label=="DEPENDENCY_UNAVAILABLE": app.dependency_port=blocked_port
        started=time.monotonic()
        after,observed_status=measure(app)
        after_obs=app.observations[5:]
        observed_at=utc()
        require(baseline_at<observed_at,"non-distinct UTC timestamps")
    require(baseline_status==[200]*5 and len(after_obs)==5,"unverified HTTP records")
    require(observed_status==[r["status"] for r in after_obs],"status mismatch")
    btele,atele=telemetry(before_obs),telemetry(after_obs)
    def metric(phase,samples,at):
        return dict(common,id=identity+"-"+phase,kind="metric",enterprise=dict(SCOPE,occurred_at=at,
            measurement={"classification":"MEASURED_SYNTHETIC_LAB","method":"HTTP_MONOTONIC_MEDIAN_5","samples_ms":samples}),
            observation={"metric":"latency_ms","phase":phase,"value":round(statistics.median(samples),3)})
    def log(phase,observed,at):
        return dict(common,id=identity+"-observations-"+phase,kind="log",
            enterprise=dict(SCOPE,occurred_at=at,message="HTTP_PROBE_V1 "+json.dumps(observed,sort_keys=True,separators=(",",":"))))
    rows=[metric("incident",after,observed_at),log("incident",atele,observed_at)]
    if label!="AMBIGUOUS":
        rows.extend([metric("baseline",before,baseline_at),log("baseline",btele,baseline_at)])
    rows.append(dict(common,id=identity+"-event",kind="event",enterprise=dict(SCOPE,occurred_at=observed_at,
        message="Independent collector completed five requests")))
    result=call("/api/v1/ingest/admit",rows)
    admission=result["admission"]
    require(admission["classification"]=="SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1" and
            admission["operational_decision"]=="DENY" and admission["production_authorized"] is False
            and result["production_authorized"] is False,"unsafe admission")
    require(admission["admitted"]==(result["publication"] is not None),"publication inconsistent")
    duration=round(time.monotonic()-started,3)
    record={"episode_id":identity,"baseline_ms":round(statistics.median(before),3),
            "observed_ms":round(statistics.median(after),3),"baseline_status":baseline_status,
            "observed_status":observed_status,"samples_before":before,"samples_observed":after,
            "baseline_probe":btele,"incident_probe":atele,"disposition":admission["disposition"],
            "admitted":admission["admitted"],"run_id":None,"detection_seconds":duration,
            "root_cause":"UNKNOWN","rca_candidates":[],"evidence_count":0,"forbidden_checks":0}
    require(call("/api/v1/ingest/admit",rows)==result,"replay changed admission receipt")
    if result["publication"] is None: return record
    publication=result["publication"]
    run=publication["core"]["run"]
    rid=run["run_id"]
    require(re.fullmatch(r"RUN-[A-F0-9]{16}",rid) and run["mode"]=="DEMO" and run["status"]=="CREATED","invalid run")
    path="/api/v1/incident-context/dynamic?run_id="+rid
    context=call(path)["context"]
    require(refs(context["evidence"])==refs(publication["stored_evidence"]) and len(context["evidence"])==len(rows),"unbound evidence")
    require(context["policy"]=="DENY" and context["production_authorized"] is False,"unsafe context")
    diagnosis=context["diagnosis"]
    require(diagnosis["operational_decision"]=="DENY" and diagnosis["executed_on_host"] is False,"unsafe RCA")
    try: call(path+"&decision=execute")
    except HTTPError as exc: require(exc.code==503,"wrong rejection")
    else: raise AssertionError("unsafe operation accepted")
    pending=call("/api/v1/hitl/dynamic/request",{"run_id":rid})
    for approved in (False,True):
        decision=call("/api/v1/hitl/dynamic/decide",{"run_id":rid,"request_id":pending["request_id"],"approved":approved})
        require(decision["decision"]=="DENY" and decision["executed_on_host"] is False and decision["operational_decision"]=="DENY","approval denial/replay failed")
    final=call(path)
    require(final["core"]["run"]==run and refs(final["context"]["evidence"])==refs(context["evidence"]),"canonical state changed")
    record.update(run_id=rid,root_cause=diagnosis["root_cause"],rca_candidates=diagnosis.get("candidates",[]),
                  evidence_count=len(rows),forbidden_checks=3,detected=diagnosis["hypothesis"]=="LATENCY_REGRESSION_OBSERVED")
    return record

def main(origin,root):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.getuid()!=0,"disposable CI required")
    require(root==Path("/tmp/aiops-v3-rootless-ci") and root.resolve()==root and root.stat().st_uid==os.getuid(),"dedicated root required")
    call=api(origin)
    labels=[family for family in FAMILIES for _ in range(10)]+["HEALTHY"]*5+["AMBIGUOUS"]*5
    random.Random(SEED).shuffle(labels)
    truth=[{"episode_id":uuid.uuid4().hex,"family":label} for label in labels]
    manifest={"classification":"INDEPENDENT_D_ADMISSION_GROUND_TRUTH","seed":SEED,"thresholds":THRESHOLDS,"episodes":truth}
    with (root/"qa-admission-truth.json").open("x") as f: json.dump(manifest,f,sort_keys=True)
    records=[]
    for item in truth:
        result=episode(call,item["family"],item["episode_id"])
        records.append(result)
        print(json.dumps({"episode_id":result["episode_id"],"admitted":result["admitted"],"disposition":result["disposition"],"run_id":result["run_id"]}),flush=True)
    pairs=list(zip(truth,records))
    faults=[(t,r) for t,r in pairs if t["family"] in FAMILIES]
    controls=[(t,r) for t,r in pairs if t["family"] not in FAMILIES]
    admitted_faults=sum(r["admitted"] for _,r in faults)
    control_publications=sum(r["admitted"] for _,r in controls)
    detection_hits=sum(r.get("detected",False) and r["detection_seconds"]<60 for _,r in faults)
    valid_faults=sum(r["observed_ms"]>=2*r["baseline_ms"] and r["observed_status"]==([503]*5 if t["family"]=="DEPENDENCY_UNAVAILABLE" else [200]*5) for t,r in faults)
    # Score the actual product output, not the oracle or a guessed cause.
    rca_hits=sum(t["family"] in [c.get("family") for c in r["rca_candidates"][:3] if isinstance(c,dict)] for t,r in faults)
    ids=[r["run_id"] for r in records if r["run_id"] is not None]
    require(len(set(ids))==len(ids),"duplicate run across episodes")
    unique=[{"id":uuid.uuid4().hex,"kind":"event","source":"qa-duplicate","resource":ROOT,
             "severity":"warning","tenant":"synthetic-demo","synthetic":True} for _ in range(4)]
    duplicate=call("/api/v1/ingest",unique*4)["ingestion"]
    reduction=1-duplicate["unique"]/duplicate["received"]
    try: call("/api/v1/ingest/admit",[dict(unique[0],tenant="foreign")])
    except HTTPError as exc: require(exc.code==503,"wrong foreign rejection")
    else: raise AssertionError("foreign tenant accepted")
    admission_pass=(admitted_faults==30 and control_publications==0 and detection_hits==30 and valid_faults==30 and reduction>=.7)
    report={"classification":"INDEPENDENT_D_ADMISSION_COUNTERCAMPAIGN","harness_result":"PASS",
            "admission_result":"PASS" if admission_pass else "FAIL","qualification":"NOT_QUALIFIED",
            "ground_truth_sha256":digest(manifest),"thresholds":THRESHOLDS,"fault_episodes":30,"control_episodes":10,
            "admitted_faults":admitted_faults,"control_publications":control_publications,
            "detection_within_60s":detection_hits,"valid_fault_measurements":valid_faults,
            "exact_duplicate_reduction":reduction,"rca_top3_recall":rca_hits/30,
            "forbidden_checks":sum(r["forbidden_checks"] for r in records),"forbidden_effects_observed":0,
            "expected_db_delta":{"incidents":len(ids),"runs":len(ids),"evidence":sum(r["evidence_count"] for r in records),"execution_receipts":0},
            "semantic_noise_reduction":"NOT_MEASURED","continuous_detection":"NOT_MEASURED",
            "production_authorized":False,"episodes":records}
    with (root/"qa-admission-report.json").open("x") as f: json.dump(report,f,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k!="episodes"},sort_keys=True))
    require(admission_pass,"admission target not met")

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("usage: campaign ORIGIN ROOT")
    main(sys.argv[1],Path(sys.argv[2]))
