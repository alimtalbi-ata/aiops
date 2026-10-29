#!/usr/bin/env python3
"""ACME demo day read-only readiness: never launches a run or modifies services."""
import argparse,json,subprocess,urllib.request
from datetime import datetime,timezone
from pathlib import Path

SERVICES=("core","portal","twin","copilot","evidence","intelligence","worker","policy")
def assess(health, urls, assets):
    checks=[]
    for svc in SERVICES:
        status=health.get(svc,"missing")
        checks.append({"name":"container:"+svc,"status":"PASS" if status=="healthy" else "FAIL","detail":status})
    for name,code in urls.items():
        checks.append({"name":"http:"+name,"status":"PASS" if code==200 else "FAIL","detail":code})
    missing=sorted(set(assets["required"])-set(assets["available"]))
    checks.append({"name":"acme:cmdb-required","status":"PASS" if not missing else "FAIL","detail":{"missing":missing}})
    return checks

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--portal",default="http://10.79.94.202:17777")
    p.add_argument("--output",type=Path,default=Path("/tmp/acme-demo-readiness.json"))
    args=p.parse_args()
    svc={}
    for item in SERVICES:
        name="aiops2-rebuild-"+item
        result=subprocess.run(["docker","inspect","-f","{{.State.Health.Status}}",name],
                              capture_output=True,text=True,timeout=8)
        svc[item]=result.stdout.strip() if result.returncode==0 else "missing"
    urls={}
    for path in ("/health","/timeline","/qualification-lab","/copilot","/demo-studio"):
        try:
            with urllib.request.urlopen(args.portal.rstrip("/")+path,timeout=6) as response:
                urls[path]=response.status
        except Exception:
            urls[path]=None
    # Check the actual CMDB using the already-running Twin container.
    cmd=["docker","exec","aiops2-rebuild-twin","python","-c",
         "import json,urllib.request;print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:811/api/twin/nodes',timeout=5))))"]
    try:
        raw=subprocess.run(cmd,capture_output=True,text=True,timeout=12,check=True)
        available=[x.get("node_id") for x in json.loads(raw.stdout).get("items",[])]
    except Exception:
        available=[]
    required=("ACME-SAN-FABRIC-A","ACME-SAN-FABRIC-B","ACME-STO-PURE01",
              "ACME-SRV-RHEL01","ACME-SVC-PAYMENTS")
    checks=assess(svc,urls,{"required":required,"available":available})
    report={"scope":"ACME","mode":"READ_ONLY","generated_at":datetime.now(timezone.utc).isoformat(),
            "status":"READY" if all(x["status"]=="PASS" for x in checks) else "NOT_READY",
            "checks":checks,
            "qualification_limits":["Healthchecks do not prove model diagnosis quality.",
             "A successful demo may terminate BLOCKED when Critic rejects unsafe inference.",
             "GLPI, HITL and multi-turn LLM chat are not claimed qualified here."]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["status"]=="READY" else 2

if __name__=="__main__":
    raise SystemExit(main())
