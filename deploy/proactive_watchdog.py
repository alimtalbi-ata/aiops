#!/usr/bin/env python3
"""Report discovery transitions with durable reconciliation of ambiguous GitHub posts."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from proactive_candidate import atomic, REPO

EXPECTED_AUTHOR=os.environ.get("AIOPS2_GH_ACTOR","alimtalbi-ata")

def comments_for(marker):
    raw=subprocess.run(["gh","api","--paginate","--slurp",f"repos/{REPO}/issues/804/comments?per_page=100"],check=True,timeout=30,capture_output=True,text=True)
    pages=json.loads(raw.stdout)
    if not isinstance(pages,list) or any(not isinstance(page,list) for page in pages):
        raise ValueError("invalid paginated comments response")
    return [item for page in pages for item in page if item.get("body","").startswith(marker)]

def reconcile(receipt, marker):
    matches=comments_for(marker)
    if len(matches)==1 and matches[0].get("user",{}).get("login")==EXPECTED_AUTHOR:
        atomic(receipt,{"status":"PUBLISHED","marker":marker,"comment_id":matches[0]["id"],"reconciled":True})
    elif len(matches)>1:
        atomic(receipt,{"status":"DUPLICATE_ESCALATION","marker":marker,"match_count":len(matches)})
    elif len(matches)==1:
        atomic(receipt,{"status":"AUTHOR_CONFLICT","marker":marker,"comment_id":matches[0].get("id")})
    else:
        previous=json.loads(receipt.read_text())
        attempts=int(previous.get("reconciliation_attempts",0))+1
        status="MANUAL_ESCALATION_REQUIRED" if attempts>=3 else "PUBLICATION_UNCERTAIN"
        atomic(receipt,{"status":status,"marker":marker,"match_count":0,"reconciliation_attempts":attempts,"reconciled_at":dt.datetime.now(dt.timezone.utc).isoformat()})

def main():
    os.umask(0o077)
    root=Path.home()/".local/state/aiops2-proactive"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Same lock as discovery: never inspect the transient CHECKING state mid-write.
    with (root/"lock").open("a") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        try:
            data=json.loads((root/"candidate.json").read_text())
            observed=dt.datetime.fromisoformat(data["observed_at"])
            age=(dt.datetime.now(dt.timezone.utc)-observed).total_seconds()
            if not 0<=age<=180: raise ValueError("stale or future observation")
            state=data["state"]
            if state=="CHECKING": return
            if state not in {"BUILD_ELIGIBLE","CI_PENDING","CI_BLOCKED","INELIGIBLE","DISCOVERY_ERROR"}: raise ValueError("invalid state")
            sha=data.get("sha","")
            if sha and not re.fullmatch(r"[0-9a-f]{40}",sha): raise ValueError("invalid sha")
        except (OSError,ValueError,KeyError,TypeError):
            state,sha="DISCOVERY_STALE",""
        marker_id=hashlib.sha256(f"{state}:{sha}".encode()).hexdigest()[:24]
        marker=f"[AIOPS2-WATCHDOG:{marker_id}]"
        receipt=root/f"reported-{marker_id}.json"
        if receipt.exists():
            previous=json.loads(receipt.read_text())
            if previous.get("status")=="PUBLISHED": return
            if previous.get("status") in {"STARTED","PUBLICATION_UNCERTAIN"}:
                reconcile(receipt,marker)
            return
        body=f"{marker}\nAIOPS2 proactive observation: {state}; SHA={sha or 'unknown'}. No deployment attestation."
        atomic(receipt,{"status":"STARTED","marker":marker})
        try:
            subprocess.run(["gh","issue","comment","804","--repo",REPO,"--body",body],check=True,timeout=30,capture_output=True)
        except (OSError,subprocess.SubprocessError):
            atomic(receipt,{"status":"PUBLICATION_UNCERTAIN","marker":marker})
            raise
        atomic(receipt,{"status":"PUBLISHED","marker":marker})
if __name__=="__main__": main()
