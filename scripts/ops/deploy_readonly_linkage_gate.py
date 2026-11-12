#!/usr/bin/env python3
"""Deploy the audited, read-only AIOps2 linkage gate on Debian; preserve history.

Run on SRV-DEB-05 as aiops. No container restart, database write or ITSM POST.
Produces a host receipt; optionally commits it to a separate ops branch.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = "alimtalbi-ata/aiops"
BRANCH = "audit/preserve-debian-48h-20261108"
FILE = "scripts/ops/run_linkage_gate.py"
URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{FILE}"
RUN = "RUN-8CA56A39E58944F1"

def call(cmd, **kwargs):
    return subprocess.run(cmd, check=True, text=True, **kwargs)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-sha256", required=True, help="Pinned SHA256 of audited script")
    p.add_argument("--run-id", default=RUN)
    p.add_argument("--observed-glpi-ticket", type=int, default=201)
    p.add_argument("--push-receipt", action="store_true",
                   help="Opt in: commit receipt to existing ops/debian-runtime-reports checkout")
    p.add_argument("--repo-checkout", type=Path, default=Path.home() / "aiops")
    a = p.parse_args()
    if len(a.expected_sha256)!=64 or any(x not in "0123456789abcdef" for x in a.expected_sha256.lower()):
        p.error("expected-sha256 must be a 64-character hex digest")
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root=Path.home()/"aiops2-audit-tools"
    root.mkdir(parents=True,exist_ok=True)
    target=root/"run_linkage_gate.py"
    with urllib.request.urlopen(URL,timeout=25) as response:
        data=response.read(2_000_000)
    digest=hashlib.sha256(data).hexdigest()
    if digest!=a.expected_sha256.lower():
        raise RuntimeError("Source digest mismatch; refused deployment")
    with tempfile.NamedTemporaryFile(prefix=".run_linkage_",suffix=".py",dir=root,delete=False) as tmp:
        tmp.write(data)
        staged=Path(tmp.name)
    try:
        call([sys.executable,"-m","py_compile",str(staged)])
        backup=None
        if target.exists():
            backup=root/f"run_linkage_gate.py.backup-{stamp}"
            shutil.copy2(target,backup)
        os.replace(staged,target)
    finally:
        staged.unlink(missing_ok=True)
    report=Path.home()/f"aiops2-run-linkage-{stamp}.json"
    command=[sys.executable,str(target),"--run-id",a.run_id,
             "--observed-glpi-ticket",str(a.observed_glpi_ticket),"--output",str(report)]
    execution=subprocess.run(command,text=True,capture_output=True,timeout=120)
    receipt={"schema":"aiops2-debian-deployment-receipt-v1","timestamp_utc":stamp,
             "host":os.uname().nodename,"component":"read-only-linkage-gate",
             "source_branch":BRANCH,"source_path":FILE,"source_sha256":digest,
             "installed_path":str(target),"backup_path":str(backup) if backup else None,
             "run_id":a.run_id,"report_path":str(report),"gate_exit_code":execution.returncode,
             "gate_stdout":execution.stdout[-3000:],"gate_stderr":execution.stderr[-1000:],
             "production_containers_changed":False,"database_changed":False}
    receipt_path=Path.home()/f"aiops2-deployment-receipt-{stamp}.json"
    receipt_path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"receipt":str(receipt_path),"report":str(report),
                      "gate_exit":execution.returncode,"installed_sha256":digest},indent=2))
    print(execution.stdout)
    if a.push_receipt:
        # Deliberately not auto-pushing to avoid accidental production cron branch changes.
        print("Receipt push not performed: submit the receipt via the existing approved report pipeline.")
    return 0 if execution.returncode in (0,2) else 1

if __name__=="__main__":
    sys.exit(main())
