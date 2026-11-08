#!/usr/bin/env python3
"""Publish sanitized read-only Debian platform/use-case receipts via existing Git remote."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

BRANCH="ops/debian-runtime-reports"
ROOT="ops/debian-reports/SRV-DEB-05"
def run(args,cwd=None,timeout=90,check=True):
    p=subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{args[0]} failed (exit {p.returncode})")
    return p

def sanitize_platform(source):
    data=json.loads(source.read_text())
    if data.get("schema")!="aiops2-platform-readiness-v1" or data.get("read_only") is not True:
        raise ValueError("unexpected platform schema")
    clean={k:data.get(k) for k in ("schema","utc","read_only","verdict","failures","probes","error")}
    clean["runtime"]={}
    for name,info in (data.get("runtime") or {}).items():
        clean["runtime"][name]={k:info.get(k) for k in ("image","image_id","state","health","networks")}
    return clean

def sanitize_usecase(source):
    data=json.loads(source.read_text())
    if data.get("schema")!="aiops2-live-usecase-qualification-v1" or data.get("read_only") is not True:
        raise ValueError("unexpected use-case schema")
    return {k:data.get(k) for k in ("schema","utc","run_id","read_only","verdict","checks","blocking","interpretation")}

def latest(folder,glob):
    items=sorted(folder.glob(glob),key=lambda x:x.stat().st_mtime)
    return items[-1] if items else None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkout",type=Path,default=Path.home()/"aiops")
    p.add_argument("--reports",type=Path,default=Path.home()/"aiops2-release-receipts")
    a=p.parse_args()
    sources=((latest(a.reports,"platform-*.json"),"latest-platform.json",sanitize_platform),
             (latest(a.reports,"usecase-summary-*.json"),"latest-usecase.json",sanitize_usecase))
    updates=[(dest,sanitize(src)) for src,dest,sanitize in sources if src is not None]
    if not updates: raise RuntimeError("no reports to publish")
    checkout=a.checkout.resolve()
    if not (checkout/".git").exists(): raise RuntimeError("existing Git checkout not found")
    remote=run(["git","remote","get-url","origin"],cwd=checkout).stdout.strip()
    if not ("github.com" in remote and "alimtalbi-ata/aiops" in remote):
        raise RuntimeError("unexpected origin")
    run(["git","fetch","origin",BRANCH],cwd=checkout)
    with tempfile.TemporaryDirectory(prefix="aiops2-report-") as td:
        work=Path(td)/"work"
        run(["git","worktree","add","--detach",str(work),"FETCH_HEAD"],cwd=checkout)
        try:
            changed=[]
            for name,data in updates:
                target=work/ROOT/name
                target.parent.mkdir(parents=True,exist_ok=True)
                encoded=json.dumps(data,indent=2,ensure_ascii=False)+"\n"
                if not target.exists() or target.read_text()!=encoded:
                    target.write_text(encoded)
                    changed.append(str(target.relative_to(work)))
            if not changed:
                print("NO_CHANGE")
                return 0
            run(["git","add","--",*changed],cwd=work)
            run(["git","-c","user.name=AIOps2 Debian Reporter",
                 "-c","user.email=aiops2-reporter@users.noreply.github.com",
                 "commit","-m","ops: update SRV-DEB-05 use-case qualification"],cwd=work)
            # Non-force push: concurrent writes fail safely rather than overwrite.
            run(["git","push","origin","HEAD:refs/heads/"+BRANCH],cwd=work)
            print("PUBLISHED:",",".join(changed))
        finally:
            run(["git","worktree","remove","--force",str(work)],cwd=checkout,check=False)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
