"""D black-box observation: independent periodic polling, no injected labels."""
import json
import os
from pathlib import Path
import queue
import re
import runpy
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"vertical"))
from continuous_collector import Collector
base=runpy.run_path(str(Path(__file__).with_name("poc-qa-measured-campaign.py")))
require,api=base["require"],base["api"]
fixture=runpy.run_path(str(Path(__file__).with_name("poc-multiasset-observed.py")))

def main(origin,root):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.getuid()!=0,"disposable CI only")
    require(root==Path("/tmp/aiops-v3-rootless-ci") and root.resolve()==root and root.stat().st_uid==os.getuid(),"dedicated root")
    require(re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) is not None,"loopback required")
    call=api(origin)
    observed=[]
    truth=[]
    events=queue.Queue()
    stop=threading.Event()
    failures=[]
    with fixture["HTTPServer"](("127.0.0.1",0),fixture["App"]) as app:
        require(app.server_port not in (7770,7777,7790),"protected port")
        app.delay=.01
        app.records=[]
        server=threading.Thread(target=app.serve_forever)
        collector=Collector(app.server_port,int(origin.rsplit(":",1)[1]))
        def collect():
            try: collector.run(stop,lambda value:events.put((time.monotonic(),value)),max_windows=60)
            except Exception as exc:
                failures.append(type(exc).__name__)
        runner=threading.Thread(target=collect)
        server.start()
        runner.start()
        def next_window():
            stamp,row=events.get(timeout=20)
            require(not failures and row.get("observation")=="MEASURED" and row["state"]!="UNKNOWN_BLOCKED","collector failed")
            observed.append({"observed_monotonic":stamp,**row})
            return stamp,row
        def wait_state(state,count=1):
            hits=0
            for _ in range(12):
                stamp,row=next_window()
                hits=hits+1 if row["state"]==state else 0
                if hits>=count: return stamp,row
            raise AssertionError("collector did not reach "+state)
        def inject(delay,label):
            stamp=time.monotonic()
            truth.append({"label":label,"at_monotonic":stamp})
            app.delay=delay
            return stamp
        try:
            wait_state("ARMED",2)
            # One degraded window; no publication is allowed. The injector
            # never calls observe() or passes a fault flag to the collector.
            inject(.12,"TRANSIENT")
            for _ in range(4):
                _,row=next_window()
                require(row["state"]=="ARMED" and not row.get("published"),"transient opened incident")
                if row["median_ms"]>=80: break
            else: raise AssertionError("transient not observed")
            inject(.01,"TRANSIENT_END")
            wait_state("ARMED",3)
            detected=[]
            for number in (1,2):
                start=inject(.12,"PERSISTENT_"+str(number))
                stamp,row=wait_state("LATCHED")
                require(row.get("published") is True and stamp-start<60,"missing or late detection")
                rid=row["run_id"]
                detected.append({"run_id":rid,"detection_seconds":round(stamp-start,3)})
                for _ in range(3):
                    _,row=next_window()
                    require(row["state"]=="LATCHED" and row["run_id"]==rid and not row.get("published"),"duplicate incident")
                context=call("/api/v1/incident-context/dynamic?run_id="+rid)["context"]
                require(context["policy"]=="DENY" and context["diagnosis"]["hypothesis"]=="LATENCY_REGRESSION_OBSERVED"
                        and len(context["evidence"])==3,"unverified persisted evidence")
                inject(.01,"RECOVERY_"+str(number))
                wait_state("ARMED",2)
            require(len({r["run_id"] for r in detected})==2,"incident identity reused")
            require(sum(bool(r.get("published")) for r in observed)==2,"wrong publication count")
        finally:
            stop.set()
            runner.join(20)
            app.shutdown()
            server.join(3)
            require(not runner.is_alive() and not server.is_alive() and not failures,"collector leaked or failed")
    report={"classification":"INDEPENDENT_D_PERIODIC_COLLECTION","result":"PASS",
            "polling_period_seconds":1.1,"persistent_episodes":detected,"transient_publications":0,
            "publication_count":2,"observations":observed,"http_requests":len(app.records),
            "operational_decision":"DENY","production_authorized":False,
            "limitations":["Single synthetic loopback HTTP target","No durable collector state or collector authentication",
                           "No unattended remediation","Not production monitoring"]}
    for name,value in (("qa-periodic-truth.json",truth),("qa-periodic-report.json",report)):
        with (root/name).open("x") as f: json.dump(value,f,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k!="observations"},sort_keys=True))

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("usage: campaign ORIGIN ROOT")
    main(sys.argv[1],Path(sys.argv[2]))
