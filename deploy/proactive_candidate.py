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
EXPECTED_CHECK_APP = "github-actions"
REQUIRED = frozenset(("core-postgres-noc-real-integration","policy-and-static","grafana-real-integration","offline-e2e","synthetic-contracts","synthetic-noc","tenant-postgres-isolation","contract","offline-readiness","ephemeral-portal-chromium","portal-tenant-actor-boundary","offline"))

def gh(path):
    return json.loads(subprocess.check_output(["gh","api","--method","GET",path],timeout=30))

def fetch_check_runs(sha):
    # --slurp preserves every page returned by --paginate; never accept a
    # partial first page as a complete qualification snapshot.
    raw=subprocess.check_output(
        ["gh","api","--paginate","--slurp",f"repos/{REPO}/commits/{sha}/check-runs?per_page=100&filter=all"],
        timeout=60,
    )
    pages=json.loads(raw)
    if not isinstance(pages,list) or not pages or len(pages)>20:
        raise ValueError("invalid or excessive check-run pagination")
    total=None
    checks=[]
    seen=set()
    for page in pages:
        if not isinstance(page,dict) or not isinstance(page.get("check_runs"),list):
            raise ValueError("invalid check-run page")
        page_total=page.get("total_count")
        if type(page_total) is not int or page_total<0 or (total is not None and total!=page_total):
            raise ValueError("inconsistent check-run total")
        total=page_total
        for check in page["check_runs"]:
            if not isinstance(check,dict) or type(check.get("id")) is not int or check["id"] in seen:
                raise ValueError("invalid or duplicate check-run id")
            seen.add(check["id"])
            checks.append(check)
    if total is None or total!=len(checks):
        raise ValueError("incomplete check-run pagination")
    return checks

def classify(pr, checks):
    if pr.get("state") != "open" or not re.fullmatch(r"[0-9a-f]{40}",pr.get("head",{}).get("sha","")):
        return "INELIGIBLE"
    if not pr.get("head",{}).get("repo") or pr["head"]["repo"].get("full_name") != REPO:
        return "INELIGIBLE"
    latest = {}
    for c in sorted(checks,key=lambda c:c.get("id",0)):
        if c.get("head_sha") == pr["head"]["sha"] and c.get("app",{}).get("slug") == EXPECTED_CHECK_APP:
            latest[c["name"]] = c
    if any(latest[n].get("conclusion") in {"failure","cancelled","timed_out","action_required"} for n in REQUIRED & latest.keys()):
        return "CI_BLOCKED"
    if all(latest.get(n,{}).get("conclusion") == "success" and latest[n].get("status") == "completed" for n in REQUIRED):
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
        dfd=os.open(path.parent,os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def main():
    os.umask(0o077)
    state=Path.home()/".local/state/aiops2-proactive"
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Candidate discovery and watchdog share one flock. The watchdog skips while
    # discovery is running, so CHECKING cannot be mistaken for a broken observer.
    with (state/"lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        target=state/"candidate.json"
        atomic(target,{"state":"CHECKING","observed_at":now(),"deploy_authorized":False})
        try:
            pr=gh(f"repos/{REPO}/pulls/818")
            sha=pr["head"]["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}",sha): raise ValueError("invalid SHA")
            checks=fetch_check_runs(sha)
            result={"sha":sha,"pr":818,"state":classify(pr,checks),"deploy_authorized":False}
        except Exception as exc:
            result={"state":"DISCOVERY_ERROR","error_type":type(exc).__name__,"deploy_authorized":False}
        result["observed_at"]=now()
        atomic(target,result)
        print(json.dumps(result))
if __name__ == "__main__": main()
