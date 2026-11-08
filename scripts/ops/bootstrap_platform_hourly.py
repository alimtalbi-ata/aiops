#!/usr/bin/env python3
"""AIOps2 bootstrap: read-only hourly platform evidence, no production mutation.

One-time host execution. Fetches audited gate at pinned SHA, runs once, and
installs a user crontab line. No Docker restart, DB writes or deployment.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

BASE="https://raw.githubusercontent.com/alimtalbi-ata/aiops/audit/preserve-debian-48h-20261108"
SOURCE=BASE+"/scripts/ops/platform_readiness_gate.py"
def call(argv,**kw):
    return subprocess.run(argv,text=True,capture_output=True,**kw)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gate-sha256",required=True)
    p.add_argument("--no-cron",action="store_true")
    a=p.parse_args()
    if len(a.gate_sha256)!=64 or any(c not in "0123456789abcdef" for c in a.gate_sha256.lower()):
        p.error("invalid gate SHA256")
    home=Path.home()
    tools=home/"aiops2-audit-tools"
    receipts=home/"aiops2-release-receipts"
    tools.mkdir(parents=True,exist_ok=True)
    receipts.mkdir(parents=True,exist_ok=True)
    data=urllib.request.urlopen(SOURCE,timeout=30).read(2_000_000)
    digest=hashlib.sha256(data).hexdigest()
    if digest!=a.gate_sha256.lower(): raise RuntimeError("gate SHA256 mismatch; no changes")
    compile(data,SOURCE,"exec")
    target=tools/"platform_readiness_gate.py"
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if target.exists():
        (tools/f"platform_readiness_gate.py.backup-{stamp}").write_bytes(target.read_bytes())
    with tempfile.NamedTemporaryFile(dir=tools,prefix=".platform_",delete=False) as f:
        f.write(data)
        staged=Path(f.name)
    os.replace(staged,target)
    # Install a dedicated cron wrapper, keeping all reports local and immutable.
    wrapper=tools/"platform_hourly.sh"
    script=f"""#!/bin/sh
set -u
umask 077
mkdir -p "{receipts}"
exec /usr/bin/flock -n "{receipts}/platform.lock" /bin/sh -c '
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  /usr/bin/python3 "{target}" --output "{receipts}/platform-$stamp.json" > "{receipts}/platform-$stamp.log" 2>&1
  rc=$?
  echo "exit_code=$rc" >> "{receipts}/platform-$stamp.log"
  exit 0
'
"""
    wrapper.write_text(script)
    wrapper.chmod(0o700)
    initial=call([str(wrapper)],timeout=180)
    if initial.returncode!=0: raise RuntimeError("initial platform gate invocation failed: "+initial.stderr[-300:])
    cron_status="NOT_REQUESTED"
    if not a.no_cron:
        existing=call(["crontab","-l"])
        if existing.returncode not in (0,1):
            raise RuntimeError("cannot inspect user crontab")
        current=existing.stdout if existing.returncode==0 else ""
        marker="# AIOPS2_PLATFORM_EVIDENCE_MANAGED"
        if marker not in current:
            new=current.rstrip("\n")+"\n"+f"17 * * * * {wrapper} {marker}"+"\n"
            applied=call(["crontab","-"],input=new)
            if applied.returncode: raise RuntimeError("crontab update failed: "+applied.stderr[:200])
            cron_status="INSTALLED"
        else: cron_status="ALREADY_INSTALLED"
    receipt={"schema":"aiops2-platform-bootstrap-v1","utc":stamp,"host":os.uname().nodename,
             "gate_sha256":digest,"gate_path":str(target),"wrapper":str(wrapper),
             "cron":cron_status,"initial_wrapper_exit":initial.returncode,
             "report_dir":str(receipts),"production_containers_changed":False,
             "github_push_configured":False}
    out=receipts/f"bootstrap-{stamp}.json"
    out.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"receipt":str(out),"report_dir":str(receipts),"cron":cron_status,
                      "gate_sha256":digest},indent=2))
    return 0
if __name__=="__main__":
    sys.exit(main())
