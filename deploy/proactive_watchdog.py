#!/usr/bin/env python3
"""Report discovery state transitions; no build or deployment side effects."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from proactive_candidate import atomic, REPO

def main():
    os.umask(0o077)
    root=Path.home()/".local/state/aiops2-proactive"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (root/"watchdog.lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        try:
            data=json.loads((root/"candidate.json").read_text())
            age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(data["observed_at"])).total_seconds()
            if not 0<=age<=180: raise ValueError("stale")
            state=data["state"]
            if state not in {"BUILD_ELIGIBLE","CI_PENDING","CI_BLOCKED","INELIGIBLE","DISCOVERY_ERROR"}: raise ValueError("invalid state")
            sha=data.get("sha","")
            if sha and not re.fullmatch(r"[0-9a-f]{40}",sha): raise ValueError("invalid sha")
        except (OSError,ValueError,KeyError,TypeError):
            state,sha="DISCOVERY_STALE",""
        marker=hashlib.sha256(f"{state}:{sha}".encode()).hexdigest()[:24]
        receipt=root/f"reported-{marker}.json"
        if receipt.exists(): return
        body=f"AIOPS2 proactive observation: {state}; SHA={sha or 'unknown'}; marker={marker}. No deployment attestation."
        # Reserve before publishing; ambiguous failures are visible locally, not retried blindly.
        atomic(receipt,{"status":"STARTED","marker":marker})
        try:
            subprocess.run(["gh","issue","comment","804","--repo",REPO,"--body",body],check=True,timeout=30,capture_output=True)
        except (OSError,subprocess.SubprocessError):
            atomic(receipt,{"status":"PUBLICATION_UNCERTAIN","marker":marker})
            raise
        atomic(receipt,{"status":"PUBLISHED","marker":marker})
if __name__=="__main__": main()
