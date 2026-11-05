#!/usr/bin/env python3
"""Offline, fail-closed verifier for synthetic filesystem host receipts.

This does not deploy, execute, approve, or publish anything.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import re
import sys

RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
ROOT = pathlib.Path("/home/aiops/.local/state/aiops2-demo-filesystem")

def verify(directory, expected_run, expected_source_sha):
    if not RUN.fullmatch(expected_run):
        raise ValueError("invalid expected run id")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
        raise ValueError("invalid source commit")
    directory = pathlib.Path(directory)
    if directory.is_symlink() or directory.resolve() != (ROOT / "runs" / expected_run):
        raise ValueError("receipt path outside fixed root or symlink")
    for filename in ("state.json", "receipt.json"):
        if (directory / filename).is_symlink():
            raise ValueError("symlink input")
    state_bytes = (directory / "state.json").read_bytes()
    state = json.loads(state_bytes)
    receipt = json.loads((directory / "receipt.json").read_text())
    if receipt.get("run_id") != expected_run or state.get("run_id") != expected_run:
        raise ValueError("run mismatch")
    if receipt.get("source_sha") != expected_source_sha:
        raise ValueError("source mismatch")
    if receipt.get("state_sha256") != hashlib.sha256(state_bytes).hexdigest():
        raise ValueError("state hash mismatch")
    if receipt.get("mode") != "SYNTHETIC_NO_EFFECT":
        raise ValueError("not synthetic")
    if receipt.get("host") != "SRV-DEB-05":
        raise ValueError("wrong host")
    timestamp = receipt.get("collected_at")
    if not isinstance(timestamp, str):
        raise ValueError("missing timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    if parsed > datetime.now(timezone.utc):
        raise ValueError("future timestamp")
    return {"status": "VERIFIED_SYNTHETIC_RECEIPT_ONLY", "run_id": expected_run,
            "source_sha": expected_source_sha, "state_sha256": receipt["state_sha256"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.directory, args.run_id, args.source_sha), sort_keys=True))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "NO_GO", "reason": str(exc)}), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
