#!/usr/bin/env python3
"""Publish the latest AIOps2 platform evidence to existing GitHub ops branch.

Uses the already-configured Git remote in the Debian checkout. Does not alter
the active checkout, deployed branch, cron, Docker or databases. Fail closed.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile

BRANCH="ops/debian-runtime-reports"
ALLOWED={"schema","utc","read_only","runtime","probes","failures","verdict","error"}
def run(args,cwd=None,timeout=45,check=True):
    p=subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode: raise RuntimeError(f"{args[0]} failed (exit {p.returncode})")
    return p
def sanitize(source):
    data=json.loads(source.read_text())
    if data.get("schema")!="aiops2-platform-readiness-v1" or data.get("read_only") is not True:
        raise ValueError("unexpected platform report schema")
    clean={k:v for k,v in data.items() if k in ALLOWED}
    # Only safe health data: avoid network configuration, raw labels, env, secrets.
    runtime={}
    for name,info in clean.get("runtime",{}).items():
        runtime[name]={k:info.get(k) for k in ("image","image_id","state","health","networks")}
    clean["runtime"]=runtime
    return clean
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkout",type=Path,default=Path.home()/"aiops")
    p.add_argument("--reports",type=Path,default=Path.home()/"aiops2-release-receipts")
    a=p.parse_args()
    reports=sorted(a.reports.glob("platform-*.json"),key=lambda x:x.stat().st_mtime)
    data=sanitize(reports[-1]) if reports else None
    usecases=sorted(a.reports.glob("usecase-summary-*.json"),key=lambda x:x.stat().st_mtime)
    usecase=json.loads(usecases[-1].read_text()) if usecases else None
    if usecase is not None:
        if usecase.get("schema")!="aiops2-live-usecase-qualification-v1" or usecase.get("read_only") is not True:
            raise ValueError("unexpected use-case schema")
        usecase={k:usecase.get(k) for k in ("schema","utc","run_id","read_only","verdict","checks","blocking","interpretation")}
    if data is None and usecase is None: raise RuntimeError("no platform or usecase report found")
    checkout=a.checkout.resolve()
    if not (checkout/".git").exists(): raise RuntimeError("existing Git checkout not found")
    remote=run(["git","remote","get-url","origin"],cwd=checkout).stdout.strip()
    if not ("github.com" in remote and "alimtalbi-ata/aiops" in remote):
        raise RuntimeError("origin is not the expected AIOps2 repository")
    run(["git","fetch","origin",BRANCH],cwd=checkout,timeout=90)
    with tempfile.TemporaryDirectory(prefix="aiops2-report-") as td:
        work=Path(td)/"work"
        run(["git","worktree","add","--detach",str(work),"FETCH_HEAD"],cwd=checkout)
        try:
            target=work/"ops/debian-reports/SRV-DEB-05/latest-platform.json"
            target.parent.mkdir(parents=True,exist_ok=True)
            encoded=json.dumps(data,indent=2,ensure_ascii=False)+"\n"
            if target.exists() and target.read_text()==encoded:
                print("NO_CHANGE: existing GitHub report matches latest Debian report")
                return 0
            target.write_text(encoded)
            run(["git","add","--",str(target.relative_to(work))],cwd=work)
            run(["git","-c","user.name=AIOps2 Debian Reporter",
                 "-c","user.email=aiops2-reporter@users.noreply.github.com",
                 "commit","-m","ops: refresh SRV-DEB-05 platform readiness"],cwd=work)
            # Lease protects the remote branch from overwriting concurrent updates.
            run(["git","push","origin","HEAD:refs/heads/"+BRANCH],cwd=work,timeout=90)
            print("PUBLISHED:",BRANCH,target.relative_to(work))
        finally:
            run(["git","worktree","remove","--force",str(work)],cwd=checkout,check=False)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
