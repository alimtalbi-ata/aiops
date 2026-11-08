#!/usr/bin/env python3
"""AIOps2 Debian release intake: fail-closed, read-only baseline stage.

Reads a pinned GitHub raw file, verifies SHA256, syntax-checks it, atomically
installs the audit tool, runs the platform-wide smoke gate and writes a receipt.
No Docker restarts, DB mutations, or automatic promotion to production.
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

SOURCE="https://raw.githubusercontent.com/alimtalbi-ata/aiops/audit/preserve-debian-48h-20261108/scripts/ops/platform_readiness_gate.py"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sha256",required=True)
    p.add_argument("--output-dir",type=Path,default=Path.home()/"aiops2-release-receipts")
    a=p.parse_args()
    if len(a.sha256)!=64 or any(c not in "0123456789abcdef" for c in a.sha256.lower()):
        p.error("invalid SHA256")
    a.output_dir.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tool_dir=Path.home()/"aiops2-audit-tools"
    tool_dir.mkdir(parents=True,exist_ok=True)
    destination=tool_dir/"platform_readiness_gate.py"
    data=urllib.request.urlopen(SOURCE,timeout=25).read(2_000_000)
    digest=hashlib.sha256(data).hexdigest()
    if digest!=a.sha256.lower():
        raise RuntimeError("SHA256 mismatch; nothing installed")
    with tempfile.NamedTemporaryFile(prefix=".platform_",suffix=".py",dir=tool_dir,delete=False) as tmp:
        tmp.write(data)
        stage=Path(tmp.name)
    try:
        compile(data,str(stage),"exec")
        if destination.exists():
            shutil.copy2(destination,tool_dir/f"platform_readiness_gate.py.backup-{stamp}")
        os.replace(stage,destination)
    finally:
        stage.unlink(missing_ok=True)
    report=a.output_dir/f"platform-readiness-{stamp}.json"
    result=subprocess.run([sys.executable,str(destination),"--output",str(report)],
                          capture_output=True,text=True,timeout=150)
    receipt={"schema":"aiops2-release-intake-v1","utc":stamp,
             "host":os.uname().nodename,"source":SOURCE,"sha256":digest,
             "installed":str(destination),"report":str(report),
             "exit_code":result.returncode,"stdout":result.stdout[-4000:],
             "stderr":result.stderr[-1000:],
             "container_restart":False,"database_write":False,"production_deploy":False}
    receipt_file=a.output_dir/f"release-intake-{stamp}.json"
    receipt_file.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"receipt":str(receipt_file),"report":str(report),
                      "gate_exit":result.returncode,"installed_sha256":digest},indent=2))
    print(result.stdout)
    return 0 if result.returncode in (0,2) else 1
if __name__=="__main__":
    sys.exit(main())
