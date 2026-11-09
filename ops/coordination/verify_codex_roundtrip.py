#!/usr/bin/env python3
"""Fail-closed verification of an observed GitHub -> Codex -> GitHub round trip.

Only reads an independently collected JSON receipt; does not invoke Codex.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
SESSION = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
REQUIRED = {"schema_version", "correlation_id", "work_id", "executor",
            "session_id", "started_at", "finished_at", "source_sha",
            "result_sha", "task_url", "result_url", "exit_code", "evidence_kind"}

def stamp(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != dt.timedelta(0):
        raise ValueError("timestamp must be UTC")
    return value

def verify(receipt, expected_work_id=None):
    if not isinstance(receipt, dict) or set(receipt) != REQUIRED:
        raise ValueError("invalid receipt fields")
    if receipt["schema_version"] != "aiops.codex-roundtrip.v1":
        raise ValueError("unknown schema")
    if expected_work_id is not None and receipt["work_id"] != expected_work_id:
        raise ValueError("work mismatch")
    if receipt["executor"] not in {"codex.cli.debian", "codex.cloud"}:
        raise ValueError("executor not recognized")
    if not isinstance(receipt["session_id"], str) or not SESSION.fullmatch(receipt["session_id"]):
        raise ValueError("session ID missing or malformed")
    if not all(isinstance(receipt[k], str) and SHA.fullmatch(receipt[k]) for k in ("source_sha", "result_sha")):
        raise ValueError("exact SHAs required")
    if stamp(receipt["finished_at"]) < stamp(receipt["started_at"]):
        raise ValueError("time order inconsistent")
    if type(receipt["exit_code"]) is not int or receipt["exit_code"] != 0:
        raise ValueError("Codex execution did not succeed")
    if receipt["evidence_kind"] != "OBSERVED":
        raise ValueError("synthetic or unverified receipt")
    if not isinstance(receipt["correlation_id"], str) or not receipt["correlation_id"]:
        raise ValueError("missing correlation ID")
    for key in ("task_url", "result_url"):
        value = receipt[key]
        if not isinstance(value, str) or not value.startswith("https://github.com/alimtalbi-ata/aiops/"):
            raise ValueError("noncanonical evidence link")
    return {"status": "STRUCTURALLY_VALID_OBSERVED_CLAIM",
            "work_id": receipt["work_id"], "session_id": receipt["session_id"],
            "source_sha": receipt["source_sha"], "result_sha": receipt["result_sha"],
            "warning": "Receipt contents must still be independently cross-checked against Codex and GitHub job records"}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("receipt", type=Path)
    p.add_argument("--work-id")
    a = p.parse_args()
    try:
        if a.receipt.is_symlink() or not a.receipt.is_file() or a.receipt.stat().st_size > 65536:
            raise ValueError("receipt must be a bounded regular file")
        result = verify(json.loads(a.receipt.read_text(encoding="utf-8")), a.work_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as e:
        print("DISPATCH_NOT_VERIFIED:", e, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
