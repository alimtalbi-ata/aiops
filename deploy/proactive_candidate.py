#!/usr/bin/env python3
"""Read-only candidate discovery; durable handoff, never deploys by itself."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = "alimtalbi-ata/aiops"
REQUIRED = frozenset(("core-postgres-noc-real-integration","policy-and-static","grafana-real-integration","offline-e2e","synthetic-contracts","synthetic-noc","tenant-postgres-isolation","contract","offline-readiness","ephemeral-portal-chromium","portal-tenant-actor-boundary","offline"))
def gh(path):
    return json.loads(subprocess.check_output(["gh","api","--method","GET",path],timeout=30))
def classify(pr, checks):
    if pr["state"] != "open" or not re.fullmatch(r"[0-9a-f]{40}",pr["head"]["sha"]):
        return "INELIGIBLE"
    if pr["head"]["repo"]["full_name"] != REPO:
        return "INELIGIBLE"
    latest = {}
    for c in sorted(checks,key=lambda c:c["id"]):
        if c.get("head_sha") == pr["head"]["sha"]:
            latest[c["name"]] = c
    if any(latest[n].get("conclusion") in {"failure","cancelled","timed_out","action_required"} for n in REQUIRED & latest.keys()):
        return "CI_BLOCKED"
    if all(latest.get(n,{}).get("conclusion") == "success" for n in REQUIRED):
        return "BUILD_ELIGIBLE"
    return "CI_PENDING"
def atomic(path, value):
    fd,tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,"w") as f:
            json.dump(value,f,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
def main():
    os.umask(0o077)
    state=Path.home()/".local/state/aiops2-proactive"
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (state/"lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        target=state/"candidate.json"
        # Withdraw prior handoff before network operations; errors fail closed.
        atomic(target,{"state":"CHECKING","deploy_authorized":False})
        try:
            pr=gh(f"repos/{REPO}/pulls/818")
            sha=pr["head"]["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}",sha): raise ValueError("invalid SHA")
            checks=gh(f"repos/{REPO}/commits/{sha}/check-runs?per_page=100")
            if checks["total_count"]>100: raise ValueError("check pagination required")
            result={"sha":sha,"pr":818,"state":classify(pr,checks["check_runs"]),"deploy_authorized":False}
        except Exception as exc:
            result={"state":"DISCOVERY_ERROR","error_type":type(exc).__name__,"deploy_authorized":False}
        result["observed_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
        atomic(target,result)
        print(json.dumps(result))
if __name__ == "__main__": main()
