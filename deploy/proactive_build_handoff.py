#!/usr/bin/env python3
"""Bounded handoff, never execute candidate code or authorize deployment."""
import datetime as dt
import fcntl
import json
from pathlib import Path
import re
import subprocess
import os
from proactive_candidate import atomic, REPO

def main():
    os.umask(0o077)
    root=Path.home()/".local/state/aiops2-proactive"
    with (root/"handoff.lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        d=json.loads((root/"candidate.json").read_text())
        age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(d["observed_at"])).total_seconds()
        sha=d.get("sha","")
        if not (0<=age<=120 and d.get("state")=="BUILD_ELIGIBLE" and d.get("pr")==818 and d.get("deploy_authorized") is False and re.fullmatch(r"[0-9a-f]{40}",sha)): return
        receipt=root/f"build-handoff-{sha}.json"
        if receipt.exists(): return
        body=f"[CENTRAL][BUILD_QUALIFICATION:{sha}] Team C: qualify isolated build for PR #818 at exact SHA; publish image digest and provenance. Team D: independently verify evidence and prepare desktop 7770 acceptance. On failure open corrective task; on success request protected promotion according to policy. No runtime deployment authorized by this task."
        atomic(receipt,{"status":"STARTED","sha":sha})
        try:
            subprocess.run(["gh","issue","comment","804","--repo",REPO,"--body",body],check=True,timeout=30,capture_output=True)
        except (OSError,subprocess.SubprocessError):
            atomic(receipt,{"status":"PUBLICATION_UNCERTAIN","sha":sha})
            raise
        atomic(receipt,{"status":"PUBLISHED","sha":sha})
if __name__=="__main__": main()
