#!/usr/bin/env python3
"""Install a 12-minute read-only use-case gate using existing GitHub remote.

No production changes. One managed cron entry, backup of replaced audit
scripts, pinned Git commit, and first qualification receipt. Never runs deploy.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO="alimtalbi-ata/aiops"
BRANCH="audit/preserve-debian-48h-20261108"
FILES=("scripts/ops/live_usecase_qualification.py",
       "scripts/ops/publish_platform_evidence.py")
MARKER="# AIOPS2_LIVE_USECASE_12MIN_MANAGED"

def call(args, **kwargs):
    p=subprocess.run(args,text=True,capture_output=True,timeout=120,**kwargs)
    if p.returncode:
        raise RuntimeError(f"{args[0]} returned {p.returncode}: {p.stderr[-150:]}")
    return p.stdout

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--checkout",type=Path,default=Path.home()/"aiops")
    ap.add_argument("--commit",required=True,help="Full audited commit SHA")
    args=ap.parse_args()
    if len(args.commit)!=40 or any(x not in "0123456789abcdef" for x in args.commit.lower()):
        ap.error("commit must be 40 hex characters")
    checkout=args.checkout.resolve()
    remote=call(["git","remote","get-url","origin"],cwd=checkout).strip()
    if not ("github.com" in remote and REPO in remote):
        raise RuntimeError("Git origin not the expected AIOps2 repository")
    call(["git","fetch","origin",BRANCH],cwd=checkout)
    head=call(["git","rev-parse","FETCH_HEAD"],cwd=checkout).strip()
    if head!=args.commit.lower():
        raise RuntimeError("branch moved; refuse unreviewed script revision")
    root=Path.home()/"aiops2-audit-tools"
    receipts=Path.home()/"aiops2-release-receipts"
    root.mkdir(parents=True,exist_ok=True)
    receipts.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for source in FILES:
        raw=call(["git","show",head+":"+source],cwd=checkout)
        compile(raw,source,"exec")
        dest=root/Path(source).name
        if dest.exists():
            (root/(dest.name+".backup-"+stamp)).write_bytes(dest.read_bytes())
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f:
            f.write(raw.encode())
            stage=Path(f.name)
        os.replace(stage,dest)
        dest.chmod(0o700)
    wrapper=root/"live_usecase_12min.sh"
    qualifier=root/"live_usecase_qualification.py"
    publisher=root/"publish_platform_evidence.py"
    log=receipts/"usecase-cron.log"
    lock=receipts/"usecase.lock"
    # Run publisher even when qualification correctly returns HOLD (exit 2).
    shell=f"""#!/bin/sh
set -u
umask 077
exec /usr/bin/flock -n "{lock}" /bin/sh -c '
  /usr/bin/python3 "{qualifier}" --output-dir "{receipts}" >> "{log}" 2>&1
  gate_rc=$?
  /usr/bin/python3 "{publisher}" --checkout "{checkout}" --reports "{receipts}" >> "{log}" 2>&1
  push_rc=$?
  echo "gate_exit=$gate_rc publish_exit=$push_rc" >> "{log}"
  exit $push_rc
'
"""
    wrapper.write_text(shell)
    wrapper.chmod(0o700)
    current=subprocess.run(["crontab","-l"],capture_output=True,text=True)
    if current.returncode not in (0,1):
        raise RuntimeError("cannot read crontab")
    entries=current.stdout.splitlines() if current.returncode==0 else []
    managed=[x for x in entries if MARKER in x]
    if len(managed)>1:
        raise RuntimeError("duplicate managed entries; refuse to modify crontab")
    line=f"2,14,26,38,50 * * * * {wrapper} {MARKER}"
    entries=[line if MARKER in x else x for x in entries]
    if not managed: entries.append(line)
    if not managed or managed[0]!=line:
        call(["crontab","-"],input="\n".join(entries)+"\n")
    # Run once, but HOLD (exit=2) is an expected result, not install failure.
    probe=subprocess.run([sys.executable,str(root/"live_usecase_qualification.py"),
        "--output-dir",str(receipts)],capture_output=True,text=True,timeout=180)
    receipt={"schema":"aiops2-usecase-installer-v1","utc":stamp,"source_commit":head,
             "cron":line,"initial_exit":probe.returncode,
             "initial_output":probe.stdout[-500:],"production_modified":False}
    dest=receipts/f"usecase-install-{stamp}.json"
    dest.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"receipt":str(dest),"cron":"INSTALLED","initial_gate_exit":probe.returncode,
                      "source_commit":head},indent=2))
    return 0 if probe.returncode in (0,2) else 1
if __name__=="__main__":
    raise SystemExit(main())
