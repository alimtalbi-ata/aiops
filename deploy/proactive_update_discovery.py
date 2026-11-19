#!/usr/bin/env python3
"""Read-only release discovery; activation deliberately separate."""
import json
import re
import subprocess
from pathlib import Path
from proactive_candidate import atomic, REPO

def get(path):
    return json.loads(subprocess.check_output(["gh","api","--method","GET",f"repos/{REPO}/{path}"],timeout=30))

def main():
    root=Path.home()/".local/state/aiops2-proactive"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    result={"state":"UPDATE_BLOCKED","activation_authorized":False}
    try:
        branch=get("branches/deploy/aiops2-stable")
        sha=branch["commit"]["sha"]
        if branch.get("protected") is not True or not re.fullmatch(r"[0-9a-f]{40}",sha):
            raise ValueError("unverified branch")
        import base64
        entry=get(f"contents/deploy/proactive-release.json?ref={sha}")
        manifest=json.loads(base64.b64decode(entry["content"],validate=False))
        if manifest.get("schema")!=1 or manifest.get("enabled") is not True:
            raise ValueError("disabled manifest")
        result.update(state="REVIEW_REQUIRED",stable_sha=sha)
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        pass
    atomic(root/"update-candidate.json",result)

if __name__=="__main__": main()
