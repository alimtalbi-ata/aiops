#!/usr/bin/env python3
"""Install read-only live use-case checks on Debian without a local Git checkout.

Fetch a specific immutable GitHub commit, validate Python before replacing,
preserve prior tools, schedule one managed cron, and produce a first receipt.
No Docker restart, ITSM POST, database mutation, or new Git credential.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request

REPO="alimtalbi-ata/aiops"
SOURCE="scripts/ops/live_usecase_qualification.py"
MARKER="# AIOPS2_LIVE_USECASE_12MIN_MANAGED"
def fetch_pinned(commit):
    url=f"https://raw.githubusercontent.com/{REPO}/{commit}/{SOURCE}"
    with urllib.request.urlopen(url,timeout=30) as response:
        data=response.read(2000001)
    if len(data)>2000000: raise RuntimeError("script too large")
    compile(data,url,"exec")
    return data

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--commit",required=True,help="40-char immutable source commit")
    p.add_argument("--no-cron",action="store_true")
    a=p.parse_args()
    if not re.fullmatch(r"[a-fA-F0-9]{40}",a.commit):
        p.error("commit must be 40 hex characters")
    data=fetch_pinned(a.commit.lower())
    root=Path.home()/"aiops2-audit-tools"
    receipts=Path.home()/"aiops2-release-receipts"
    root.mkdir(parents=True,exist_ok=True)
    receipts.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target=root/"live_usecase_qualification.py"
    if target.exists():
        (root/f"live_usecase_qualification.py.backup-{stamp}").write_bytes(target.read_bytes())
    with tempfile.NamedTemporaryFile(dir=root,prefix=".usecase-",delete=False) as handle:
        handle.write(data)
        stage=Path(handle.name)
    os.replace(stage,target)
    target.chmod(0o700)
    log=receipts/"usecase-cron.log"
    lock=receipts/"usecase.lock"
    wrapper=root/"live_usecase_12min.sh"
    wrapper.write_text(
        "#!/bin/sh\nset -u\numask 077\n"
        f'exec /usr/bin/flock -n "{lock}" /bin/sh -c '
        f"'"+f'/usr/bin/python3 "{target}" --output-dir "{receipts}" >> "{log}" 2>&1; '
        f'rc=$?; echo "gate_exit=$rc" >> "{log}"; exit 0'+"'\n")
    wrapper.chmod(0o700)
    status="SKIPPED"
    if not a.no_cron:
        old=subprocess.run(["crontab","-l"],capture_output=True,text=True)
        if old.returncode not in (0,1):
            raise RuntimeError("cannot inspect user crontab")
        lines=old.stdout.splitlines() if old.returncode==0 else []
        existing=[line for line in lines if MARKER in line]
        if len(existing)>1:
            raise RuntimeError("multiple managed cron entries; refusing changes")
        line=f"2,14,26,38,50 * * * * {wrapper} {MARKER}"
        lines=[line if MARKER in entry else entry for entry in lines]
        if not existing: lines.append(line)
        if not existing or existing[0]!=line:
            changed=subprocess.run(["crontab","-"],input="\n".join(lines)+"\n",
                                   capture_output=True,text=True)
            if changed.returncode:
                raise RuntimeError("crontab install failed: "+changed.stderr[-200:])
        status="INSTALLED" if not existing else "ALREADY_INSTALLED"
    probe=subprocess.run([sys.executable,str(target),"--output-dir",str(receipts)],
                         capture_output=True,text=True,timeout=240)
    receipt={"schema":"aiops2-usecase-installer-v2","utc":stamp,"source_commit":a.commit.lower(),
             "source_path":SOURCE,"installed_path":str(target),"cron":status,
             "initial_exit":probe.returncode,"initial_output":probe.stdout[-500:],
             "initial_error":probe.stderr[-300:],"production_containers_changed":False}
    out=receipts/f"usecase-install-{stamp}.json"
    out.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"receipt":str(out),"cron":status,
                      "initial_gate_exit":probe.returncode,"source_commit":a.commit.lower()},indent=2))
    return 0 if probe.returncode in (0,2) else 1
if __name__=="__main__":
    raise SystemExit(main())
