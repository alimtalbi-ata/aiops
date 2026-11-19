#!/usr/bin/env python3
"""Bounded handoff; revalidates source HEAD and never authorizes deployment."""
import datetime as dt
import fcntl
import json
from pathlib import Path
import re
import subprocess
import os
from proactive_candidate import atomic, REPO

EXPECTED_AUTHOR=os.environ.get("AIOPS2_GH_ACTOR","alimtalbi-ata")

def current_pr_head():
    raw=subprocess.check_output(["gh","api","--method","GET",f"repos/{REPO}/pulls/818"],timeout=30,text=True)
    pr=json.loads(raw)
    if pr.get("state")!="open" or not pr.get("head",{}).get("repo") or pr["head"]["repo"].get("full_name")!=REPO:
        raise ValueError("PR is not eligible")
    return pr["head"]["sha"]

def reconcile(receipt, marker, sha):
    raw=subprocess.run(["gh","api","--paginate","--slurp",f"repos/{REPO}/issues/804/comments?per_page=100"],check=True,timeout=30,capture_output=True,text=True)
    pages=json.loads(raw.stdout)
    if not isinstance(pages,list) or any(not isinstance(page,list) for page in pages):
        raise ValueError("invalid paginated comments response")
    matches=[item for page in pages for item in page if item.get("body","").startswith(marker)]
    if len(matches)==1 and matches[0].get("user",{}).get("login")==EXPECTED_AUTHOR:
        atomic(receipt,{"status":"PUBLISHED","sha":sha,"marker":marker,"comment_id":matches[0]["id"],"reconciled":True})
    elif len(matches)>1:
        atomic(receipt,{"status":"DUPLICATE_ESCALATION","sha":sha,"marker":marker,"match_count":len(matches)})
    elif len(matches)==1:
        atomic(receipt,{"status":"AUTHOR_CONFLICT","sha":sha,"marker":marker,"comment_id":matches[0].get("id")})
    else:
        atomic(receipt,{"status":"PUBLICATION_UNCERTAIN","sha":sha,"marker":marker,"match_count":0,"reconciled_at":dt.datetime.now(dt.timezone.utc).isoformat()})

def main():
    os.umask(0o077)
    root=Path.home()/".local/state/aiops2-proactive"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (root/"lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        d=json.loads((root/"candidate.json").read_text())
        age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(d["observed_at"])).total_seconds()
        sha=d.get("sha","")
        if not (0<=age<=120 and d.get("state")=="BUILD_ELIGIBLE" and d.get("pr")==818 and d.get("deploy_authorized") is False and re.fullmatch(r"[0-9a-f]{40}",sha)): return
        receipt=root/f"build-handoff-{sha}.json"
        marker=f"[CENTRAL][BUILD_QUALIFICATION:{sha}]"
        if receipt.exists():
            previous=json.loads(receipt.read_text())
            if previous.get("status")=="PUBLISHED": return
            if previous.get("status") not in {"STARTED","PUBLICATION_UNCERTAIN"}: return
            reconcile(receipt,marker,sha)
            return
        # Re-read GitHub PR head immediately before reserving/publishing the task.
        if current_pr_head()!=sha:
            atomic(receipt,{"status":"OBSOLETE_SHA","sha":sha,"deploy_authorized":False})
            return
        body=f"{marker}\nTeam C: qualify isolated build for PR #818 at exact SHA; publish image provenance. Team D: independently verify evidence. No runtime deployment or promotion authorized by this task."
        atomic(receipt,{"status":"STARTED","sha":sha,"marker":marker,"deploy_authorized":False})
        try:
            subprocess.run(["gh","issue","comment","804","--repo",REPO,"--body",body],check=True,timeout=30,capture_output=True)
        except (OSError,subprocess.SubprocessError):
            atomic(receipt,{"status":"PUBLICATION_UNCERTAIN","sha":sha,"marker":marker,"deploy_authorized":False})
            raise
        atomic(receipt,{"status":"PUBLISHED","sha":sha,"marker":marker,"deploy_authorized":False})
if __name__=="__main__": main()
