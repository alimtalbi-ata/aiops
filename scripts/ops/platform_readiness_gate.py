#!/usr/bin/env python3
"""AIOps2 platform-wide read-only smoke gate for SRV-DEB-05.

Checks all primary services, Docker topology, runtime versions, core data,
and cross-service reachability without mutating infrastructure.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

SERVICES={
 "core":("aiops2-rebuild-core",810,"/health"),
 "twin":("aiops2-rebuild-twin",811,"/health"),
 "evidence":("aiops2-rebuild-evidence",812,"/health"),
 "policy":("aiops2-rebuild-policy",813,"/health"),
 "worker":("aiops2-rebuild-worker",815,"/health"),
 "intelligence":("aiops2-rebuild-intelligence",817,"/health"),
 "glpi":("aiops2-rebuild-glpi",80,"/"),
}
INFRA={"temporal":"aiops2-rebuild-temporal","postgres":"aiops2-rebuild-postgres"}
def cmd(args,stdin=None,timeout=30):
    p=subprocess.run(args,input=stdin,text=True,capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(f"{args[0]} exit={p.returncode}: {p.stderr[:180]}")
    return p.stdout
def docker_state():
    names=[x[0] for x in SERVICES.values()]+list(INFRA.values())
    return json.loads(cmd(["docker","inspect",*names]))
def core_probe():
    program="""import json,urllib.request,urllib.error
services=json.loads(__import__('sys').argv[1])
out={}
for name,host,port,path in services:
 try:
  with urllib.request.urlopen('http://'+host+':'+str(port)+path,timeout=5) as r:
   out[name]={'http':r.status}
 except urllib.error.HTTPError as e: out[name]={'http':e.code}
 except Exception as e: out[name]={'error':type(e).__name__}
for name,path in [('dashboard','/api/dashboard'),('runs','/api/runs'),('incidents','/api/incidents'),('twin_summary','http://aiops2-rebuild-twin:811/api/twin/summary')]:
 url=path if path.startswith('http') else 'http://127.0.0.1:810'+path
 try:
  with urllib.request.urlopen(url,timeout=6) as r:
   data=json.load(r)
   out[name]={'http':r.status,'top_level_keys':sorted(data)[:30] if isinstance(data,dict) else [],
              'counts':{k:v for k,v in data.items() if k in ('runs_total','open_incidents','twin_nodes','nodes_total','edges_total') and isinstance(v,(int,float))} if isinstance(data,dict) else {}}
 except urllib.error.HTTPError as e: out[name]={'http':e.code}
 except Exception as e: out[name]={'error':type(e).__name__}
print(json.dumps(out))
"""
    targets=[(name,container,port,path) for name,(container,port,path) in SERVICES.items() if name!="core"]
    targets.insert(0,("core","127.0.0.1",810,"/health"))
    return json.loads(cmd(["docker","exec","-i","aiops2-rebuild-core","python3","-c",program,json.dumps(targets)]))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    report={"schema":"aiops2-platform-readiness-v1","utc":dt.datetime.now(dt.timezone.utc).isoformat(),"read_only":True,
            "qualification_scope":"read_only_platform_smoke",
            "e2e_verdict":"NOT_VERIFIED",
            "deployment_verdict":"NOT_VERIFIED"}
    try:
        containers=docker_state()
        report["runtime"]={c["Name"].lstrip("/"):{"image":c["Config"]["Image"],
            "image_id":c["Image"],"state":c["State"]["Status"],
            "health":c["State"].get("Health",{}).get("Status","NOT_CONFIGURED"),
            "networks":sorted(c["NetworkSettings"]["Networks"])} for c in containers}
        report["probes"]=core_probe()
        failures=[]
        for name,(container,_,_) in SERVICES.items():
            if report["runtime"][container]["state"]!="running": failures.append(name+":NOT_RUNNING")
            if report["runtime"][container]["health"]=="unhealthy": failures.append(name+":UNHEALTHY")
            probe=report["probes"].get(name,{})
            if probe.get("http")!=200: failures.append(name+":HEALTH_NOT_200")
        for name,container in INFRA.items():
            if report["runtime"][container]["state"]!="running": failures.append(name+":NOT_RUNNING")
            if report["runtime"][container]["health"]=="unhealthy": failures.append(name+":UNHEALTHY")
        for name in ("dashboard","runs","incidents","twin_summary"):
            if report["probes"].get(name,{}).get("http")!=200: failures.append(name+":API_NOT_200")
        report["failures"]=failures
        report["verdict"]="PASS" if not failures else "HOLD"
    except Exception as e:
        report["verdict"]="HOLD"
        report["error"]=type(e).__name__+":"+str(e)[:250]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(f"PLATFORM_GATE={report['verdict']} report={a.output}")
    for name,probe in report.get("probes",{}).items():
        print(f"  {name}: {probe.get('http',probe.get('error','UNKNOWN'))}")
    for f in report.get("failures",[]): print("  FAILURE:",f)
    return 0 if report["verdict"]=="PASS" else 2
if __name__=="__main__":
    sys.exit(main())
