"""D process-crash campaign; real GAMMA publication and independent target."""
import json
import os
from pathlib import Path
import queue
import re
import runpy
import subprocess
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"vertical"))
import continuous_collector as periodic
from durable_collector import DurableCollector
base=runpy.run_path(str(Path(__file__).with_name("poc-qa-measured-campaign.py")))
require,api=base["require"],base["api"]
fixture=runpy.run_path(str(Path(__file__).with_name("poc-multiasset-observed.py")))

def child(root,target,gamma,mode):
    # This failure injection is test harness only. A real successful HTTP
    # publication is observed by the adapter, then the process dies before
    # the collector can consume its response or commit LATCHED.
    if mode=="crash-after-publication":
        real=periodic.admission
        def lose_ack(port,rows):
            response=real(port,rows)
            assert response["admission"]["admitted"] is True
            print(json.dumps({"committed_run":response["publication"]["core"]["run"]["run_id"]}),flush=True)
            os._exit(73)
        periodic.admission=lose_ack
    with DurableCollector(target,gamma,root,initialize=mode=="init") as collector:
        collector.run(threading.Event(),lambda row:print(json.dumps(row),flush=True),max_windows=100)

def main(origin,root):
    require(os.getenv("GITHUB_ACTIONS")=="true" and os.getuid()!=0 and root==Path("/tmp/aiops-v3-rootless-ci")
            and root.resolve()==root and root.stat().st_uid==os.getuid(),"disposable root required")
    require(re.fullmatch(r"http://127\.0\.0\.1:[0-9]{4,5}",origin) is not None,"loopback required")
    gamma=int(origin.rsplit(":",1)[1])
    call=api(origin)
    journal=root/"collector-durable"
    journal.mkdir(mode=0o700,exist_ok=False)
    report=[]
    with fixture["HTTPServer"](("127.0.0.1",0),fixture["App"]) as app:
        app.delay=.01
        app.records=[]
        server=threading.Thread(target=app.serve_forever)
        server.start()
        p=None
        reader=None
        events=None
        def launch(mode):
            nonlocal p,reader,events
            events=queue.Queue()
            p=subprocess.Popen([sys.executable,__file__,"child",str(journal),str(app.server_port),str(gamma),mode],
                               stdout=subprocess.PIPE,text=True)
            stream=p.stdout
            target_queue=events
            def read():
                for line in stream: target_queue.put(json.loads(line))
                target_queue.put(None)
            reader=threading.Thread(target=read)
            reader.start()
        def kill():
            nonlocal p,reader
            if p is not None:
                if p.poll() is None: p.kill()
                p.wait(timeout=10)
                reader.join(5)
                require(not reader.is_alive(),"reader leaked")
                p.stdout.close()
                p=None
        def next_row():
            row=events.get(timeout=20)
            require(row is not None,"collector exited unexpectedly")
            report.append(row)
            return row
        def until(state):
            for _ in range(12):
                row=next_row()
                if row.get("state")==state: return row
            raise AssertionError("state not reached "+state)
        try:
            launch("init")
            until("ARMED")
            # A second live process must not acquire the journal.
            try:
                with DurableCollector(app.server_port,gamma,journal): pass
            except BlockingIOError: pass
            else: raise AssertionError("second owner accepted")
            app.delay=.12
            row=until("LATCHED")
            rid=row["run_id"]
            require(row.get("published") is True,"missing first publication")
            kill()
            launch("resume")
            for _ in range(3):
                row=next_row()
                require(row["state"]=="LATCHED" and row["run_id"]==rid and not row.get("published"),"restart duplicate")
            app.delay=.01
            until("ARMED")
            kill()
            launch("crash-after-publication")
            until("ARMED")
            app.delay=.12
            committed=None
            for _ in range(12):
                row=next_row()
                if "committed_run" in row:
                    committed=row["committed_run"]
                    break
            require(committed and committed!=rid,"missing second real publication")
            require(p.wait(timeout=10)==73,"expected process crash")
            kill()
            launch("resume")
            for _ in range(3):
                row=next_row()
                require(row["state"]=="UNKNOWN_BLOCKED" and not row.get("published"),"ambiguous publication retried")
            app.delay=.01
            for _ in range(3):
                require(next_row()["state"]=="UNKNOWN_BLOCKED","ambiguous latch rearmed")
            app.delay=.12
            for _ in range(3):
                require(next_row()["state"]=="UNKNOWN_BLOCKED","ambiguous latch published")
            for identity in (rid,committed):
                ctx=call("/api/v1/incident-context/dynamic?run_id="+identity)["context"]
                require(ctx["policy"]=="DENY" and len(ctx["evidence"])==3,"missing canonical evidence")
            kill()
        finally:
            kill()
            app.shutdown()
            server.join(5)
    result={"classification":"INDEPENDENT_D_DURABLE_COLLECTOR","result":"PASS","run_ids":[rid,committed],
            "actual_process_crashes":2,"ack_loss_after_real_publication":True,"exclusive_owner":True,
            "latched_restart_no_duplicate":True,"ambiguous_restart_no_retry":True,
            "http_requests":len(app.records),"production_authorized":False,"observations":report}
    with (root/"qa-durable-collector.json").open("x") as f: json.dump(result,f,sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!="observations"},sort_keys=True))

if __name__=="__main__":
    if len(sys.argv)==6 and sys.argv[1]=="child":
        child(Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),sys.argv[5])
    elif len(sys.argv)==3:
        main(sys.argv[1],Path(sys.argv[2]))
    else: raise SystemExit("unsupported invocation")
