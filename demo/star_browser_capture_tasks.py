"""Fail-closed, offline Chromium navigation instructions from STAR capture worklist.

Operator must supply reviewed exact URLs for every ready cue. No URLs are guessed.
This module does not drive a browser or attest a runtime.
"""
from __future__ import annotations
from urllib.parse import urlsplit
from demo.star_browser_request_fence import canonical_origin
from demo.star_snapshot_choreography import CUES

def build_browser_capture_tasks(worklist: dict, reviewed_urls: dict, origins: dict) -> dict:
    if not isinstance(worklist, dict) or worklist.get("schema") != "star-capture-execution-worklist-v1":
        raise ValueError("unrecognized STAR worklist")
    steps = worklist.get("steps")
    if not isinstance(steps, list) or len(steps) != len(CUES):
        raise ValueError("invalid STAR steps")
    if worklist.get("runtime_proof_count") != 0 or worklist.get("read_only") is not True or worklist.get("live_action_authorized") is not False:
        raise ValueError("unsafe STAR worklist")
    if not isinstance(reviewed_urls, dict) or not isinstance(origins, dict) or set(origins) != {"n8n", "glpi", "grafana"}:
        raise ValueError("invalid approved browser origins")
    if set(reviewed_urls) - {cue.cue for cue in CUES}:
        raise ValueError("unexpected URL mapping")
    for origin in origins.values():
        if not isinstance(origin, str) or canonical_origin(origin) != origin:
            raise ValueError("unsafe approved origin")
    tasks = []
    seen_urls = set()
    for step, cue in zip(steps, CUES):
        if not isinstance(step, dict) or step.get("cue") != cue.cue or step.get("application") != cue.service or step.get("expected_view") != cue.view:
            raise ValueError("mismatched cue")
        status = step.get("status")
        if status not in ("READY_FOR_READ_ONLY_CAPTURE", "MISSING_IDENTIFIERS"):
            raise ValueError("untrusted status")
        ids = step.get("capture_identifiers")
        if not isinstance(ids, dict) or ids.get("run_id") != worklist.get("run_id"):
            raise ValueError("missing run binding")
        url = reviewed_urls.get(cue.cue)
        if status == "MISSING_IDENTIFIERS":
            if url is not None:
                raise ValueError("URL provided for blocked capture")
            continue
        if not isinstance(url, str) or canonical_origin(url) != origins[cue.service]:
            raise ValueError("missing or unauthorized exact navigation URL")
        parts = urlsplit(url)
        if parts.query or parts.fragment or not parts.path.startswith("/") or "//" in parts.path or ".." in parts.path:
            raise ValueError("unreviewed URL path/query")
        if url in seen_urls:
            raise ValueError("same page reused across independent checkpoints")
        seen_urls.add(url)
        tasks.append({
            "cue":cue.cue, "application":cue.service, "expected_view":cue.view,
            "run_id":worklist["run_id"], "capture_identifiers":ids,
            "exact_reviewed_url":url, "method":"GET", "navigation_only":True,
            "authenticated_runtime_proof":False, "capture_performed":False,
        })
    return {"schema":"star-browser-capture-tasks-v1", "run_id":worklist["run_id"],
            "tasks":tasks, "browser_executed":False, "read_only":True,
            "runtime_proof_count":0, "live_action_authorized":False}
