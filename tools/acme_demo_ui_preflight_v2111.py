#!/usr/bin/env python3
"""Read-only client-demo HTTP preflight. No incidents, writes, or credentials."""
import argparse,json,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path

PAGES=("/health","/policy-story","/acme-stories","/demo-studio",
       "/qualification-lab","/copilot",
       "/timeline?run_id=RUN-A4449145A6E377FF")

def probe(base,opener=urllib.request.urlopen):
    result=[]
    for path in PAGES:
        try:
            with opener(base.rstrip("/")+path,timeout=8) as response:
                status=response.status
                content=response.read(1024*1024).decode("utf-8","replace")
            valid=status==200
            if path=="/policy-story":
                valid=valid and all(x in content for x in ("story-next","story-reset","STOP_AUTO","FICTIF / SANS EFFET"))
            result.append({"path":path,"http_status":status,"status":"PASS" if valid else "FAIL"})
        except (urllib.error.URLError,TimeoutError,OSError) as error:
            result.append({"path":path,"http_status":None,"status":"FAIL","error":type(error).__name__})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--portal",default="http://10.79.94.202:17777")
    p.add_argument("--output",type=Path,default=Path("/tmp/acme-demo-ui-preflight.json"))
    a=p.parse_args()
    checks=probe(a.portal)
    report={"scope":"ACME","mode":"READ_ONLY","timestamp":datetime.now(timezone.utc).isoformat(),
            "status":"PASS" if all(x["status"]=="PASS" for x in checks) else "FAIL",
            "checks":checks,
            "limitations":["HTTP and HTML checks cannot prove browser JavaScript interaction.",
                           "No live model inference, GLPI action or remediation is exercised."]}
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report["status"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
