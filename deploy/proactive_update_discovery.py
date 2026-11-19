#!/usr/bin/env python3
"""Read-only release discovery; activation deliberately separate."""
import base64
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from proactive_candidate import atomic, REPO

def get(path):
    return json.loads(subprocess.check_output(["gh","api","--method","GET",f"repos/{REPO}/{path}"],timeout=30))

def validate_manifest(manifest):
    if not isinstance(manifest,dict):
        raise ValueError("manifest must be an object")
    required={"schema","enabled","expires_at","source_sha","artifact_digest"}
    if set(manifest)!=required:
        raise ValueError("manifest keys do not match strict schema")
    if type(manifest["schema"]) is not int or manifest["schema"]!=1:
        raise ValueError("unsupported schema")
    if manifest["enabled"] is not True:
        raise ValueError("manifest disabled")
    if not isinstance(manifest["source_sha"],str) or not re.fullmatch(r"[0-9a-f]{40}",manifest["source_sha"]):
        raise ValueError("invalid source SHA")
    if not isinstance(manifest["artifact_digest"],str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",manifest["artifact_digest"]):
        raise ValueError("invalid artifact digest")
    if not isinstance(manifest["expires_at"],str):
        raise ValueError("invalid expiry")
    expires=dt.datetime.fromisoformat(manifest["expires_at"].replace("Z","+00:00"))
    if expires.tzinfo is None or expires.utcoffset() is None:
        raise ValueError("expiry must include timezone")
    if expires<=dt.datetime.now(dt.timezone.utc):
        raise ValueError("manifest expired")
    return manifest

def main():
    root=Path.home()/".local/state/aiops2-proactive"
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    # Withdraw previous candidate before network calls; failures stay fail-closed.
    result={"state":"UPDATE_BLOCKED","activation_authorized":False}
    atomic(root/"update-candidate.json",result)
    try:
        branch=get("branches/deploy/aiops2-stable")
        sha=branch["commit"]["sha"]
        if branch.get("protected") is not True or not re.fullmatch(r"[0-9a-f]{40}",sha):
            raise ValueError("unverified branch")
        entry=get(f"contents/deploy/proactive-release.json?ref={sha}")
        raw=base64.b64decode("".join(entry["content"].split()),validate=True)
        manifest=validate_manifest(json.loads(raw))
        if manifest["source_sha"]!=sha:
            raise ValueError("manifest source SHA does not match protected branch")
        result={"state":"REVIEW_REQUIRED","stable_sha":sha,"artifact_digest":manifest["artifact_digest"],"expires_at":manifest["expires_at"],"activation_authorized":False}
    except Exception as exc:
        result={"state":"UPDATE_BLOCKED","error_type":type(exc).__name__,"activation_authorized":False}
    atomic(root/"update-candidate.json",result)

if __name__=="__main__": main()
