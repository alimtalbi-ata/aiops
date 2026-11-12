#!/usr/bin/env python3
"""Install read-only live use-case checks on Debian without a local Git checkout.

Fetch a specific immutable GitHub commit, validate Python before replacing,
preserve prior tools, never modify cron, and produce a first receipt.
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
    p.add_argument("--no-cron",action="store_true",help="compatibility flag; cron is always untouched")
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
    # Existing Debian scheduler is owned externally. Never create/replace a cron entry.
    status="SKIPPED"
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
    # HOLD must propagate to the caller, not masquerade as successful qualification.
    return 0 if probe.returncode == 0 else (2 if probe.returncode == 2 else 1)
if __name__=="__main__":
    raise SystemExit(main())
